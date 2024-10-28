from django.shortcuts import render, redirect, redirect,get_object_or_404
from django.contrib.auth.models import User
from django.core.paginator import Paginator, EmptyPage,PageNotAnInteger
from django.db.models import Count
from django.db.models import Q
import os
from .forms import LearnerForm

# Create your views here.
def learnerView(request):
    if not request.user.is_superuser:
            posts = User.objects.filter(id=request.user.id)
            #posts = get_object_or_404(User, id=request.user.id)
            count = User.objects.all().count()
            
            query = request.GET.get('q')
            if query is not None and query !='':
                posts=User.objects.filter(Q(email__icontains=query) | Q(username__icontains=query)).distinct()  
                count = posts.count()     
            page = Paginator(posts,10)
            page_list = request.GET.get('page')
            page = page.get_page(page_list)
            
            context= {'count': count, 'page':page}

            return render(request,'learner/alluser.html',context)
    
    posts = User.objects.all()
    #posts = get_object_or_404(User, id=request.user.id)
    count = User.objects.all().count()
    
    query = request.GET.get('q')
    if query is not None and query !='':
        posts=User.objects.filter(Q(email__icontains=query) | Q(username__icontains=query)).distinct()  
        count = posts.count()     
    page = Paginator(posts,10)
    page_list = request.GET.get('page')
    page = page.get_page(page_list)
    
    context= {'count': count, 'page':page}

    return render(request,'learner/alluser.html',context)


def learnerEdit(request, pk):
    cour = User.objects.get(id=pk)
    cour = get_object_or_404(User, id=request.user.pk)

    if request.method == 'POST':
        form = LearnerForm(request.POST, instance=cour)
        if form.is_valid():
            # update the existing `Band` in the database
            form.save()
            # redirect to the detail page of the `Band` we just updated
            return redirect('/learner') 
    else:
        form = LearnerForm(instance=cour)

    context = {'form':form}    
    return render (request,'learner/learner_detail.html', context)