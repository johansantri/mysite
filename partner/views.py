from django.shortcuts import render, get_object_or_404, redirect
from courses.models import Partner
from authentication.models import Universiti
from courses.forms import PartnerFormUpdate
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator,EmptyPage, PageNotAnInteger
from django.http import HttpResponseForbidden
from courses.models import Course, Enrollment,CourseRating,CourseComment,CourseViewLog,UserActivityLog,CourseSessionLog,Certificate
from authentication.models import CustomUser
from collections import defaultdict
from django.db.models import Avg, Count, Q,F,FloatField, ExpressionWrapper
from django.contrib import messages
from datetime import timedelta
from django.utils.timezone import now
from django.http import Http404
from django.db.models.functions import ExtractHour, ExtractWeekDay
from django.contrib.auth.decorators import login_required, user_passes_test
from django.views.decorators.cache import cache_page
import json
from django.db.models.functions import TruncDate, ExtractWeekDay
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.db.models import Count, Sum
from .utils import get_geo_from_ip
from audit.models import AuditLog
from django.db.models.functions import TruncMonth
from collections import defaultdict
from decimal import Decimal
from django.db.models.functions import TruncWeek


@login_required
@user_passes_test(lambda u: u.is_superuser or u.is_partner)
def active_partners_view(request):
    partners = Partner.objects.all()

    if request.user.is_partner and not request.user.is_superuser:
        try:
            partners = partners.filter(user=request.user)
        except Partner.DoesNotExist:
            messages.error(request, "Akun Anda belum terhubung ke data Partner.")
            return redirect('authentication:dashboard')

    partners = partners.annotate(
        total_courses=Count('courses', distinct=True),
        total_certificates=Count('courses__certificates', distinct=True)
    ).order_by('-total_courses', '-total_certificates')[:10]

    labels = [partner.name.name for partner in partners]
    course_counts = [partner.total_courses for partner in partners]
    certificate_counts = [partner.total_certificates for partner in partners]

    return render(request, 'partner/active_partners.html', {
        'labels': labels,
        'course_counts': course_counts,
        'certificate_counts': certificate_counts,
    })



@login_required
@user_passes_test(lambda u: u.is_superuser or u.is_partner)
def certificate_analytics_view(request):
    # Ambil course berdasarkan partner jika bukan superuser
    courses = Course.objects.all()

    if request.user.is_partner and not request.user.is_superuser:
        try:
            partner = request.user.partner_user
            courses = courses.filter(org_partner=partner)
        except Partner.DoesNotExist:
            messages.error(request, "Akun Anda belum terhubung ke data Partner.")
            return redirect('authentication:dashboard')

    # Sertifikat per bulan
    monthly_certificates = (
        Certificate.objects.filter(course__in=courses)
        .annotate(month=TruncMonth('issue_date'))
        .values('month')
        .annotate(count=Count('id'))
        .order_by('month')
    )
    labels = [entry['month'].strftime('%b %Y') for entry in monthly_certificates]
    counts = [entry['count'] for entry in monthly_certificates]

    # Rata-rata skor per course
    avg_scores = (
        Certificate.objects.filter(course__in=courses)
        .values('course__course_name')
        .annotate(avg_score=Avg('total_score'))
        .order_by('-avg_score')[:10]
    )
    score_labels = [entry['course__course_name'] for entry in avg_scores]
    scores = [float(entry['avg_score']) for entry in avg_scores]

    return render(request, 'partner/certificate_analytics.html', {
        'labels': labels,
        'counts': counts,
        'score_labels': score_labels,
        'scores': scores,
    })


@login_required
@user_passes_test(lambda u: u.is_superuser or u.is_partner)
def course_dropoff_rate_view(request):
    courses = Course.objects.all()

    if request.user.is_partner and not request.user.is_superuser:
        try:
            partner = request.user.partner_user
            courses = courses.filter(org_partner=partner)
        except Partner.DoesNotExist:
            messages.error(request, "Akun Anda belum terhubung ke data Partner.")
            return redirect('authentication:dashboard')

    data = (
        Enrollment.objects.filter(course__in=courses)
        .values('course__course_name')
        .annotate(
            total_enrolled=Count('id'),
            total_completed=Count('id', filter=Q(certificate_issued=True))
        )
        .order_by('-total_enrolled')[:10]
    )

    labels = [entry['course__course_name'] for entry in data]
    completed = [entry['total_completed'] for entry in data]
    dropoffs = [entry['total_enrolled'] - entry['total_completed'] for entry in data]

    return render(request, 'partner/course_dropoff_rate.html', {
        'labels': labels,
        'completed': completed,
        'dropoffs': dropoffs,
    })

