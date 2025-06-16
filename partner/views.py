from django.shortcuts import render, get_object_or_404, redirect
from courses.models import Partner
from authentication.models import Universiti
from courses.forms import PartnerFormUpdate
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator,EmptyPage, PageNotAnInteger
from django.http import HttpResponseForbidden
from courses.models import Course, Enrollment,CourseRating,CourseComment,CourseViewLog,UserActivityLog,CourseSessionLog
from authentication.models import CustomUser
from collections import defaultdict
from django.db.models import Avg, Count
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



@login_required
@user_passes_test(lambda u: u.is_superuser or u.is_partner)
def participant_geography_view(request):
    view_mode = request.GET.get('view', 'country')  # default: country

    if view_mode == 'city':
        data = (
            CourseSessionLog.objects
            .exclude(location_country__isnull=True)
            .exclude(location_city__isnull=True)
            .values('location_country', 'location_city')
            .annotate(total=Count('id'))
            .order_by('-total')[:10]
        )
        labels = [
            f"{item['location_city']}, {item['location_country']}" for item in data
        ]
    else:
        data = (
            CourseSessionLog.objects
            .exclude(location_country__isnull=True)
            .values('location_country')
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
    # Jika superuser, tampilkan semua course
    if request.user.is_superuser:
        courses = Course.objects.all()
    else:
        partner = getattr(request.user, 'partner_user', None)
        if not partner:
            raise Http404("Partner profile not found.")
        courses = Course.objects.filter(org_partner=partner)

    # Ambil session log berdasarkan course yang dimiliki
    session_logs = CourseSessionLog.objects.filter(course__in=courses)

    today = now().date()
    week_ago = today - timedelta(days=7)
    month_ago = today - timedelta(days=30)

    # Hitung total waktu belajar dalam detik
    weekly_seconds = session_logs.filter(started_at__date__gte=week_ago).aggregate(total=Sum('duration_seconds'))['total'] or 0
    monthly_seconds = session_logs.filter(started_at__date__gte=month_ago).aggregate(total=Sum('duration_seconds'))['total'] or 0

    # Total waktu belajar per course
    duration_by_course = (
        session_logs.values('course__course_name')
        .annotate(total_seconds=Sum('duration_seconds'))
        .order_by('-total_seconds')[:10]
    )

    # Ubah ke menit
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
def is_superuser_or_staff(user):
    return user.is_authenticated and (user.is_superuser or user.is_staff)


@user_passes_test(is_superuser_or_staff)
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
@user_passes_test(is_superuser_or_partner)
def heatmap_view(request):
    qs = (
        UserActivityLog.objects
        .annotate(hour=ExtractHour('timestamp'), weekday=ExtractWeekDay('timestamp'))
        .values('hour', 'weekday')
        .annotate(count=Count('id'))
    )

    # Buat heatmap format {x: hour, y: weekday (0-index), v: count}
    heatmap_data = []
    for item in qs:
        hour = item['hour']
        weekday = (item['weekday'] - 1) % 7  # 1=Sunday jadi 0-indexed, aman dari index error
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
    # Pastikan hanya partner yang bisa mengakses halaman ini
    if not request.user.is_superuser:
        return HttpResponseForbidden("You are not authorized to view this page.")

    # Ambil semua kursus yang dimiliki oleh partner
    owned_courses = Course.objects.filter(org_partner__user=request.user)
    
    # Ambil semua komentar dari kursus yang dimiliki partner, hanya komentar utama (parent__isnull=True)
    comments = CourseComment.objects.filter(course__in=owned_courses, parent__isnull=True).order_by('-created_at')

    # Paginasi komentar, tampilkan 5 komentar per halaman
    paginator = Paginator(comments, 5)
    page = request.GET.get('page')
    
    try:
        comments_page = paginator.page(page)
    except PageNotAnInteger:
        comments_page = paginator.page(1)
    except EmptyPage:
        comments_page = paginator.page(paginator.num_pages)

    # Tangani balasan komentar jika POST
    if request.method == 'POST':
        content = request.POST.get('content')
        parent_id = request.POST.get('parent_id')

        try:
            parent_comment = CourseComment.objects.get(id=parent_id, course__in=owned_courses)
        except CourseComment.DoesNotExist:
            return HttpResponseForbidden("Invalid parent comment.")

        if content:
            # Buat komentar balasan
            CourseComment.objects.create(
                user=request.user,
                content=content,
                course=parent_comment.course,
                parent=parent_comment
            )
            return redirect('partner:partner_course_comments')  # Redirect ke halaman komentar

    context = {
        'comments': comments_page  # Kirim komentar yang dipaginasi ke template
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