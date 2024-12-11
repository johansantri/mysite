from django.shortcuts import render, redirect, get_object_or_404
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.db.models import Q
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required
from .forms import CourseForm, PartnerForm, SectionForm
from django.http import JsonResponse
from .models import Course, Partner, Section


#add section
@csrf_exempt
def create_section(request):
    if request.method == "POST":
        form = SectionForm(request.POST)
        if form.is_valid():
            form.save()
            return JsonResponse({'status': 'success', 'message': 'Section created!'})
        else:
            return JsonResponse({'status': 'error', 'message': 'Form is not valid'})
    return JsonResponse({'status': 'error', 'message': 'Invalid request method'})

# Delete section
@csrf_exempt
def delete_section(request, pk):
    item = get_object_or_404(Section, pk=pk)
    item.delete()
    return JsonResponse({'status': 'success', 'message': 'section deleted!'})

# Update Section
@csrf_exempt
def update_section(request, pk):
    item = get_object_or_404(Section, pk=pk)
    if request.method == "POST":
        form = SectionForm(request.POST, instance=item)
        if form.is_valid():
            form.save()
            return JsonResponse({'status': 'success', 'message': 'Item updated!'})
        else:
            # Log or return specific form errors for debugging
            return JsonResponse({'status': 'error', 'message': 'Form is not valid', 'errors': form.errors})
    return JsonResponse({'status': 'error', 'message': 'Invalid request method'})

def courseView(request):
    # Check if the user is authenticated
    if not request.user.is_authenticated:
        return redirect('/')

    # Determine which courses to display
    if request.user.is_superuser:
        courses = Course.objects.all()
    #partner
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
    return render(request, 'courses/course_view.html')

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
    if not request.user.is_partner:
        return redirect('/')

    # Assuming `id` refers to the course id you're trying to filter
    course = Course.objects.filter(id=id, author_id=request.user.id).first()
    
    if not course:
        return redirect('/courses')  # If no course is found, redirect to the homepage

    # Get sections related to the course
    section = Section.objects.filter(parent=None, courses_id=course.id)

    # Render the page normally for non-Ajax requests
    return render(request, 'courses/course_detail.html', {'course': course, 'section': section})



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

