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
from django.contrib.admin.views.decorators import staff_member_required
from django.core.validators import EmailValidator
from django.core.exceptions import ValidationError
import logging
from datetime import timedelta
from django.contrib.auth.tokens import PasswordResetTokenGenerator
from courses.models import Course, Enrollment

logger = logging.getLogger(__name__)


@login_required
def licens_dashboard(request):
    """Menampilkan dashboard lisensi untuk PT A (admin) yang mengelola undangan dan melihat peserta kursus."""
    if not request.user.is_subscription:
        logger.warning(f"Pengalihan ke participant_dashboard untuk {request.user.email} karena bukan admin langganan (is_subscription=False)")
        messages.error(request, "Akses ditolak. Hanya pengguna dengan status langganan yang dapat mengakses dashboard ini.")
        return redirect('licensing:participant_dashboard')

    logger.info(f"Pengguna {request.user.email} mengakses licens_dashboard (is_subscription=True)")
    invitations = Invitation.objects.filter(inviter=request.user)

    # Filter berdasarkan status
    status = request.GET.get('status')
    if status:
        invitations = invitations.filter(status=status)

    # Pencarian berdasarkan invitee_email
    search_query = request.GET.get('search')
    if search_query:
        invitations = invitations.filter(invitee_email__icontains=search_query)

    # Urutkan berdasarkan tanggal undangan
    invitations = invitations.order_by('-invitation_date')

    # Paginasi untuk undangan
    paginator = Paginator(invitations, 10)
    page_number = request.GET.get('page')
    invitations_page = paginator.get_page(page_number)

    # Ambil semua lisensi yang terkait dengan pengguna
    licenses = License.objects.filter(users=request.user)

    # Hitung statistik undangan
    invitation_stats = {
        'pending': invitations.filter(status='pending').count(),
        'accepted': invitations.filter(status='accepted').count(),
        'expired': invitations.filter(status='expired').count(),
    }

    # Ambil semua kursus yang diikuti oleh peserta dalam lisensi
    license_course_data = []
    for license in licenses:
        # Ambil semua peserta dalam lisensi (kecuali PT A sendiri)
        participants = license.users.exclude(id=request.user.id)
        # Ambil semua enrollments untuk peserta ini
        enrollments = Enrollment.objects.filter(user__in=participants)
        # Kelompokkan enrollments berdasarkan kursus
        courses = Course.objects.filter(enrollments__in=enrollments).distinct()
        course_data = []
        for course in courses:
            course_enrollments = enrollments.filter(course=course)
            course_data.append({
                'course': course,
                'enrollments': course_enrollments,
                'enrollment_count': course_enrollments.count(),
            })
        license_course_data.append({
            'license': license,
            'courses': course_data,
        })

    context = {
        'invitations': invitations_page,
        'licenses': licenses,
        'status': status,
        'search_query': search_query,
        'invitation_stats': invitation_stats,
        'license_course_data': license_course_data,
    }

    return render(request, 'licensing/licens_dashboard.html', context)

@login_required
def participant_dashboard(request):
    """Menampilkan dashboard khusus untuk peserta."""
    licenses = License.objects.filter(users=request.user)
    context = {
        'licenses': licenses,
    }
    return render(request, 'licensing/participant_dashboard.html', context)

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
    if not request.user.is_partner:
        return redirect('licensing:participant_dashboard')

    if request.method == 'POST':
        form = InvitationForm(request.POST)
        if form.is_valid():
            invitee_emails = form.cleaned_data['invitee_emails']
            email_list = [email.strip() for email in invitee_emails.replace('\n', ',').split(',') if email.strip()]

            if not email_list:
                messages.error(request, "Harap masukkan setidaknya satu email yang valid.")
                return render(request, 'licensing/send_invitation.html', {'form': form})

            logger.info(f"Memeriksa lisensi untuk pengguna: {request.user.username} (ID: {request.user.id})")
            license = License.objects.filter(users=request.user, status=True).order_by('-start_date').first()
            if not license:
                logger.error(f"Tidak ditemukan lisensi aktif untuk pengguna: {request.user.username} (ID: {request.user.id})")
                messages.error(request, "Tidak ditemukan lisensi aktif untuk akun Anda. Silakan hubungi Super Admin untuk membuat atau mengaktifkan lisensi.")
                return redirect('licensing:licens_dashboard')

            logger.info(f"Lisensi ditemukan: {license.name} (ID: {license.id}, Status: {license.status}, Pengguna: {license.users.count()}/{license.max_users})")

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
                    logger.warning(f"Email tidak valid dilewati: {email}")
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
                logger.info(f"Pengguna {request.user.username} mengirim undangan ke {email}")
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
            logger.info(f"Lisensi {license.name} (ID: {license.id}) dibuat untuk pengguna {user.username} (ID: {user.id}) dengan is_subscription=True")
            messages.success(request, f"Lisensi {name} berhasil dibuat untuk {user.username}.")
            return redirect('admin:licensing_license_changelist')
        except CustomUser.DoesNotExist:
            logger.error(f"Pengguna dengan ID {user_id} tidak ditemukan saat membuat lisensi.")
            messages.error(request, "Pengguna tidak ditemukan.")
        except Exception as e:
            logger.error(f"Error saat membuat lisensi: {str(e)}")
            messages.error(request, f"Error saat membuat lisensi: {str(e)}")

    users = CustomUser.objects.all()
    return render(request, 'licensing/create_license.html', {'users': users})