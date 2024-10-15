from django.shortcuts import render, redirect
from django.contrib.auth.models import User
from django.conf import settings
from .models import Partner
from django.contrib import messages
from django.contrib.auth.models import User
import os

def partnerView(request):
    if request.user.is_authenticated:
           partner_list = Partner.objects.all()
           context = {'partnerlist':partner_list}   

           return render (request,'partner/partner_view.html', context)
    else:
          
        return redirect ('/')

def partnerAdd(request):

    if request.user.is_staff == True:
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
                    return redirect('/list')
        
        user_list = User.objects.all()
        context = {'us':user_list}
        return render (request,'partner/partner_add.html', context)
    else:
        
        return redirect ('/')

# Create your views here.
def partnerEdit(request, pk):
    if request.user.is_authenticated:
        par = Partner.objects.get(id=pk)
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
            return redirect('/list')

        context = {'partner':par,'user':user_list}
        return render(request, 'partner/partner_edit.html', context)
    return redirect("/login/?next=%s" % request.path)