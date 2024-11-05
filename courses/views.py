from django.shortcuts import render

# Create your views here.
from django.shortcuts import render, redirect,get_object_or_404
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
    if not request.user.is_superuser:
            if request.user.is_authenticated:
                    posts = Course.objects.filter(author_id=request.user.id)
                    count = Course.objects.all().count()

                    query = request.GET.get('q')
                    if query is not None and query !='':
                        posts=Course.objects.filter(Q(course_name__icontains=query) | Q(status_course__icontains=query),author_id=request.user.id).distinct() 
                        
                    count = posts.count()     
                    page = Paginator(posts,5)
                    page_list = request.GET.get('page')
                    page = page.get_page(page_list)

                    context= {'count': count, 'page':page}  

                    return render (request,'courses/course_view.html', context)
            else:
                
                return redirect ('/')
    #else        
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
    
@login_required
def courseAdd(request):
    if request.user.is_superuser:
        if request.method == 'POST':
        
            form = CourseForm(request.POST)
            if form.is_valid():
                course = form.save(commit=False)
                course.author_id = request.user.id
                course.save()  
                messages.success(request, 'Data berhasil disimpan!')          
                return redirect('/course') 
        else:       
            form = CourseForm()
        context = {'form':form}    
        return render (request,'courses/course_add.html', context)

    elif request.user.is_staff:
          if request.method == 'POST':
        
            form = CourseForm(request.POST)
            if form.is_valid():
                course = form.save(commit=False)
                course.author_id = request.user.id
                course.save()  
                messages.success(request, 'Data berhasil disimpan!')          
                return redirect('/course') 
          else:       
               form = CourseForm()
          context = {'form':form}    
          return render (request,'courses/course_add.html', context)
    else:
        messages.success(request, 'anda tidak dapat menambahkan course baru')          
        return redirect('/course') 
            
 
   
    
   
        
   

# Create your views here.
@login_required
def courseDetail(request, pk):
    if not request.user.is_superuser:
                cour = Course.objects.get(id=pk)
                cour = get_object_or_404(Course, id=pk, author_id=request.user.id)

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
                return render (request,'courses/course_detail.html', context)
     #else 
    cour = Course.objects.get(id=pk)
    cour = get_object_or_404(Course, id=pk)

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
    return render (request,'courses/course_detail.html', context)