@login_required
@user_passes_test(lambda u: u.is_superuser or u.is_partner)
def course_enrollment_growth_view(request):
    courses = Course.objects.all()

    # Filter untuk partner
    if request.user.is_partner and not request.user.is_superuser:
        try:
            partner = request.user.partner_user
            courses = courses.filter(org_partner=partner)
        except Partner.DoesNotExist:
            messages.error(request, "Akun Anda belum terhubung ke data Partner.")
            return redirect('authentication:dashboard')

    enrollments = (
        Enrollment.objects.filter(course__in=courses)
        .annotate(month=TruncMonth('enrolled_at'))
        .values('course__course_name', 'month')
        .annotate(count=Count('id'))
        .order_by('month')
    )

    course_data = defaultdict(lambda: defaultdict(int))
    months_set = set()

    for entry in enrollments:
        course_name = entry['course__course_name']
        month = entry['month'].strftime('%Y-%m')
        course_data[course_name][month] = entry['count']
        months_set.add(month)

    all_months = sorted(list(months_set))

    datasets = []
    for i, (course, month_data) in enumerate(course_data.items()):
        datasets.append({
            'label': course,
            'data': [month_data.get(month, 0) for month in all_months],
            'color_hue': (i * 45) % 360,
        })

    return render(request, 'partner/course_enrollment_growth.html', {
        'labels': all_months,
        'datasets': datasets,
    })


@login_required
@user_passes_test(lambda u: u.is_superuser or u.is_partner)
def top_courses_by_rating_view(request):
    courses = Course.objects.all()

    # Jika partner, filter berdasarkan org_partner
    if request.user.is_partner and not request.user.is_superuser:
        try:
            partner = request.user.partner_user  # relasi OneToOne ke Partner
            courses = courses.filter(org_partner=partner)
        except Partner.DoesNotExist:
            messages.error(request, "Akun Anda belum terhubung ke data Partner.")
            return redirect('authentication:dashboard')

    top_courses = (
        courses.annotate(avg_rating=Avg('ratings__rating'))
        .filter(avg_rating__isnull=False)
        .order_by('-avg_rating')[:10]
    )

    labels = [course.course_name for course in top_courses]
    ratings = [round(course.avg_rating, 2) for course in top_courses]

    return render(request, 'partner/top_courses_by_rating.html', {
        'labels': labels,
        'ratings': ratings,
    })

@login_required
@user_passes_test(lambda u: u.is_superuser or getattr(u, 'is_partner', False))
def retention_rate_view(request):
    today = now().date()
    start_date = today - timedelta(weeks=12)

    users = CustomUser.objects.filter(date_joined__gte=start_date)

    # Jika user partner, filter berdasarkan partner
    if request.user.is_partner and not request.user.is_superuser:
        try:
            partner = request.user.partner_user  # related_name dari Partner
            users = users.filter(partner_user=partner)  # pastikan ini sesuai dengan OneToOne atau FK
        except Partner.DoesNotExist:
            messages.error(request, "Akun Anda belum terhubung ke data Partner.")
            return redirect('authentication:dashboard')

    # Cohort by week
    cohorts = (
        users
        .annotate(week_joined=TruncWeek('date_joined'))
        .values('week_joined')
        .annotate(
            new_users=Count('id'),
            retained_users=Count('id', filter=Q(last_login__gte=F('date_joined') + timedelta(days=7)))
        )
        .order_by('week_joined')
    )

    week_labels = [c['week_joined'].strftime('%Y-%m-%d') for c in cohorts]
    new_users = [c['new_users'] for c in cohorts]
    retained_users = [c['retained_users'] for c in cohorts]

    # Login activity per day
    user_ids = users.values_list('id', flat=True)
    activity = (
        UserActivityLog.objects.filter(
            activity_type='login',
            timestamp__gte=start_date,
            user_id__in=user_ids
        )
        .annotate(day=TruncDate('timestamp'))
        .values('day')
        .annotate(active_users=Count('user', distinct=True))
        .order_by('day')
    )

    day_labels = [a['day'].strftime('%Y-%m-%d') for a in activity]
    daily_active_users = [a['active_users'] for a in activity]

    return render(request, 'partner/retention_rate.html', {
        'week_labels': week_labels,
        'new_users': new_users,
        'retained_users': retained_users,
        'day_labels': day_labels,
        'daily_active_users': daily_active_users,
    })






