from django.shortcuts import render, redirect, get_object_or_404
from django.core.paginator import Paginator
from django.db.models import Q
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from .models import Course
from .forms import CourseForm

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

@login_required
def courseAdd(request):
    if request.user.is_superuser or request.user.is_staff:
        return handle_course_form(request)
    messages.error(request, 'You do not have permission to add a new course.')
    return redirect('/course')

def handle_course_form(request, instance=None):
    """Handle course form processing for add and edit views."""
    form = CourseForm(request.POST or None, instance=instance)
    if request.method == 'POST' and form.is_valid():
        course = form.save(commit=False)
        course.author_id = request.user.id
        course.save()
        messages.success(request, 'Course saved successfully!')
        return redirect('/course')
    return render(request, 'courses/course_add.html', {'form': form})

@login_required
def courseDetail(request, pk):
    course = get_object_or_404(Course, id=pk) if request.user.is_superuser else get_object_or_404(Course, id=pk, author_id=request.user.id)
    return handle_course_form(request, instance=course)
