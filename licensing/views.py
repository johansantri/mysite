from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.core.mail import send_mail
from django.utils import timezone
from .models import Invitation, License
from .forms import InvitationForm
from django.core.paginator import Paginator
from django.contrib import messages
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.template.loader import render_to_string
from authentication.models import CustomUser
from django.urls import reverse
import uuid
from django.db.models import Count,F
from django.contrib.admin.views.decorators import staff_member_required
from django.core.validators import EmailValidator
from django.core.exceptions import ValidationError
import logging
from datetime import timedelta
from django.contrib.auth.tokens import PasswordResetTokenGenerator
from courses.models import Course, Enrollment,Certificate,MaterialRead,AssessmentRead

logger = logging.getLogger(__name__)

@login_required
def licens_dashboard(request):
    if not request.user.is_subscription:
        messages.error(request, "Akses ditolak. Hanya pengguna dengan status langganan yang dapat mengakses dashboard ini.")
        return redirect('authentication:home')

    # Ambil lisensi yang terkait dengan pengguna dan yang statusnya aktif
    licenses = License.objects.filter(users=request.user, status=True).prefetch_related('users')
    
    total_enrollments = 0
    total_passed = 0
    total_participants = 0
    all_courses = []

    license_course_data = []
    now = timezone.now().date()
    license_users = set()

    for license in licenses:
        # Ambil pengguna lain selain current user
        other_users = license.users.exclude(id=request.user.id)
        
        # Cek dan tampilkan informasi pengguna
        user_count = license.users.count()
        non_admin_count = other_users.count()
        invited_users_count = Invitation.objects.filter(license=license, status='accepted').count()

        # Tambahkan ke set peserta
        license_users.update(user.id for user in other_users)

        if user_count > license.max_users:
            messages.warning(request, f"Lisensi {license.name} melebihi kapasitas pengguna ({user_count}/{license.max_users}).")

        # Periksa jumlah pengguna non-admin dan undangan
        expected_users = invited_users_count + 1  # +1 jika admin dihitung
        if non_admin_count != invited_users_count:
            messages.warning(
                request, f"Jumlah pengguna non-admin ({non_admin_count}) di {license.name} "
                         f"tidak sesuai dengan jumlah undangan diterima ({invited_users_count})."
            )

        # Hitung sisa hari
        days_remaining = (license.expiry_date - now).days if license.expiry_date >= now else 0

        # Ambil kursus yang terdaftar di lisensi ini
        courses = Course.objects.filter(enrollments__user__in=other_users).select_related('org_partner').distinct()

        # Hitung enrollments dan certificates untuk kursus-kursus ini
        enrollment_count = Enrollment.objects.filter(user__in=other_users, course__in=courses).count()
        total_enrollments += enrollment_count

        passed_count = Certificate.objects.filter(user__in=other_users, course__in=courses).count()
        total_passed += passed_count

        # Data per kursus
        course_data = []
        for course in courses:
            course_enrollment_count = Enrollment.objects.filter(course=course, user__in=other_users).count()
            course_data.append({
                'course': course,
                'enrollment_count': course_enrollment_count,
            })
            all_courses.append({
                'course': course,
                'enrollment_count': course_enrollment_count,
            })

        license_course_data.append({
            'license': license,
            'courses': course_data,
            'enrollment_count': enrollment_count,
            'passed_count': passed_count,
            'days_remaining': days_remaining,
            'user_count': user_count,
            'non_admin_count': non_admin_count,
        })

    # Total peserta berdasarkan pengguna yang terdaftar
    total_participants = len(license_users)

    # Validasi jumlah peserta dan undangan
    accepted_invites_count = sum(
        Invitation.objects.filter(license=license, status='accepted').count() for license in licenses
    )
    if total_participants != accepted_invites_count:
        messages.warning(
            request,
            f"Total peserta ({total_participants}) tidak sesuai dengan jumlah undangan yang diterima."
        )

    # Hitung pass rate
    pass_rate = round((total_passed / total_enrollments * 100), 2) if total_enrollments > 0 else 0

    # Lisensi yang akan kedaluwarsa dalam 7 hari
    expiring_licenses = licenses.filter(
        expiry_date__gt=timezone.now(),
        expiry_date__lte=timezone.now() + timedelta(days=7)
    ).count()

    for lic in licenses.filter(expiry_date__gt=timezone.now(), expiry_date__lte=timezone.now() + timedelta(days=7)):
        messages.info(request, f"Lisensi kedaluwarsa dalam 7 hari: {lic.name} (Kedaluwarsa: {lic.expiry_date})")

    # Menentukan kursus teratas berdasarkan jumlah enrollments
    top_course = max(all_courses, key=lambda x: x['enrollment_count'], default=None) if all_courses else None

    # Ambil 5 enrollment terbaru
    recent_enrollments = Enrollment.objects.filter(
        user__in=CustomUser.objects.filter(id__in=license_users),
        course__in=Course.objects.filter(enrollments__user__in=CustomUser.objects.filter(id__in=license_users))
    ).select_related('user', 'course').order_by('-enrolled_at')[:5]

    # Kirimkan data ke template
    context = {
        'licenses': licenses,
        'license_course_data': license_course_data,
        'total_enrollments': total_enrollments,
        'total_passed': total_passed,
        'total_participants': total_participants,
        'pass_rate': pass_rate,
        'expiring_licenses': expiring_licenses,
        'top_course': top_course,
        'recent_enrollments': recent_enrollments,
    }

    return render(request, 'licensing/licens_dashboard.html', context)


