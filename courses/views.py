from django.shortcuts import render, redirect, get_object_or_404
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.db.models import Q
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required
from .forms import CourseForm, PartnerForm, SectionForm, ProfilForm
from django.http import JsonResponse
from .models import Course, Partner, Section
from django.contrib.auth.models import User
from django.template.loader import render_to_string
from django.views.decorators.cache import cache_page
from django.urls import reverse



#coruse profile
@csrf_exempt  # Be cautious with this decorator; it's better to avoid using it if unnecessary
def course_profile(request, id):
    # Get the course based on the user's role
    if request.user.is_superuser:
        course = Course.objects.filter(id=id).first()
    else:
        course = Course.objects.filter(id=id, author_id=request.user.id).first()

    # If no course is found, redirect to the courses list
    if not course:
        return redirect('/courses')

    # Handle POST request to update course data
    if request.method == 'POST':
        form = ProfilForm(request.POST,request.FILES, instance=course)
        if form.is_valid():
            form.save()  # Save the updated course data
            
            #print(reverse('course_profile', kwargs={'id': course.id}))
            return redirect('courses:course_profile', id=course.id)  # Redirect back to the updated course profile
    else:
        form = ProfilForm(instance=course)  # For GET requests, display the form with existing course data

    return render(request, 'courses/course_profile.html', {'course': course, 'form': form})
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
    courses = courses.order_by('-id')  # To order by ascending order
    # Fetch only necessary fields
    courses = courses.values('id', 'course_name', 'course_number')

    # Get the page number from the request
    page_number = request.GET.get('page', 1)
    try:
        page_number = int(page_number)
    except ValueError:
        page_number = 1

    # Paginate the courses
    paginator = Paginator(courses, 10)  # 5 courses per page
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
#create course
def course_create_view(request):
    if request.user.is_partner or request.user.is_superuser:
        if request.method == 'POST':
            form = CourseForm(request.POST, user=request.user)  # Pass the logged-in user to the form
            if form.is_valid():
                form = form.save(commit=False)
                form.author_id = request.user.id
                form.save()  # Save the course with the selected partner
                return redirect('/courses')  # Redirect to a course list page or success page
        else:
            form = CourseForm(user=request.user)  # Pass the logged-in user to the form
    else :
        return redirect('/courses')
    return render(request, 'courses/course_add.html', {'form': form})

#studio detail courses
def studio(request, id):
 

    # Determine the course based on the user's role
    if request.user.is_superuser:
        course = Course.objects.filter(id=id).first()
    else:
        course = Course.objects.filter(id=id, author_id=request.user.id).first()

    # If no course is found, redirect to the courses list page
    if not course:
        return redirect('/courses')

    # Fetch sections related to the specific course
    section = Section.objects.filter(parent=None, courses_id=course.id)

    # Render the page with the course and sections data
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

def search_users(request):
    query = request.GET.get('q', '')
    
    # If query is empty, return no users or all active users (depending on your use case)
    if query:
        users = User.objects.filter(Q(email__icontains=query) & Q(is_active=True)).only('id', 'email')
    else:
        users = User.objects.filter(is_active=True).only('id', 'email')
    
    # Optional: Implement pagination (if needed)
    paginator = Paginator(users, 20)  # Show 20 users per page
    page_number = request.GET.get('page')  # Get the page number from the query params
    page_obj = paginator.get_page(page_number)
    
    # Prepare data for response
    users_data = [{'id': user.id, 'text': user.email} for user in page_obj]
    
    return JsonResponse({
        'users': users_data,
        'page': page_obj.number,
        'total_pages': paginator.num_pages,
        'total_users': paginator.count,
    })

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
            return redirect('/partner')  # Redirect to a course list page or success page
    else:
        form = PartnerForm()  # Pass the logged-in user to the form
    #print(request.POST)
    return render(request, 'partner/partner_add.html', {'form': form})


#contoh ajax
def course_create(request):
    data = dict()
    
    # Check if it's a POST request
    if request.method == 'POST':
        form = CourseForm(request.POST)
        
        if form.is_valid():
            # Save the new course if the form is valid
            form.save()
            data['form_is_valid'] = True
            
            # Fetch the updated course list after adding a new course
            courses = Course.objects.all()  # Corrected from Course.all() to Course.objects.all()
            data['course_list'] = render_to_string('courses/course_list.html', {'courses': courses})
        else:
            # Form is not valid, send this info back
            data['form_is_valid'] = False
    else:
        # For GET request, create an empty form
        form = CourseForm()
    
    # Render the course creation form
    context = {'form': form}
    data['html_form'] = render_to_string('courses/course_create.html', context, request=request)
    
    return JsonResponse(data)

# Delete Book
def course_delete(request, pk):
    courses = get_object_or_404(Course, pk=pk)
    data = dict()
    if request.method == 'POST':
        courses.delete()
        data['form_is_valid'] = True
        books = Course.objects.all()
        data['course_list'] = render_to_string('courses/course_list.html', {'courses': courses})
    return JsonResponse(data)

# View to fetch the list of books (for initial load)
@cache_page(60 * 15)
def course_list(request):
    courses = Course.objects.all()[:100]
    return render(request, 'courses/course_list.html', {'courses': courses})

def course_update(request, pk):
    course = get_object_or_404(Course, pk=pk)
    data = dict()
    if request.method == 'POST':
        form = CourseForm(request.POST, instance=course)
        if form.is_valid():
            form.save()
            data['form_is_valid'] = True
            courses = Course.objects.all()
            data['course_list'] = render_to_string('courses/course_list.html', {'courses': courses})
        else:
            data['form_is_valid'] = False
    else:
        form = CourseForm(instance=course)

    context = {'form': form}
    data['html_form'] = render_to_string('courses/course_update.html', context, request=request)
    return JsonResponse(data)