def is_passed(user, course):
    from courses.models import Assessment, QuestionAnswer, GradeRange, CourseProgress

    # Ambil semua assessment terkait course
    assessments = Assessment.objects.filter(section__courses=course).distinct()
    total_score = Decimal(0)
    total_max_score = Decimal(0)
    all_submitted = True

    for assessment in assessments:
        total_questions = assessment.questions.count()
        if total_questions == 0:
            continue

        correct_answers = 0
        answered = False
        for question in assessment.questions.all():
            answers = QuestionAnswer.objects.filter(question=question, user=user)
            if answers.exists():
                answered = True
                correct_answers += answers.filter(choice__is_correct=True).count()

        if not answered:
            all_submitted = False

        score = (Decimal(correct_answers) / Decimal(total_questions)) * Decimal(assessment.weight)
        total_score += score
        total_max_score += Decimal(assessment.weight)

    percentage = (total_score / total_max_score) * 100 if total_max_score > 0 else 0

    # Ambil progress dari CourseProgress
    course_progress = CourseProgress.objects.filter(user=user, course=course).first()
    progress_percentage = course_progress.progress_percentage if course_progress else 0

    # Ambil passing grade dari GradeRange
    grade_range = GradeRange.objects.filter(course=course).first()
    passing_threshold = grade_range.min_grade if grade_range else 0

    return progress_percentage == 100 and all_submitted and percentage >= passing_threshold


@login_required
@user_passes_test(lambda u: u.is_superuser or u.is_partner)
def course_completion_rate_view(request):
    # Ambil semua course
    courses = Course.objects.all()

    # Filter berdasarkan partner jika user adalah partner
    if request.user.is_partner and not request.user.is_superuser:
        try:
            partner = request.user.partner_user  # sesuai related_name di model Partner
            courses = courses.filter(org_partner=partner)
        except Partner.DoesNotExist:
            messages.error(request, "Akun Anda belum terhubung ke data Partner.")
            return redirect('authentication:dashboard')  # ganti dengan halaman dashboard atau error

    results = []

    for course in courses:
        enrollments = Enrollment.objects.filter(course=course)
        total_enrolled = enrollments.count()

        total_passed = 0
        for enrollment in enrollments.select_related('user'):
            if is_passed(enrollment.user, course):  # logika lulus aktual
                total_passed += 1

        results.append({
            'course_name': course.course_name,
            'total_enrolled': total_enrolled,
            'total_completed': total_passed
        })

    # Urutkan dan ambil 10 teratas
    sorted_results = sorted(results, key=lambda x: x['total_enrolled'], reverse=True)[:10]

    labels = [entry['course_name'] for entry in sorted_results]
    completed = [entry['total_completed'] for entry in sorted_results]
    not_completed = [entry['total_enrolled'] - entry['total_completed'] for entry in sorted_results]

    return render(request, 'partner/course_completion_rate.html', {
        'labels': labels,
        'completed': completed,
        'not_completed': not_completed,
    })




@login_required
@user_passes_test(lambda u: u.is_superuser or u.is_partner)
def user_growth_view(request):
    data = (
        CustomUser.objects
        .filter(date_joined__isnull=False)
        .annotate(month=TruncMonth('date_joined'))
        .values('month')
        .annotate(count=Count('id'))
        .order_by('month')
    )

    months = [entry['month'].strftime('%b %Y') for entry in data]
    counts = [entry['count'] for entry in data]

    return render(request, 'partner/user_growth.html', {
        'months': months,
        'counts': counts,
    })


