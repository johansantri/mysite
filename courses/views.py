from django.shortcuts import render

# Create your views here.
from django.shortcuts import render, redirect
from django.contrib.auth.models import User
from django.conf import settings
from .models import Course
from django.contrib import messages
from django.contrib.auth.models import User
import os

def courseView(request):
    if request.user.is_authenticated:
           course_list = Course.objects.all()
           context = {'courselist':course_list}   

           return render (request,'courses/course_view.html', context)
    else:
          
        return redirect ('/')

def courseAdd(request):

    if request.user.is_staff == True:
        if request.method == "POST":
                par = Course()
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
        return render (request,'courses/course_add.html', context)
    else:
        
        return redirect ('/')

# Create your views here.
def courseEdit(request, pk):
    par = Course.objects.get(id=pk)
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

    context = {'coures':par,'user':user_list}
    return render(request, 'courses/course_edit.html', context)