@login_required
def licens_learners(request):
    if not request.user.is_subscription:
        messages.error(request, "Akses ditolak. Hanya pengguna dengan status langganan yang dapat mengakses dashboard ini.")
        return redirect('authentication:home')

    licenses = License.objects.filter(users=request.user)
    license_course_data = []

    for license in licenses:
        participants = license.users.exclude(id=request.user.id)
        enrollments = Enrollment.objects.filter(user__in=participants).select_related('user', 'course')
        courses = Course.objects.filter(enrollments__in=enrollments).distinct().prefetch_related('sections__materials', 'sections__assessments')

        course_data = []
        for course in courses:
            course_enrollments = enrollments.filter(course=course)
            user_ids = course_enrollments.values_list('user_id', flat=True)

            # Ambil semua sertifikat untuk course ini
            certificates = Certificate.objects.filter(user_id__in=user_ids, course=course)
            cert_map = {(c.user_id, c.course_id): c for c in certificates}

            # Ambil semua section dari course ini
            sections = course.sections.all()

            # Ambil semua material dan assessment terkait section-section ini
            section_ids = sections.values_list('id', flat=True)
            material_reads = MaterialRead.objects.filter(
                user_id__in=user_ids,
                material__section_id__in=section_ids
            ).order_by('-read_at')

            last_material_map = {}
            for mr in material_reads:
                key = (mr.user_id, mr.material_id)
                if key not in last_material_map:
                    last_material_map[key] = mr.read_at

            assessment_ids = []
            for section in sections:
                assessment_ids += list(section.assessments.values_list('id', flat=True))

            assessment_reads = AssessmentRead.objects.filter(
                user_id__in=user_ids,
                assessment_id__in=assessment_ids
            ).order_by('-completed_at')

            last_assessment_map = {}
            for ar in assessment_reads:
                key = (ar.user_id, ar.assessment_id)
                if key not in last_assessment_map:
                    last_assessment_map[key] = ar.completed_at

            enrollment_data = []
            for enrollment in course_enrollments:
                for section in sections:
                    for material in section.materials.all():
                        last_accessed = last_material_map.get((enrollment.user_id, material.id))

                        last_completed = None
                        for assessment in section.assessments.all():
                            time = last_assessment_map.get((enrollment.user_id, assessment.id))
                            if time and (not last_completed or time > last_completed):
                                last_completed = time

                        enrollment_data.append({
                            'enrollment': enrollment,
                            'certificate': cert_map.get((enrollment.user_id, course.id)),
                            'material': material,
                            'last_accessed_material': last_accessed,
                            'last_completed_assessment': last_completed,
                        })

            course_data.append({
                'course': course,
                'enrollments': enrollment_data,
                'enrollment_count': course_enrollments.count(),
            })

        license_course_data.append({
            'license': license,
            'courses': course_data,
        })

    # Paginasi (misal 2 lisensi per halaman)
    paginator = Paginator(license_course_data, 2)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'license_course_data': page_obj,
    }
    return render(request, 'licensing/licens_learners.html', context)




