# licensing/views.py
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from .models import License
from django.utils import timezone

@login_required
def licens_dashboard(request):
    """Menampilkan dashboard lisensi pengguna yang sedang login."""
    # Ambil semua lisensi pengguna yang sedang login
    licenses = License.objects.filter(user=request.user)

    # Pisahkan lisensi yang kedaluwarsa dan yang masih aktif
    active_licenses = licenses.filter(status=True)
    expired_licenses = licenses.filter(status=False)

    # Menampilkan tanggal kedaluwarsa dan status kedaluwarsa untuk lisensi aktif
    approaching_expiry = active_licenses.filter(expiry_date__lte=timezone.now().date() + timezone.timedelta(days=7))

    return render(request, 'licensing/licens_dashboard.html', {
        'active_licenses': active_licenses,
        'expired_licenses': expired_licenses,
        'approaching_expiry': approaching_expiry,
    })
