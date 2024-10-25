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
from django.contrib.auth.decorators import login_required

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
@login_required
def courseAdd(request):
 
    if request.method == 'POST':
            
        form = CourseForm(request.POST)
        if form.is_valid():
            course = form.save(commit=False)
            course.author_id = request.user.id
            course.save()            
            return redirect('/course') 
    else:       
        form = CourseForm()
    context = {'form':form}    
    return render (request,'courses/course_add.html', context)
            
 
   
    
   
        
   

# Create your views here.
@login_required
def courseEdit(request, pk):
    cour = Course.objects.get(id=pk)

    if request.method == 'POST':
        form = CourseForm(request.POST, instance=cour)
        if form.is_valid():
            # update the existing `Band` in the database
            form.save()
            # redirect to the detail page of the `Band` we just updated
            return redirect('/course') 
    else:
        form = CourseForm(instance=cour)

    context = {'form':form}    
    return render (request,'courses/course_edit.html', context)