@login_required
@user_passes_test(lambda u: u.is_superuser or u.is_partner)
def popular_courses_view(request):
    courses = Course.objects.all()

    # Filter khusus partner
    if request.user.is_partner and not request.user.is_superuser:
        try:
            partner = request.user.partner_user  # Sesuai dengan related_name di model
            courses = courses.filter(org_partner=partner)
        except Partner.DoesNotExist:
            messages.error(request, "Akun Anda belum terhubung ke data Partner.")
            return redirect('authentication:dashboard')  # ganti dengan URL yang sesuai

    data = (
        courses.annotate(enrollment_count=Count('enrollments'))
        .order_by('-enrollment_count')[:10]
    )

    labels = [course.course_name for course in data]
    counts = [course.enrollment_count for course in data]

    return render(request, 'partner/popular_courses.html', {
        'labels': labels,
        'counts': counts,
    })



@login_required
@user_passes_test(lambda u: u.is_superuser or u.is_partner)
def device_usage_view(request):
    logs = AuditLog.objects.filter(action='login')

    if request.user.is_partner:
        partner = getattr(request.user, 'partner_user', None)
        if partner:
            logs = logs.filter(user__enrollments__course__org_partner=partner).distinct()

    data = (
        logs.values('device_type')
        .annotate(count=Count('id'))
        .order_by('-count')
    )

    labels = [item['device_type'] or 'Unknown' for item in data]
    counts = [item['count'] for item in data]

    return render(request, 'partner/device_usage.html', {
        'labels': labels,
        'counts': counts,
    })

@login_required
@user_passes_test(lambda u: u.is_superuser or u.is_partner)
def participant_geography_view(request):
    view_mode = request.GET.get('view', 'country')  # default: country

    logs = CourseSessionLog.objects.exclude(location_country__isnull=True)

    if request.user.is_partner and not request.user.is_superuser:
        try:
            partner = request.user.partner_user
            partner_courses = Course.objects.filter(org_partner=partner)
            logs = logs.filter(course__in=partner_courses)
        except Exception:
            logs = logs.none()  # jika partner tidak valid, tampilkan kosong

    if view_mode == 'city':
        data = (
            logs.exclude(location_city__isnull=True)
            .values('location_country', 'location_city')
            .annotate(total=Count('id'))
            .order_by('-total')[:10]
        )
        labels = [
            f"{item['location_city']}, {item['location_country']}" for item in data
        ]
    else:
        data = (
            logs.values('location_country')
            .annotate(total=Count('id'))
            .order_by('-total')[:10]
        )
        labels = [item['location_country'] for item in data]

    totals = [item['total'] for item in data]

    return render(request, 'partner/participant_geography.html', {
        'countries': labels,
        'totals': totals,
        'view_mode': view_mode,
    })


@login_required
@user_passes_test(lambda u: u.is_superuser or u.is_partner)
def learning_duration_view(request):
    # Ambil daftar course berdasarkan role
    if request.user.is_superuser:
        courses = Course.objects.all()
    else:
        partner = getattr(request.user, 'partner_user', None)
        if not partner:
            raise Http404("Partner profile not found.")
        courses = Course.objects.filter(org_partner=partner)

    session_logs = CourseSessionLog.objects.filter(course__in=courses)

    today = now().date()
    week_ago = today - timedelta(days=7)
    month_ago = today - timedelta(days=30)

    # Total waktu belajar (detik)
    weekly_seconds = session_logs.filter(started_at__date__gte=week_ago).aggregate(total=Sum('duration_seconds'))['total'] or 0
    monthly_seconds = session_logs.filter(started_at__date__gte=month_ago).aggregate(total=Sum('duration_seconds'))['total'] or 0

    # Waktu belajar per course
    duration_by_course = (
        session_logs.values('course__course_name')
        .annotate(total_seconds=Sum('duration_seconds'))
        .order_by('-total_seconds')[:10]
    )

    # Ubah detik ke menit
    for item in duration_by_course:
        item['total_minutes'] = round(item['total_seconds'] / 60)

    context = {
        'weekly_minutes': round(weekly_seconds / 60),
        'monthly_minutes': round(monthly_seconds / 60),
        'duration_by_course': duration_by_course,
    }

    return render(request, 'partner/learning_duration.html', context)


