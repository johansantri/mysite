from django.shortcuts import render, redirect, get_object_or_404
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.db.models import Q

from django.contrib.auth.decorators import login_required
from .forms import CourseForm, PartnerForm
from django.http import JsonResponse
from .models import Course, Partner, Section


def courseView(request):
    # Check if the user is authenticated
    if not request.user.is_authenticated:
        return redirect('/')

    # Determine which courses to display
    if request.user.is_superuser:
        courses = Course.objects.all()
    elif hasattr(request.user, 'is_partner') and request.user.is_partner:
        courses = Course.objects.filter(author_id=request.user.id)
    else:
        courses = Course.objects.none()  # Return an empty QuerySet for unauthorized users

    search_query = request.GET.get('search', '').strip()
    if search_query:
        courses = courses.filter(course_name__icontains=search_query)

    # Fetch only necessary fields
    courses = courses.values('id', 'course_name', 'course_number')

    # Get the page number from the request
    page_number = request.GET.get('page', 1)
    try:
        page_number = int(page_number)
    except ValueError:
        page_number = 1

    # Paginate the courses
    paginator = Paginator(courses, 5)  # 5 courses per page
    try:
        page_obj = paginator.page(page_number)
    except PageNotAnInteger:
        page_obj = paginator.page(1)
    except EmptyPage:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({"error": "Page not found"}, status=404)
        return redirect('/')  # Redirect for non-Ajax requests

    # Prepare paginated data to return as JSON
    data = {
        "items": list(page_obj),  # Convert page object to a list of dictionaries
        "count": paginator.count,
        "page_number": page_obj.number,
        "num_pages": paginator.num_pages,
        "has_next": page_obj.has_next(),
        "has_previous": page_obj.has_previous(),
    }

    # If it's an Ajax request, return JSON response
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse(data)

    # Render the page normally for non-Ajax requests
    return render(request, 'courses/course_view.html', {'page_obj': page_obj,'search_query': search_query})

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
            return redirect('/courses')  # Redirect to a course list page or success page
    else:
        form = CourseForm(user=request.user)  # Pass the logged-in user to the form

    return render(request, 'courses/course_add.html', {'form': form})


def studio(request, id):
    course = get_object_or_404(Course, id=id)
    sections = Section.objects.filter(parent=None, courses_id=course.id)  # Make sure `courses_id` matches your field in Section model

    # Prepare data
    data = {
        'course': {
            'id': course.id,
            'name': course.course_name,
            'number': course.course_number,
            'level': course.level,
            'category': course.category.name,
            'org': course.org_partner.name,
            'status': course.status_course,
            'created_at': course.created_at,
            'edited_on': course.edited_on
        },
        'sections': [
            {
                'id': section.id,
                'title': section.title,
                'slug': section.slug,
                'created_at': section.created_at
            } for section in sections
        ]
    }

    # Return JSON response
    return JsonResponse(data,safe=False)
    #return render(request, 'courses/course_detail.html', context)


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