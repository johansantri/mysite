from django.shortcuts import render, get_object_or_404, redirect
from courses.models import Partner
from authentication.models import Universiti
from courses.forms import PartnerFormUpdate
from django.contrib.auth.decorators import login_required
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