@csrf_exempt
@login_required
def ping_session(request):
    if request.method == "POST":
        try:
            data = json.loads(request.body)
            course_id = data.get("course_id")
            course = Course.objects.get(id=course_id)
        except (json.JSONDecodeError, Course.DoesNotExist):
            return JsonResponse({"error": "Invalid course_id"}, status=400)

        ip_address = get_client_ip(request)

        session, created = CourseSessionLog.objects.get_or_create(
            user=request.user,
            course=course,
            ended_at__isnull=True,
            defaults={
                "started_at": now(),
                "user_agent": request.META.get("HTTP_USER_AGENT", "")[:255],
                "ip_address": ip_address,
            }
        )

        session.ended_at = now()

        if not session.location_country:
            session.location_country, session.location_city = get_geo_from_ip(ip_address)

        session.save()

        return JsonResponse({"status": "ok", "duration_seconds": session.duration_seconds})

    return JsonResponse({"error": "Invalid method"}, status=405)


def get_client_ip(request):
    x_forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
    if x_forwarded:
        return x_forwarded.split(",")[0]
    return request.META.get("REMOTE_ADDR")


# Cek user: hanya superuser atau staff yang boleh mengakses
def is_superuser_or_partner(user):
    return user.is_authenticated and (user.is_superuser or getattr(user, 'is_partner', False))


@user_passes_test(is_superuser_or_partner)
def login_trends_view(request):
    # Ambil hanya aktivitas login
    logins_per_day = (
        UserActivityLog.objects
        .filter(activity_type='login_view')
        .annotate(date=TruncDate('timestamp'))
        .values('date')
        .annotate(count=Count('id'))
        .order_by('date')
    )

    logins_by_day = (
        UserActivityLog.objects
        .filter(activity_type='login_view')
        .annotate(weekday=ExtractWeekDay('timestamp'))
        .values('weekday')
        .annotate(count=Count('id'))
        .order_by('weekday')
    )

    # Map nama hari dari weekday (1 = Sunday di PostgreSQL)
    days_map = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday']
    login_day_data = []
    for item in logins_by_day:
        index = (item['weekday'] - 1) % 7  # Perlindungan terhadap index error
        login_day_data.append({
            "day": days_map[index],
            "count": item['count']
        })

    context = {
        "logins_per_day": json.dumps([
            {
                "date": item['date'].strftime('%Y-%m-%d'),
                "count": item['count']
            } for item in logins_per_day
        ]),
        "logins_by_day": json.dumps(login_day_data),
    }

    return render(request, 'partner/login_trends.html', context)


# Hanya superuser dan partner yang boleh akses
def is_superuser_or_partner(user):
    return user.is_authenticated and (user.is_superuser or getattr(user, 'is_partner', False))

@login_required
@user_passes_test(lambda u: u.is_superuser or u.is_partner)
def heatmap_view(request):
    qs = (
        UserActivityLog.objects
        .annotate(
            hour=ExtractHour('timestamp'),
            weekday=ExtractWeekDay('timestamp')
        )
        .values('hour', 'weekday')
        .annotate(count=Count('id'))
        .order_by('hour', 'weekday')
    )

    # Format heatmap data
    heatmap_data = []
    for item in qs:
        hour = item['hour']
        weekday = (item['weekday'] - 1) % 7  # ubah dari 1=Sunday menjadi 0=Sunday
        heatmap_data.append({
            "x": hour,
            "y": weekday,
            "v": item['count'],
        })

    return render(request, 'partner/heatmap.html', {
        'heatmap_data': json.dumps(heatmap_data),
    })


