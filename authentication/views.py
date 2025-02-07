from django.shortcuts import render, get_object_or_404
import os
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User, Universiti
from PIL import Image
from io import BytesIO
from django.core.files.base import ContentFile
# import this for sending email to user
from django.contrib.auth.tokens import default_token_generator
from django.contrib.sites.shortcuts import get_current_site
from django.core.mail import EmailMessage
from django.shortcuts import render, redirect
from django.template.loader import render_to_string
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.contrib.auth import logout
from authentication.forms import UserRegistrationForm, Userprofile, UserPhoto
from .models import Profile
from courses.models import Instructor, Course, Enrollment, Category
from django.http import HttpResponse,JsonResponse
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.http import HttpResponseForbidden
from django.core.cache import cache
from django.db.models import Q
from django.core import serializers
from django.db.models import Count
from django.utils import timezone
from django.views.decorators.csrf import csrf_protect
# Create your views here.






#course_list lms

def course_list(request):
    # Get all courses
    courses = Course.objects.all()

    # Search functionality
    search_query = request.GET.get('search', '')
    if search_query:
        courses = courses.filter(course_name__icontains=search_query)

    # Filter by category
    category_filter = request.GET.getlist('category')  # Get selected categories as a list
    if category_filter:
        courses = courses.filter(category__in=category_filter)

    # Pagination setup
    paginator = Paginator(courses, 9)  # Show 4 courses per page
    page_number = request.GET.get('page', 1)  # Default to page 1 if no page is provided
    
    # Validate page_number: if it's invalid or empty, default to page 1
    try:
        page_number = int(page_number) if int(page_number) >= 1 else 1
    except ValueError:
        page_number = 1  # If it's not a valid integer, default to 1
    
    try:
        page_obj = paginator.get_page(page_number)  # Get the page object for pagination
    except PageNotAnInteger:
        # If the page is not an integer, return the first page
        page_obj = paginator.get_page(1)
    except EmptyPage:
        # If the page number is out of range (e.g., 9999), return the last page
        page_obj = paginator.get_page(paginator.num_pages)

    # Prepare pagination info for the template
    start_index = page_obj.start_index()
    end_index = page_obj.end_index()

    # Get all available categories to display in the filter
    categories = Category.objects.all()

    # Prepare courses data for rendering in template
    courses_data = []
    for course in page_obj:
        #course_price = 'FREE' if not course.org_partner.balance or course.org_partner.balance == 0 else course.org_partner.balance
        courses_data.append({
            'course_name': course.course_name,
            'course_id': course.id,
            'num_enrollments': course.enrollments.count(), 
            'course_slug': course.slug,
            'course_image': course.image.url if course.image else None,
            #'course_price': course_price,  # Store 'FREE' or the actual balance
            'instructor': course.instructor.user.get_full_name() if course.instructor else None,
            'instructor_username': course.instructor.user.username if course.instructor else None,
            'photo': course.instructor.user.photo.url if course.instructor and course.instructor.user.photo else None,
            'partner': course.org_partner.name if course.org_partner else None,  # Corrected access to partner name
            'category': course.category.name if course.category else None,  # Corrected access to category name
            #'universiti': course.org_partner.name.name if course.org_partner and course.org_partner.name else None  # Serialize Universiti's name
        })

    # Prepare the context for rendering
    context = {
        'courses': courses_data,
        'page_obj': page_obj, 
        'total_courses': courses.count(),
        'total_pages': paginator.num_pages,
        'current_page': page_obj.number,
        'start_index': start_index,
        'end_index': end_index,
        'search_query': search_query,
        'category_filter': category_filter,
        'categories': list(categories.values('id', 'name')),  # Ensure categories are serializable
    }

    return render(request, 'home/course_list.html', context)


#detailuser
def user_detail(request, user_id):
    # Check if the user is authenticated
    if not request.user.is_authenticated:
        return redirect("/login/?next=%s" % request.path)
    
    try:
        if request.user.is_superuser:
            # Superuser can view details of any user
            user = get_object_or_404(User, id=user_id)
        elif request.user.is_partner:
            # Partner can view users related to their university, excluding superusers
            if request.user.university:
                user = get_object_or_404(
                    User,
                    id=user_id,
                    university=request.user.university,
                    is_superuser=False
                )
            else:
                # Deny access if the partner is not associated with a university
                return HttpResponseForbidden("You are not associated with any university.")
        else:
            # Other users can only view their own details
            user = get_object_or_404(User, id=request.user.id)
    except User.DoesNotExist:
        return HttpResponseForbidden("You do not have permission to view this user's details.")

    # Prepare the context with the user's details
    context = {
        'user': user
    }

    # Render the user detail template
    return render(request, 'authentication/user_detail.html', context)



