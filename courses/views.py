from django.shortcuts import render

# Create your views here.
from django.shortcuts import render, redirect
from django.contrib.auth.models import User
from django.conf import settings
from .models import Course
from django.core.paginator import Paginator, EmptyPage,PageNotAnInteger
from django.db.models import Q
from django.contrib import messages
from django.contrib.auth.models import User
import os
from .forms import CourseForm
from django.http import HttpResponse,JsonResponse

def courseView(request):
    if request.user.is_authenticated:
            posts = Course.objects.all()
            count = Course.objects.all().count()

            query = request.GET.get('q')
            if query is not None and query !='':
                posts=Course.objects.filter(Q(course_name__icontains=query) | Q(status_course__icontains=query)).distinct()  
            count = posts.count()     
            page = Paginator(posts,5)
            page_list = request.GET.get('page')
            page = page.get_page(page_list)

            context= {'count': count, 'page':page}  

            return render (request,'courses/course_view.html', context)
    else:
          
        return redirect ('/')

def courseAdd(request):
    if request.user.is_authenticated:
        context = {}   
        form = CourseForm(request.POST or None)
        if form.is_valid():
            form.save()               
            return redirect('/course')    
        form = CourseForm()
        context = {'form':form}    
        return render (request,'courses/course_add.html', context)
    else:
        return redirect('login')
    
   
        
   

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