@login_required
def partner_analytics_view(request):
    user = request.user

    # Cek apakah user superuser atau partner
    if not (user.is_superuser or getattr(user, 'is_partner', False)):
        raise Http404("You are not authorized to access this page.")

    # Jika superuser → bisa akses semua course
    if user.is_superuser:
        courses = Course.objects.all().only('id', 'course_name')
    else:
        # Jika partner → hanya course milik partner
        partner = getattr(user, 'partner_user', None)
        if not partner:
            raise Http404("Partner profile not found.")
        courses = Course.objects.filter(org_partner=partner).only('id', 'course_name')

    # Ambil log view untuk kursus-kursus tersebut
    logs = CourseViewLog.objects.filter(course__in=courses).select_related('course')

    # Waktu referensi
    today = now().date()
    week_ago = today - timedelta(days=7)
    month_ago = today - timedelta(days=30)

    # Total view dalam 7 hari dan 30 hari terakhir
    weekly_views = logs.filter(date__gte=week_ago).aggregate(total=Count('count'))['total'] or 0
    monthly_views = logs.filter(date__gte=month_ago).aggregate(total=Count('count'))['total'] or 0

    # View per course (limit 10 besar agar chart ringan)
    view_by_course = (
        logs.values('course__course_name')
        .annotate(total=Count('count'))
        .order_by('-total')[:10]
    )

    # Komentar per course (limit 10 besar)
    comment_by_course = (
        CourseComment.objects.filter(course__in=courses)
        .values('course__course_name')
        .annotate(total=Count('id'))
        .order_by('-total')[:10]
    )

    return render(request, 'partner/analytics.html', {
        'weekly_views': weekly_views,
        'monthly_views': monthly_views,
        'view_by_course': view_by_course,
        'comment_by_course': comment_by_course,
    })


@login_required
def partner_course_comments(request):
    # Jika superuser, ambil semua course dan komentar
    if request.user.is_superuser:
        owned_courses = Course.objects.all()
    elif hasattr(request.user, 'partner_user'):
        # Jika partner, ambil hanya kursus miliknya
        partner = request.user.partner_user
        owned_courses = Course.objects.filter(org_partner=partner)
    else:
        # Selain itu, tolak akses
        return HttpResponseForbidden("You are not authorized to view this page.")

    # Ambil komentar utama dari course yang dimiliki
    comments = CourseComment.objects.filter(
        course__in=owned_courses,
        parent__isnull=True
    ).order_by('-created_at')

    # Paginasi
    paginator = Paginator(comments, 5)
    page = request.GET.get('page')
    try:
        comments_page = paginator.page(page)
    except PageNotAnInteger:
        comments_page = paginator.page(1)
    except EmptyPage:
        comments_page = paginator.page(paginator.num_pages)

    # Balasan komentar
    if request.method == 'POST':
        content = request.POST.get('content')
        parent_id = request.POST.get('parent_id')

        try:
            parent_comment = CourseComment.objects.get(id=parent_id, course__in=owned_courses)
        except CourseComment.DoesNotExist:
            return HttpResponseForbidden("Invalid parent comment.")

        if content:
            CourseComment.objects.create(
                user=request.user,
                content=content,
                course=parent_comment.course,
                parent=parent_comment
            )
            return redirect('partner:partner_course_comments')

    context = {
        'comments': comments_page
    }
    return render(request, 'partner/partner_course_comments.html', context)

@login_required
def post_comment_reply(request, course_id, comment_id=None):
    course = get_object_or_404(Course, id=course_id)

    # Pastikan yang mengakses adalah partner
    if not request.user.is_partner:
        return HttpResponseForbidden("You are not authorized to post replies.")

    if request.method == 'POST':
        content = request.POST.get('content')

        # Validasi konten komentar
        if content:
            # Menambahkan balasan komentar
            if comment_id:
                parent_comment = get_object_or_404(CourseComment, id=comment_id)
                reply = CourseComment.objects.create(
                    user=request.user,
                    content=content,
                    course=course,
                    parent=parent_comment
                )
                messages.success(request, "Your reply has been posted!")
            else:
                # Bisa digunakan jika Anda ingin menambah komentar baru juga
                CourseComment.objects.create(
                    user=request.user,
                    content=content,
                    course=course
                )
                messages.success(request, "Your comment has been posted!")
        else:
            messages.error(request, "Content cannot be empty.")

    return redirect('partner:course_lms_detail', id=course.id, slug=course.slug)

@login_required
def partner_course_ratings(request):
    if not request.user.is_partner:
        return HttpResponseForbidden("You are not authorized to view this page.")

    # Ambil semua course milik partner
    partner_courses = Course.objects.filter(org_partner__user=request.user)

    # Annotate dengan rata-rata dan jumlah rating, serta komentar
    course_rating_data = partner_courses.annotate(
        avg_rating=Avg('ratings__rating'),
        rating_count=Count('ratings')
    ).order_by('-avg_rating')  # Urutkan berdasarkan rating tertinggi

    # Ambil komentar terkait untuk setiap course
    course_ratings_details = {
        course.id: CourseRating.objects.filter(course=course)
        for course in partner_courses
    }

    context = {
        'course_rating_data': course_rating_data,
        'course_ratings_details': course_ratings_details,
    }

    return render(request, 'partner/partner_course_ratings.html', context)