@login_required
def licens_analytics(request):
    # Pastikan pengguna adalah admin langganan (PT A)
    if not request.user.is_subscription:
        messages.error(request, "Akses ditolak. Hanya pengguna dengan status langganan yang dapat mengakses dashboard ini.")
        return redirect('authentication:home')

    # Ambil undangan
    invitations = Invitation.objects.filter(inviter=request.user)
    status = request.GET.get('status', '')
    search_query = request.GET.get('search_query', '')

    if status:
        invitations = invitations.filter(status=status)
    if search_query:
        invitations = invitations.filter(invitee_email__icontains=search_query)

    # Paginate invitations
    paginator = Paginator(invitations, 10)  # 10 undangan per halaman
    page_number = request.GET.get('page')
    invitations_page = paginator.get_page(page_number)

    # Statistik undangan
    invitation_stats = {
        'pending': Invitation.objects.filter(inviter=request.user, status='pending').count(),
        'accepted': Invitation.objects.filter(inviter=request.user, status='accepted').count(),
        'expired': Invitation.objects.filter(inviter=request.user, status='expired').count(),
    }

    context = {
        'invitations': invitations_page,
        'status': status,
        'search_query': search_query,
        'invitation_stats': invitation_stats,
    }
    return render(request, 'licensing/licens_analytics.html', context)



@login_required
def participant_dashboard(request):
    """Menampilkan dashboard khusus untuk peserta."""
    licenses = License.objects.filter(users=request.user)
    context = {
        'licenses': licenses,
    }
    return render(request, 'licensing/participant_dashboard.html', context)

@login_required

def delete_invitation(request, invitation_id):
    try:
        invitation = get_object_or_404(Invitation, id=invitation_id, inviter=request.user)
        invitation.delete()
        messages.success(request, "Undangan berhasil dihapus.")
    except Exception as e:
        logger.error(f"Error saat menghapus undangan ID {invitation_id}: {str(e)}")
        messages.error(request, f"Terjadi kesalahan: {str(e)}")
    return redirect('licensing:licens_dashboard')


@login_required
def cancel_invitation(request, invitation_id):
    """Menghapus undangan tertentu."""
    invitation = get_object_or_404(Invitation, id=invitation_id, inviter=request.user)
    invitation.delete()
    messages.success(request, f"Undangan untuk {invitation.invitee_email} telah dibatalkan.")
    return redirect('licensing:licens_dashboard')

@login_required
def resend_invitation(request, invitation_id):
    """Mengirim ulang undangan tertentu."""
    invitation = get_object_or_404(Invitation, id=invitation_id, inviter=request.user)
    
    if invitation.is_expired():
        invitation.expiry_date = timezone.now() + timedelta(days=7)
        invitation.token = str(uuid.uuid4())
        invitation.status = 'pending'
    
    accept_url = request.build_absolute_uri(
        reverse('licensing:accept_invitation', kwargs={
            'uidb64': urlsafe_base64_encode(str(invitation.id).encode()),
            'token': invitation.token
        })
    )
    html_message = render_to_string('licensing/invitation_email.html', {
        'invitation': invitation,
        'accept_url': accept_url,
    })
    subject = f"Undangan Dikirim Ulang dari {request.user.username}"
    send_mail(subject, '', 'from@example.com', [invitation.invitee_email], html_message=html_message, fail_silently=True)

    invitation.save()
    messages.success(request, f"Undangan untuk {invitation.invitee_email} telah dikirim ulang.")
    return redirect('licensing:licens_dashboard')

@login_required
def send_invitation(request):
    """View untuk PT A mengirim undangan ke satu atau banyak email."""
    if not request.user.is_subscription:
        return redirect('licensing:participant_dashboard')

    if request.method == 'POST':
        form = InvitationForm(request.POST)
        if form.is_valid():
            invitee_emails = form.cleaned_data['invitee_emails']
            email_list = [email.strip() for email in invitee_emails.replace('\n', ',').split(',') if email.strip()]

            if not email_list:
                messages.error(request, "Harap masukkan setidaknya satu email yang valid.")
                return render(request, 'licensing/send_invitation.html', {'form': form})

           
            license = License.objects.filter(users=request.user, status=True).order_by('-start_date').first()
            if not license:
                logger.error(f"Tidak ditemukan lisensi aktif untuk pengguna: {request.user.username} (ID: {request.user.id})")
                messages.error(request, "Tidak ditemukan lisensi aktif untuk akun Anda. Silakan hubungi Super Admin untuk membuat atau mengaktifkan lisensi.")
                return redirect('licensing:licens_dashboard')

           

            current_users = license.users.count()
            available_slots = license.max_users - current_users
            if len(email_list) > available_slots:
                messages.error(request, f"Tidak dapat mengundang {len(email_list)} pengguna. Hanya {available_slots} slot tersedia.")
                return render(request, 'licensing/send_invitation.html', {'form': form})

            validator = EmailValidator()
            for email in email_list:
                try:
                    validator(email)
                except ValidationError:
                    
                    messages.warning(request, f"Email tidak valid dilewati: {email}")
                    continue

                if Invitation.objects.filter(invitee_email=email, license=license, status__in=['pending', 'accepted']).exists():
                    messages.warning(request, f"Email {email} sudah diundang sebelumnya.")
                    continue

                invitation = Invitation.objects.create(
                    inviter=request.user,
                    invitee_email=email,
                    license=license,
                )

                accept_url = request.build_absolute_uri(
                    reverse('licensing:accept_invitation', kwargs={
                        'uidb64': urlsafe_base64_encode(str(invitation.id).encode()),
                        'token': invitation.token
                    })
                )
                html_message = render_to_string('licensing/invitation_email.html', {
                    'invitation': invitation,
                    'accept_url': accept_url,
                })
                subject = f"Undangan Kursus dari {request.user.username}"
                send_mail(subject, '', 'from@example.com', [email], html_message=html_message, fail_silently=True)
               
                messages.success(request, f"Undangan dikirim ke {email}.")

            return redirect('licensing:licens_dashboard')
    else:
        form = InvitationForm()

    return render(request, 'licensing/send_invitation.html', {'form': form})