def all_user(request):
    if not request.user.is_authenticated:
        return redirect("/login/?next=%s" % request.path)
    
    # Role-based filtering
    if request.user.is_superuser:
        # Superuser can access all users
        users = User.objects.all().order_by('-date_joined')
    elif request.user.is_partner:
        # Partner can only access users related to their university, excluding superusers
        if request.user.university:
            users = User.objects.filter(
                university=request.user.university, 
                is_superuser=False
            ).order_by('-date_joined')
        else:
            # If the partner has no associated university, deny access
            return HttpResponseForbidden("You are not associated with any university.")
    else:
        # If not superuser or partner, show only self data
        users = User.objects.filter(id=request.user.id).order_by('-date_joined')

    # Get filters from GET request
    search_query = request.GET.get('search', '').strip()
    status_filter = request.GET.get('status', '').strip()
    date_from = request.GET.get('date_from', '').strip()
    date_to = request.GET.get('date_to', '').strip()
    page_number = request.GET.get('page', 1)

    # Search functionality
    if search_query:
        users = users.filter(
            Q(username__icontains=search_query) | 
            Q(email__icontains=search_query) |
            Q(first_name__icontains=search_query)
        )

    # Status filter
    if status_filter:
        if status_filter == 'active':
            users = users.filter(is_active=True)
        elif status_filter == 'inactive':
            users = users.filter(is_active=False)

    # Date filters
    if date_from:
        users = users.filter(date_joined__gte=date_from)
    if date_to:
        users = users.filter(date_joined__lte=date_to)

    # Get the total count of users (before pagination and filtering)
    total_user_count = users.count()

    # Paginate the results
    paginator = Paginator(users, 10)  # Show 10 users per page
    page_obj = paginator.get_page(page_number)

    # Render the template with user data and the total count
    context = {
        'users': page_obj,
        'search_query': search_query,
        'total_user_count': total_user_count,
        'status_filter': status_filter,
        'date_from': date_from,
        'date_to': date_to,
    }

    return render(request, 'authentication/all_user.html', context)

@csrf_protect  # Keep this if you're doing a POST request or if you need it for security
def popular_courses(request):
    # Get the current date
    now = timezone.now().date()

    # Get popular courses
    courses = Course.objects.filter(
        status_course='published',
        end_date__gte=now
    ).annotate(
        num_enrollments=Count('enrollments')
    ).order_by('-num_enrollments')[:6]

    # Check if there are no courses
    if not courses.exists():
        return JsonResponse({'error': 'No popular courses found.'}, status=404)

    # Convert queryset to list of dictionaries
    courses_list = list(courses.values(
        'id', 'course_name', 'slug', 'image','num_enrollments',
        'instructor__user__first_name',
        'instructor__user__last_name', 
        'instructor__user__photo',
        'instructor__user__username',
        'org_partner__name__name',
        'org_partner__name__slug',
        'org_partner__logo',
    ))

    # Update image URLs to be full URLs
    for course in courses_list:
        if course['image']:
            course['image'] = settings.MEDIA_URL + course['image']
        if course['instructor__user__photo']:
            course['instructor__user__photo'] = settings.MEDIA_URL + course['instructor__user__photo']
        if course['org_partner__logo']:
            course['org_partner__logo'] = settings.MEDIA_URL + course['org_partner__logo']
    
    # Return JSON response
    return JsonResponse({'courses': courses_list})

def home(request):
    
    popular_categories = Category.objects.annotate(
    num_courses=Count('category_courses', filter=Q(category_courses__status_course='published'))
    ).order_by('-num_courses')[:6]

    
    

    
    return render(request, 'home/index.html',{'popular_categories':popular_categories})




def dasbord(request):
    # Initialize variables
    if request.user.is_authenticated:
        enrollments = None
        search_query = request.GET.get('search', '')  # Get search query from the request
        enrollments_page = request.GET.get('enrollments_page', 1)  # Page number for enrollments
        
        # Fetch enrollments for the currently logged-in user
        enrollments = Enrollment.objects.filter(user=request.user)

        # Search logic for enrollments (by username or course name)
        if search_query:
            enrollments = enrollments.filter(
                user__username__icontains=search_query
            ) | enrollments.filter(
                course__course_name__icontains=search_query
            )  # Search by user username or course name
        
        # Pagination for enrollments
        enrollments_paginator = Paginator(enrollments, 5)  # Show 5 enrollments per page
        enrollments = enrollments_paginator.get_page(enrollments_page)

        # Render the dashboard with the appropriate data
        return render(request, 'home/dasbord.html', {
            'enrollments': enrollments,
            'search_query': search_query,  # Pass the search query to the template
            'enrollments_page': enrollments_page
        })
    return redirect("/login/?next=%s" % request.path)


def pro(request,username):
    if request.user.is_authenticated:
        username=User.objects.get(username=username)
        instructor = Instructor.objects.filter(user=username).first()

        return render(request,'home/profile.html',{

            'user': username,

            'instructor': instructor,  # This will be None if the user is not an instructor

        })
    return redirect("/login/?next=%s" % request.path)

