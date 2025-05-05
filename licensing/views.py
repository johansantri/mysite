# licensing/views.py
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.core.mail import send_mail
from django.utils import timezone
from .models import Invitation, License
from .forms import InvitationForm,InvitationSearchForm
from django.contrib import messages
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.contrib.sites.shortcuts import get_current_site
from django.template.loader import render_to_string


# licensing/views.py
@login_required
def licens_dashboard(request):
    """Menampilkan dashboard lisensi pengguna yang sedang login dan mengelola undangan."""
    
    # Ambil semua lisensi pengguna yang sedang login
    licenses = License.objects.filter(user=request.user)

    # Pisahkan lisensi yang kedaluwarsa dan yang masih aktif
    active_licenses = licenses.filter(status=True)
    expired_licenses = licenses.filter(status=False)

    # Menampilkan tanggal kedaluwarsa dan status kedaluwarsa untuk lisensi aktif
    approaching_expiry = active_licenses.filter(expiry_date__lte=timezone.now().date() + timezone.timedelta(days=7))

    # Mengambil form pencarian
    search_form = InvitationSearchForm(request.GET)
    
    # Filter undangan berdasarkan pencarian
    if search_form.is_valid():
        search_email = search_form.cleaned_data.get('search_email')
        status = search_form.cleaned_data.get('status')
        
        invitations = Invitation.objects.filter(inviter=request.user)
        
        # Menambahkan filter untuk email dan status
        if search_email:
            invitations = invitations.filter(invitee_email__icontains=search_email)
        if status:
            invitations = invitations.filter(status=status)
    else:
        invitations = Invitation.objects.filter(inviter=request.user)
    
    # Mengambil undangan aktif, diterima, dan kedaluwarsa
    active_invitations = invitations.filter(status='Pending')
    accepted_invitations = invitations.filter(status='Accepted')
    expired_invitations = invitations.filter(status='Expired')

    return render(request, 'licensing/licens_dashboard.html', {
        'active_licenses': active_licenses,
        'expired_licenses': expired_licenses,
        'approaching_expiry': approaching_expiry,
        'active_invitations': active_invitations,
        'accepted_invitations': accepted_invitations,
        'expired_invitations': expired_invitations,
        'search_form': search_form,
    })


@login_required
def delete_license(request, license_id):
    """Menghapus lisensi yang sudah diterima oleh peserta"""
    try:
        license = License.objects.get(id=license_id, user=request.user)
        license.delete()
        messages.success(request, 'License deleted successfully.')
    except License.DoesNotExist:
        messages.error(request, 'License not found or you do not have permission to delete it.')
    return redirect('licensing:licens_dashboard')


@login_required
def resend_invitation(request, invitation_id):
    """Mengirim ulang undangan yang belum diterima"""
    try:
        invitation = Invitation.objects.get(id=invitation_id, inviter=request.user)
        # Logika untuk mengirim ulang email atau membuat ulang undangan
        invitation.send_invitation_email()
        messages.success(request, 'Invitation resent successfully.')
    except Invitation.DoesNotExist:
        messages.error(request, 'Invitation not found or you do not have permission to resend it.')
    return redirect('licensing:licens_dashboard')



@login_required
def send_invitation(request):
    """Membuat dan mengirim undangan ke peserta (satu atau lebih email)."""
    if request.method == 'POST':
        form = InvitationForm(request.POST)
        if form.is_valid():
            # Ambil daftar email peserta yang dipisahkan oleh spasi atau baris baru
            invitee_emails = form.cleaned_data['invitee_emails']

            # Tentukan lisensi default untuk PT A, bisa disesuaikan sesuai kebutuhan
            license = License.objects.filter(user=request.user, status=True).first()  # Lisensi default

            if not license:
                messages.error(request, "You don't have an active license.")
                return redirect('licensing:licens_dashboard')

            # Proses setiap email yang dimasukkan
            for invitee_email in invitee_emails:
                invitation = Invitation(
                    inviter=request.user,  # Pengundang (PT A)
                    invitee_email=invitee_email,
                    license=license,  # Lisensi yang ditetapkan
                    status='pending',
                    expiry_date=timezone.now() + timezone.timedelta(days=7)
                )
                invitation.save()  # This will automatically generate the token

                # Membuat URL untuk menerima undangan
                token = invitation.token  # Token dari undangan
                uidb64 = urlsafe_base64_encode(str(invitation.id).encode())  # Enkode ID undangan untuk link yang aman
                domain = request.get_host()  # Mengambil domain dari request
                link = f'https://{domain}/accept-invitation/{uidb64}/{token}/'

                # Kirim email pemberitahuan undangan ke peserta
                subject = 'You have been invited to join the course'
                message = f'You have been invited to join the course. Please click the link below to accept or reject the invitation:\n\n{link}'
                send_mail(
                    subject,
                    message,
                    'indonesialokal@gmail.com',  # Gantilah dengan email yang valid
                    [invitee_email],
                    fail_silently=False,
                )

            messages.success(request, 'Invitation(s) sent successfully!')
            return redirect('licensing:licens_dashboard')

    else:
        form = InvitationForm()

    return render(request, 'licensing/send_invitation.html', {'form': form})


def accept_invitation(request, uidb64, token):
    try:
        # Dekode ID undangan dari URL
        invitation_id = urlsafe_base64_decode(uidb64).decode()
        invitation = Invitation.objects.get(id=invitation_id, token=token)

        # Periksa apakah undangan sudah kadaluarsa
        if invitation.is_expired():
            messages.error(request, "This invitation has expired.")
            return redirect('authentication:home')  # Redirect ke halaman lain jika sudah kadaluarsa

        # Periksa apakah undangan sudah diterima
        if invitation.status == 'accepted':
            messages.info(request, "You have already accepted this invitation.")
            return redirect('authentication:home')

        # Jika peserta sudah login
        if request.user.is_authenticated:
            # Tandai undangan sebagai diterima
            invitation.status = 'accepted'
            invitation.save()

            # Jika undangan memiliki lisensi terkait, daftarkan pengguna untuk lisensi tersebut
            if invitation.license:
                invitation.license.user.add(request.user)  # Daftarkan pengguna pada lisensi
                messages.success(request, "You have successfully joined the course!")

            return redirect('licensing:licens_dashboard')

        # Jika peserta belum login, arahkan ke halaman login atau registrasi
        else:
            return redirect('authentication:login')  # Ganti dengan URL login Anda

    except Invitation.DoesNotExist:
        messages.error(request, "Invalid invitation link.")
        return redirect('authentication:home')