def accept_invitation(request, uidb64, token):
    """Memproses penerimaan undangan oleh pengguna."""
    try:
        invitation_id = urlsafe_base64_decode(uidb64).decode()
        invitation = Invitation.objects.get(id=invitation_id, token=token)

        if invitation.is_expired():
            messages.error(request, "Undangan ini telah kadaluarsa.")
            return redirect('authentication:home')

        if invitation.status == 'accepted':
            messages.info(request, "Anda sudah menerima undangan ini.")
            return redirect('licensing:participant_dashboard')

        if request.user.is_authenticated:
            if invitation.license and not invitation.license.can_add_user():
                messages.error(request, "Lisensi ini telah mencapai batas maksimum pengguna.")
                return redirect('authentication:home')

            if invitation.license and invitation.license.users.contains(request.user):
                messages.info(request, "Anda sudah tergabung dalam lisensi ini.")
                return redirect('licensing:participant_dashboard')

            invitation.status = 'accepted'
            invitation.save()

            if invitation.license:
                try:
                    user = CustomUser.objects.get(email=invitation.invitee_email)
                except CustomUser.DoesNotExist:
                    user = CustomUser.objects.create(
                        email=invitation.invitee_email,
                        username=invitation.invitee_email.split('@')[0],
                        is_learner=True,
                    )
                    user.set_password("temporarypassword")
                    user.save()

                    token_generator = PasswordResetTokenGenerator()
                    reset_token = token_generator.make_token(user)
                    reset_url = request.build_absolute_uri(
                        reverse('authentication:password_reset_confirm', kwargs={
                            'uidb64': urlsafe_base64_encode(str(user.id).encode()),
                            'token': reset_token
                        })
                    )
                    subject = 'Atur Kata Sandi Anda'
                    message = f'Silakan atur kata sandi Anda menggunakan tautan berikut: {reset_url}'
                    send_mail(subject, message, 'from@example.com', [user.email], fail_silently=True)

                invitation.license.users.add(user)
                messages.success(request, f"Anda berhasil bergabung dalam kursus sebagai {user.username}!")

            return redirect('licensing:participant_dashboard')
        else:
            return redirect('authentication:login')

    except Invitation.DoesNotExist:
        messages.error(request, "Tautan undangan tidak valid.")
        return redirect('authentication:home')

@staff_member_required
def create_license(request):
    """View untuk Super Admin membuat lisensi."""
    if request.method == 'POST':
        name = request.POST.get('name')
        license_type = request.POST.get('license_type')
        subscription_type = request.POST.get('subscription_type')
        subscription_frequency = request.POST.get('subscription_frequency')
        max_users = request.POST.get('max_users', 20)
        user_id = request.POST.get('user_id')

        try:
            user = CustomUser.objects.get(id=user_id)
            user.is_subscription = True  # Set sebagai admin langganan (PT A)
            user.is_learner = False  # Pastikan bukan peserta
            user.save()
            license = License.objects.create(
                name=name,
                license_type=license_type,
                subscription_type=subscription_type,
                subscription_frequency=subscription_frequency,
                start_date=timezone.now().date(),
                expiry_date=timezone.now().date() + timedelta(days=365),
                max_users=max_users,
                status=True,
            )
            license.users.add(user)
            
            messages.success(request, f"Lisensi {name} berhasil dibuat untuk {user.username}.")
            return redirect('admin:licensing_license_changelist')
        except CustomUser.DoesNotExist:
           
            messages.error(request, "Pengguna tidak ditemukan.")
        except Exception as e:
            
            messages.error(request, f"Error saat membuat lisensi: {str(e)}")

    users = CustomUser.objects.all()
    return render(request, 'licensing/create_license.html', {'users': users})