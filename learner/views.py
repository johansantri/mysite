from django.shortcuts import render
from django.contrib.auth.models import User
from django.core.paginator import Paginator, EmptyPage,PageNotAnInteger
from django.db.models import Count
from django.db.models import Q

# Create your views here.
def learnerView(request):
    posts = User.objects.all()
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