@login_required
def partner_enrollment_view(request):
    if not request.user.is_partner:
        return HttpResponseForbidden("You are not authorized to view this page.")

    # Ambil universitas partner
    partner_university = request.user.university
    if not partner_university:
        return HttpResponseForbidden("Your account is not linked to any university.")

    # Ambil semua course milik partner
    owned_courses = Course.objects.filter(org_partner__user=request.user)

    # Ambil parameter arah enroll
    direction = request.GET.get("direction", "")  # inbound / outbound / internal / all

    # Filter berdasarkan arah enroll
    if direction == "inbound":
        users = CustomUser.objects.filter(
            enrollments__course__in=owned_courses
        ).exclude(university=partner_university).distinct()

    elif direction == "outbound":
        users = CustomUser.objects.filter(
            university=partner_university
        ).exclude(enrollments__course__in=owned_courses).distinct()

    elif direction == "internal":
        users = CustomUser.objects.filter(
            university=partner_university,
            enrollments__course__in=owned_courses
        ).distinct()

    else:
        # Default: semua user yang enroll ke course milik partner
        users = CustomUser.objects.filter(
            enrollments__course__in=owned_courses
        ).distinct()

    # ORDER BY untuk hindari warning dari Paginator
    users = users.order_by('id')

    # Hitung total user sebelum paginasi
    total_users = users.count()

    # Ambil enrollments
    enrollments = Enrollment.objects.select_related('course').filter(user__in=users)

    # Mapping user.id → course names
    user_courses_map = defaultdict(list)
    for enroll in enrollments:
        user_courses_map[enroll.user_id].append(enroll.course.course_name)

    # Pagination
    paginator = Paginator(users, 10)
    page_number = request.GET.get("page", 1)
    page_obj = paginator.get_page(page_number)

    context = {
        "users": page_obj,
        "direction": direction,
        "owned_courses": owned_courses,
        "user_courses_map": user_courses_map,
        "total_users": total_users,
    }

    return render(request, "partner/partner_enrollments.html", context)

# Create your views here.
@login_required
def partner_update_view(request, partner_id, universiti_slug):
    # Mendapatkan partner yang sesuai dengan ID yang diberikan
    partner = get_object_or_404(Partner, id=partner_id)

    # Mendapatkan universitas berdasarkan slug
    universiti = get_object_or_404(Universiti, slug=universiti_slug)

    # Mengecek apakah pengguna yang sedang login adalah pemilik partner tersebut
    if partner.user != request.user:
        return redirect('authentication:home')  # Redirect ke halaman jika pengguna bukan pemilik data
    if partner.name != universiti:
        return redirect('authentication:home')

    
    # Jika form dikirim (POST)
    if request.method == 'POST':
        form = PartnerFormUpdate(request.POST, request.FILES, instance=partner)
        if form.is_valid():
            partner = form.save(commit=False)
            partner.universiti = universiti  # Update universiti ke partner yang diubah
            partner.save()
            return redirect('courses:partner_detail', partner_id=partner.id)  # Redirect ke halaman profil partner
    else:
        form = PartnerFormUpdate(instance=partner)

    return render(request, 'partner/partner_update.html', {'form': form, 'universiti': universiti})


def explore(request):
    # Ambil semua mitra dari database
    partners_list = Partner.objects.all()
    
    # Tentukan jumlah mitra per halaman
    paginator = Paginator(partners_list, 6)  # Tampilkan 6 mitra per halaman
    
    # Dapatkan halaman yang saat ini diminta
    page_number = request.GET.get('page')  # Mendapatkan nomor halaman dari query parameter
    page_obj = paginator.get_page(page_number)  # Dapatkan objek halaman sesuai nomor halaman
    
    # Render halaman dengan mitra yang ditemukan dan objek pagination
    return render(request, 'partner/explore.html', {'page_obj': page_obj})