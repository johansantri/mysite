from django.shortcuts import render, redirect,get_object_or_404
from django.contrib.auth.models import User
from django.core.mail import send_mail
from django.conf import settings
from .models import Partner,Invitation
from django.contrib import messages
from django.contrib.auth.models import User
import os
from django.contrib.auth.decorators import login_required
from django.contrib import messages

from authentication.forms import UserRegistrationForm
from django.http import HttpResponseForbidden
from django.core.paginator import Paginator
from django.db.models import Q

@login_required
def partnerView(request):
    if not request.user.is_superuser:
            posts = Partner.objects.filter(id=request.user.id)
            #posts = get_object_or_404(User, id=request.user.id)
            count = Partner.objects.filter(id=request.user.id).count()
            
            query = request.GET.get('q')
            if query is not None and query !='':
                posts=User.objects.filter(Q(partner_name__icontains=query) | Q(abbreviation__icontains=query)).distinct().filter(id=request.user.id)  
                count = posts.count()     
            page = Paginator(posts,10)
            page_list = request.GET.get('page')
            page = page.get_page(page_list)
            
            context= {'count': count, 'page':page}

            return render(request,'learner/alluser.html',context)
        
    posts = Partner.objects.all()
    #posts = get_object_or_404(User, id=request.user.id)
    count = Partner.objects.all().count()
    
    query = request.GET.get('q')
    if query is not None and query !='':
        posts=Partner.objects.filter(Q(partner_name__icontains=query) | Q(abbreviation__icontains=query)).distinct()  
        count = posts.count()     
    page = Paginator(posts,10)
    page_list = request.GET.get('page')
    page = page.get_page(page_list)
    
    context= {'count': count, 'page':page}

    return render(request,'partner/partner_view.html',context)
    


@login_required
def partnerAdd(request):
    if not request.user.is_superuser:
        return redirect('/')

    if request.method == "POST":
        par = create_partner_from_request(request)
        if len(request.FILES) != 0:
            par.logo = request.FILES['partner_logo']
        par.save()
        messages.success(request, "PARTNER ADDED SUCCESSFULLY")
        return redirect('/partners')
    
    user_list = User.objects.all()
    context = {'us': user_list}
    return render(request, 'partner/partner_add.html', context)

def create_partner_from_request(request):
    """Helper function to create a Partner object from POST data."""
    return Partner(
        partner_name=request.POST.get('partner_name'),
        abbreviation=request.POST.get('partner_abbreviation'),
        e_mail_id=request.POST.get('partner_email'),
        phone=request.POST.get('partner_phone'),
        address=request.POST.get('partner_address'),
        tax=request.POST.get('partner_tax'),
        status=request.POST.get('partner_status'),
        checks=request.POST.get('partner_check')
    )

# update

def partnerEdit(request, pk):
    partner = get_partner_by_role(request.user, pk)
    if not partner:
        return redirect('login')

    if request.method == "POST":
        update_partner_from_request(request, partner)
        if len(request.FILES) != 0:
            update_partner_logo(request, partner)
        partner.save()
        messages.success(request, "Partner Updated Successfully")
        return redirect('/partners')

    user_list = User.objects.all() if request.user.is_superuser else None
    context = {'partner': partner, 'tes': user_list}
    return render(request, 'partner/partner_edit.html', context)

def get_partner_by_role(user, pk):
    """Retrieve the partner based on user role."""
    if user.is_superuser:
        return get_object_or_404(Partner, id=pk)
    elif user.is_staff:
        return get_object_or_404(Partner, id=pk, e_mail_id=user.id)
    return None

def update_partner_from_request(request, partner):
    """Update partner fields from POST data."""
    partner.partner_name = request.POST.get('partner_name')
    partner.abbreviation = request.POST.get('partner_abbreviation')
    partner.e_mail_id = request.POST.get('partner_email')
    partner.phone = request.POST.get('partner_phone')
    partner.address = request.POST.get('partner_address')
    partner.tax = request.POST.get('partner_tax')
    partner.status = request.POST.get('partner_status')
    partner.checks = request.POST.get('partner_check')

def update_partner_logo(request, partner):
    """Handle partner logo update."""
    if partner.logo and os.path.exists(partner.logo.path):
        os.remove(partner.logo.path)
    partner.logo = request.FILES['partner_logo']



@login_required
def invite_user(request):
    if request.method == 'POST':
        email = request.POST.get('email')
        
        if invitation_exists(email):
            messages.error(request, "An invitation has already been sent to this email.")
        else:
            send_invitation(request, email)
            messages.success(request, f"Invitation sent to {email}!")
            return redirect('/invite')
    
    invitations = Invitation.objects.all()
    return render(request, 'partner/invite_user.html', {'inv': invitations})

def invitation_exists(email):
    """Check if an invitation to this email already exists."""
    return Invitation.objects.filter(email=email).exists()

def send_invitation(request, email):
    """Create an invitation and send an email to the invited user."""
    invitation = Invitation.objects.create(email=email, invited_by=request.user)
    signup_url = request.build_absolute_uri(f'/accept-invite/{invitation.token}/')
    send_mail(
        'You have been invited to partner ICE institute!',
        f'You have been invited to join our platform. Click the link to sign up: {signup_url}',
        'from@example.com',
        [email],
    )


def accept_invitation(request, token):
    invitation = get_object_or_404(Invitation, token=token)

    if invitation.accepted:
        return HttpResponseForbidden("This invitation has already been used.")

    if request.method == 'POST':
        form = UserRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            mark_invitation_as_accepted(invitation)
            return redirect('login')
    else:
        form = UserRegistrationForm()

    return render(request, 'authentication/register.html', {'form': form})

def mark_invitation_as_accepted(invitation):
    """Mark the invitation as accepted."""
    invitation.accepted = True
    invitation.save()