@login_required
def edit_profile(request, pk):
    # Retrieve the user instance based on the primary key
    user = get_object_or_404(User, pk=pk)

    if request.method == "GET":
        # Render the form with the user's current data
        form = Userprofile(instance=user)
        return render(request, 'home/edit_profile_form.html', {'form': form})

    elif request.method == "POST":
        # Populate the form with POST data and the user instance
        form = Userprofile(request.POST,request.FILES, instance=user)
        if form.is_valid():
            form = form.save(commit=False)
            if not request.FILES.get('photo'):

            # If no new photo, keep the existing one

                form.photo = request.user.photo 
            form.save()
            return JsonResponse({'success': True, 'message': 'Profile updated successfully!'})
        else:
            # If the form is invalid, re-render the form with errors
            return render(request, 'home/edit_profile_form.html', {'form': form}, status=400)
    

#convert image before update
def process_image_to_webp(uploaded_photo):
    # Open the image using Pillow
    img = Image.open(uploaded_photo)

    # Convert the image to RGB mode (if not already in RGB)
    img = img.convert('RGB')

    # Resize the image to 50% of its original size
    width, height = img.size
    new_size = (width // 2, height // 2)
    img = img.resize(new_size, Image.Resampling.LANCZOS)  # Use LANCZOS for high-quality resizing

    # Save the image to a BytesIO buffer in WebP format
    buffer = BytesIO()
    img.save(buffer, format='WEBP', quality=85)  # Adjust quality as needed
    buffer.seek(0)

    # Return the processed image as a ContentFile
    return ContentFile(buffer.read(), name='photo.webp')

#update image
def edit_photo(request, pk):
    user = get_object_or_404(User, pk=pk)

    if request.method == "GET":
        form = UserPhoto(instance=user)
        return render(request, 'home/edit_photo.html', {'form': form})

    elif request.method == "POST":
        old_photo_path = user.photo.path if user.photo else None
        form = UserPhoto(request.POST, request.FILES, instance=user)

        if form.is_valid():
            user_profile = form.save(commit=False)

            if 'photo' in request.FILES:
                # Process the uploaded photo
                uploaded_photo = request.FILES['photo']
                processed_photo = process_image_to_webp(uploaded_photo)
                user_profile.photo = processed_photo

            user_profile.save()

            if old_photo_path and os.path.exists(old_photo_path):
                os.remove(old_photo_path)

            return redirect('authentication:dasbord')

        else:
            return render(request, 'home/edit_photo.html', {'form': form}, status=400)

@login_required
def edit_profile_save(request, pk):
    # Ensure the profile exists, fetching by pk
    profile = get_object_or_404(User, pk=pk)

    if request.method == "POST":
        # Create a form instance bound to the profile
        form = Userprofile(request.POST,request.FILES, instance=profile)
        if form.is_valid():
            form.save()
            # Render the updated profile details
            return render(request, 'home/profile_detail.html', {'user': profile})
        else:
            # Return the form with errors and a 400 status code
            return render(request, 'home/edit_profile_form.html', {'form': form}, status=400)

    # If the method is not POST, handle it gracefully (e.g., redirect)
    return JsonResponse({'error': 'Invalid request method'}, status=405)

def logout_view(request):
    logout(request)
    return redirect('authentication:login')
def register(request):
    form = UserRegistrationForm()

    if request.method == "POST":
        form = UserRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.is_active = False
            user.save()

            # email user with activation link
            current_site = get_current_site(request)
            mail_subject = "Activate your account."

            # the message will render what is written in authentication/email_activation/activate_email_message.html
            message = render_to_string('authentication/email_activation/activate_email_message.html', {
                    'user': form.cleaned_data['username'],
                    'domain': current_site.domain,
                    'uid': urlsafe_base64_encode(force_bytes(user.pk)),
                    'token':  default_token_generator.make_token(user),
                })
            to_email = form.cleaned_data['email']
            email = EmailMessage(
                mail_subject, message, to=[to_email]
            )
            email.send()
            messages.success(request, 'Account created successfully. Please check your email to activate your account.')
            return redirect('login')
        else:
            messages.error(request, 'Account creation failed. Please try again.')


    return render(request, 'authentication/register.html',{
        'form': form
    })

# to activate user from email
def activate(request, uidb64, token):
    try:
        uid = urlsafe_base64_decode(uidb64).decode()
        user = User.objects.get(pk=uid)
    except(TypeError, ValueError, OverflowError, User.DoesNotExist):
        user = None
    if user is not None and default_token_generator.check_token(user, token):
        user.is_active = True
        user.save()
        return render(request, 'authentication/email_activation/activation_successful.html')
    else:
        return render(request, 'authentication/email_activation/activation_unsuccessful.html')

def profile_list(request):
    if request.user.is_authenticated:
        profiles = Profile.objects.exclude(user=request.user)
        return render(request,'authentication/profile.html',{'profiles':profiles})
    else:
        return redirect('login')
    
def profile(request,pk):
    if request.user.is_authenticated:
        profile = Profile.objects.get(user_id=pk)
        if request.method == "POST":
            current_user_profile = request.user.profile
            action = request.POST['follow']
            if action =="unfollow":
                current_user_profile.follows.remove(profile)
            elif action == "follow":
                current_user_profile.follows.add(profile)
            current_user_profile.save()
            
        return render(request,'authentication/myprofile.html',{'profile':profile})
    else:
        return redirect('login')
    
    
