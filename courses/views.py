from django.shortcuts import render

# Create your views here.
from django.shortcuts import render, redirect
from django.contrib.auth.models import User
from django.conf import settings
from .models import Course
from django.contrib import messages
from django.contrib.auth.models import User
import os
from .forms import CourseForm
from django.http import HttpResponse,JsonResponse

def courseView(request):
    if request.user.is_authenticated:
           course_list = Course.objects.all()
           context = {'courselist':course_list}   

           return render (request,'courses/course_view.html', context)
    else:
          
        return redirect ('/')

def courseAdd(request):
   
    if request.method == "POST":
          form = CourseForm(request.POST)

          if form.is_valid():
                redirect('/') 
    else:
        form = CourseForm()
    context = {'form':form}
     
   
    return render (request,'courses/course_add.html', context)
   
        
   

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