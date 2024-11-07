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
from django.contrib.auth.forms import UserCreationForm
from authentication.forms import UserRegistrationForm
from django.http import HttpResponseForbidden

@login_required
def partnerView(request):
    if not request.user.is_superuser:
    
           partner_list = Partner.objects.filter(e_mail_id=request.user.id)
           context = {'partnerlist':partner_list}   

           return render (request,'partner/partner_view.html', context)
           #return redirect ('/')
    else:
           partner_list = Partner.objects.all()
           context = {'partnerlist':partner_list}   

           return render (request,'partner/partner_view.html', context)
          
        #return redirect ('/')
    

@login_required
def partnerAdd(request):

    if request.user.is_superuser:
        if request.method == "POST":
                par = Partner()
                par.partner_name = request.POST.get('partner_name')
                par.abbreviation = request.POST.get('partner_abbreviation')
                par.e_mail_id = request.POST.get('partner_email')
                par.phone = request.POST.get('partner_phone')
                par.address = request.POST.get('partner_address')
                par.tax = request.POST.get('partner_tax')
                par.status = request.POST.get('partner_status')
                #par.partner_logo = request.POST.get('partner_logo')
                par.checks = request.POST.get('partner_check')

                if len(request.FILES) != 0:
                    par.logo = request.FILES['partner_logo']
                    par.save()
                    messages.success(request, "PARTNER ADD SUCCESSFULLY")
                    return redirect('/partners')
        
        user_list = User.objects.all()
        context = {'us':user_list}
        return render (request,'partner/partner_add.html', context)
    else:
        
        return redirect ('/')

# Create your views here.

def partnerEdit(request, pk):
  
        if request.user.is_superuser:
            par = Partner.objects.get(id=pk)
            par =get_object_or_404(Partner,id=pk)
            
            user_list = User.objects.all()
            if request.method == "POST":
                if len(request.FILES) != 0:
                    if len(par.logo) > 0:
                        os.remove(par.logo.path)
                            #prod.image = request.FILES['image']
                    par.logo = request.FILES['partner_logo']
                par.partner_name = request.POST.get('partner_name')
                par.abbreviation = request.POST.get('partner_abbreviation')
                par.e_mail_id = request.POST.get('partner_email')
                par.phone = request.POST.get('partner_phone')
                par.address = request.POST.get('partner_address')
                par.tax = request.POST.get('partner_tax')
                par.status = request.POST.get('partner_status')
                
                par.checks = request.POST.get('partner_check')
                par.save()
                messages.success(request, "Partner Updated Successfully")
                return redirect('/partners')

            context = {'partner':par,'tes':user_list}
            return render(request, 'partner/partner_edit.html', context)
        elif request.user.is_staff:
                #par = Partner.objects.get(id=pk)
                par =get_object_or_404(Partner,id=pk,e_mail_id=request.user.id)
               
                
               # user_list = User.objects.all()
                if request.method == "POST":
                    if len(request.FILES) != 0:
                        if len(par.logo) > 0:
                            os.remove(par.logo.path)
                                #prod.image = request.FILES['image']
                        par.logo = request.FILES['partner_logo']
                    par.partner_name = request.POST.get('partner_name')
                    par.abbreviation = request.POST.get('partner_abbreviation')
                    par.e_mail_id = request.POST.get('partner_email')
                    par.phone = request.POST.get('partner_phone')
                    par.address = request.POST.get('partner_address')
                    par.tax = request.POST.get('partner_tax')
                    par.status = request.POST.get('partner_status')
                    
                    par.checks = request.POST.get('partner_check')
                    par.save()
                    messages.success(request, "Partner Updated Successfully")
                    return redirect('/partners')

                context = {'partner':par}
                return render(request, 'partner/partner_edit.html', context)
        
        return redirect('login')



@login_required
def invite_user(request):
    if request.method == 'POST':
        email = request.POST.get('email')
        # Check if an invitation to this email already exists
        if Invitation.objects.filter(email=email).exists():
            messages.error(request, "An invitation has already been sent to this email.")
        else:
            # Create a new invitation
            invitation = Invitation.objects.create(email=email, invited_by=request.user)
            # Send an email to the invited user with a signup link
            signup_url = request.build_absolute_uri(f'/accept-invite/{invitation.token}/')
            send_mail(
                'You have been invited to partner ICE institute!',
                f'You have been invited to join our platform. Click the link to sign up: {signup_url}',
                'from@example.com',
                [email],
            )
            messages.success(request, f"Invitation sent to {email}!")
            return redirect('/invite')
    inv = Invitation.objects.all()
    
    return render(request, 'partner/invite_user.html',{'inv': inv})


def accept_invitation(request, token):
    invitation = get_object_or_404(Invitation, token=token)
    
    if invitation.accepted:
        return HttpResponseForbidden("This invitation has already been used.")
        
    
    if request.method == 'POST':
        form = UserRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()  # Create a new user
            # Mark the invitation as accepted
            invitation.accepted = True
            invitation.save()
            # Optionally, link the newly created user to the invitation (if needed)
            return redirect('login')  # Redirect to login or other page after successful signup
    else:
        form = UserRegistrationForm()

    return render(request, 'authentication/register.html', {'form': form})