from django.shortcuts import render, redirect, get_object_or_404
from django.core.paginator import Paginator
from django.db.models import Q

from django.contrib.auth.decorators import login_required
from .forms import CourseForm, PartnerForm

from .models import Course, Partner

def courseView(request):
    if not request.user.is_authenticated:
        return redirect('/')

    posts = Course.objects.all() if request.user.is_superuser else Course.objects.filter(author_id=request.user.id)
    posts = filter_courses_by_query(request, posts)
    page = paginate_courses(request, posts)

    context = {'count': posts.count(), 'page': page}
    return render(request, 'courses/course_view.html', context)

def filter_courses_by_query(request, posts):
    """Filter courses based on search query."""
    query = request.GET.get('q')
    if query is not None and query !='':
        posts = posts.filter(Q(course_name__icontains=query) | Q(status_course__icontains=query)).distinct()
    return posts

def paginate_courses(request, posts):
    """Paginate the course list."""
    paginator = Paginator(posts, 5)
    page_number = request.GET.get('page')
    return paginator.get_page(page_number)

def course_create_view(request):
    if request.method == 'POST':
        form = CourseForm(request.POST, user=request.user)  # Pass the logged-in user to the form
        if form.is_valid():
            form = form.save(commit=False)
            form.author_id = request.user.id
            form.save()  # Save the course with the selected partner
            return redirect('/course')  # Redirect to a course list page or success page
    else:
        form = CourseForm(user=request.user)  # Pass the logged-in user to the form

    return render(request, 'courses/course_add.html', {'form': form})





#add partner

def partnerView(request):
    if not request.user.is_authenticated:
        return redirect('/')

    posts = Partner.objects.all() if request.user.is_superuser else Partner.objects.filter(user_id=request.user.id)
    
    posts = filter_partner_by_query(request, posts)
    page = paginate_partner(request, posts)

    context = {'count': posts.count(), 'page': page}
    return render(request, 'partner/partner_view.html', context)

def filter_partner_by_query(request, posts):
    """Filter partner based on search query."""
    query = request.GET.get('q')
    if query is not None and query !='':
        posts = posts.filter(Q(name__icontains=query) | Q(abbreviation__icontains=query)).distinct()
    return posts

def paginate_partner(request, posts):
    """Paginate the course list."""
    paginator = Paginator(posts, 5)
    page_number = request.GET.get('page')
    return paginator.get_page(page_number)

def partner_create_view(request):
    if not request.user.is_superuser:
     return redirect('/')

    if request.method == 'POST':
        form = PartnerForm(request.POST)  # Pass the logged-in user to the form
        if form.is_valid():
            form = form.save(commit=False)
            form.author_id = request.user.id
            form.save()  # Save the course with the selected partner
            return redirect('/course')  # Redirect to a course list page or success page
    else:
        form = PartnerForm()  # Pass the logged-in user to the form

    return render(request, 'partner/partner_add.html', {'form': form})