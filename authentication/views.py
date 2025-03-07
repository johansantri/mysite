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
from courses.models import Instructor,Partner,Assessment,GradeRange,Submission,AssessmentScore,QuestionAnswer,CourseStatus,Enrollment,MicroCredential, MicroCredentialEnrollment,Course, Enrollment, Category,CourseProgress
from django.http import HttpResponse,JsonResponse
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.http import HttpResponseForbidden
from django.core.cache import cache
from django.db.models import Q
from django.core import serializers
from django.db.models import Count
from django.utils import timezone
from django.views.decorators.csrf import csrf_protect
from decimal import Decimal
from django.urls import reverse

# Create your views here.


def mycourse(request):
    if request.user.is_authenticated:
        # Mengambil semua kursus yang diambil oleh user yang sedang login
        courses = Enrollment.objects.filter(user=request.user)

        # Pencarian (Search)
        search_query = request.GET.get('search', '')
        if search_query:
            # Menambahkan filter pencarian berdasarkan nama kursus
            courses = courses.filter(Q(course__course_name__icontains=search_query))

        # Ordering the courses by enrolled_at or any relevant field
        courses = courses.order_by('-enrolled_at')  # Adjust this field based on your needs

        # Pagination
        paginator = Paginator(courses, 10)  # 10 item per halaman
        page_number = request.GET.get('page')
        page_obj = paginator.get_page(page_number)

        # Render template dengan data kursus dan pagination
        return render(request, 'learner/mycourse_list.html', {
            'page_obj': page_obj,
            'search_query': search_query
        })
          
    return redirect("/login/?next=%s" % request.path)

def microcredential_list(request):
    if request.user.is_authenticated:
        # Mengambil semua MicroCredential yang diambil oleh user yang sedang login
        microcredentials = MicroCredentialEnrollment.objects.filter(user=request.user)

        # Pencarian (Search)
        search_query = request.GET.get('search', '')
        if search_query:
            # Menambahkan filter pencarian berdasarkan judul atau nama microcredential
            microcredentials = microcredentials.filter(Q(microcredential__title__icontains=search_query))

        # Add order_by to ensure consistent pagination
        microcredentials = microcredentials.order_by('microcredential__title')  # Change 'title' to your preferred field

        # Pagination
        paginator = Paginator(microcredentials, 10)  # 10 item per halaman
        page_number = request.GET.get('page')
        page_obj = paginator.get_page(page_number)

        # Render template dengan data microcredentials dan pagination
        return render(request, 'learner/microcredential_list.html', {
            'page_obj': page_obj,
            'search_query': search_query
        })

    # Jika user belum login, redirect ke halaman login
    return redirect("/login/?next=%s" % request.path)



#course_list lms

def course_list(request):
    # Get the 'published' status from CourseStatus model
    published_status = CourseStatus.objects.get(status='published')  # Use 'status' field

    # Get all courses with 'published' status
    courses = Course.objects.filter(status_course=published_status)

    # Search functionality
    search_query = request.GET.get('search', '')
    if search_query:
        courses = courses.filter(course_name__icontains=search_query)

    # Filter by category
    category_filter = request.GET.getlist('category')  # Get selected categories as a list
    if category_filter:
        courses = courses.filter(category__in=category_filter)

    # Pagination setup
    paginator = Paginator(courses, 9)  # Show 9 courses per page
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
    # Pastikan pengguna yang mengakses adalah pengguna yang tepat
    user = get_object_or_404(User, id=user_id)  # Menggunakan user_id untuk mengambil pengguna
    
    # Ambil daftar kursus yang diikuti oleh pengguna ini
    enrollments = Enrollment.objects.filter(user=user)
    courses = [enrollment.course for enrollment in enrollments]
    
    # Implementasi pencarian berdasarkan course_name
    search_query = request.GET.get('search', '')
    if search_query:
        courses = [course for course in courses if search_query.lower() in course.course_name.lower()]
    
    # Menyiapkan data untuk pagination
    course_details = []
    for course in courses:
        # Ambil total skor dan status dari setiap kursus
        total_max_score = 0
        total_score = 0
        status = "Fail"  # Default status
        
        # Ambil nilai grade range untuk kursus tersebut
        grade_range = GradeRange.objects.filter(course=course).first()
        passing_threshold = grade_range.min_grade if grade_range else 0

        # Loop untuk mengambil skor dari setiap assessment dalam kursus
        assessments = Assessment.objects.filter(section__courses=course)
        for assessment in assessments:
            # Ambil skor untuk assessment ini
            score_value = Decimal(0)
            total_correct_answers = 0
            total_questions = assessment.questions.count()
            
            # Hitung skor untuk assessment ini (misalnya multiple-choice)
            if total_questions > 0:
                for question in assessment.questions.all():
                    answers = QuestionAnswer.objects.filter(question=question, user=user)
                    total_correct_answers += answers.filter(choice__is_correct=True).count()
                if total_questions > 0:
                    score_value = (Decimal(total_correct_answers) / Decimal(total_questions)) * Decimal(assessment.weight)
            
            total_max_score += assessment.weight
            total_score += score_value
        
        # Hitung status kelulusan
        if total_max_score > 0:
            overall_percentage = (total_score / total_max_score) * 100
            if overall_percentage >= passing_threshold:
                status = "Pass"
        
        # Tambahkan detail kursus ke daftar
        course_details.append({
            'course_name': course.course_name,
            'total_score': total_score,
            'total_max_score': total_max_score,
            'status': status
        })
    
    # Pagination untuk hasil kursus
    paginator = Paginator(course_details, 5)  # Menampilkan 5 kursus per halaman
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'user': user,
        'course_details': page_obj,  # Gunakan page_obj untuk paginasi
        'search_query': search_query,  # Kirim query pencarian untuk form pencarian
    }
    
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

    # Annotate the total courses enrolled by each user
    users = users.annotate(total_courses=Count('enrollments'))

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

    # Get the 'published' CourseStatus ID
    try:
        published_status = CourseStatus.objects.get(status='published')
    except CourseStatus.DoesNotExist:
        return JsonResponse({'error': 'Published status not found.'}, status=404)

    # Get popular courses filtered by the 'published' CourseStatus ID
    courses = Course.objects.filter(
        status_course=published_status,  # Use the 'published' CourseStatus object, not the string
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
    try:
        # Get the 'published' CourseStatus ID
        published_status = CourseStatus.objects.get(status='published')
    except CourseStatus.DoesNotExist:
        # Handle case where 'published' status is missing
        published_status = None

    if published_status:
        # Get the popular categories with published courses
        popular_categories = Category.objects.annotate(
            num_courses=Count('category_courses', filter=Q(category_courses__status_course=published_status))
        ).order_by('-num_courses')[:6]
        
        # Get the active microcredentials
        popular_microcredentials = MicroCredential.objects.filter(
            status='active'
        ).order_by('-created_at')[:6]  # Limit to 6 popular microcredentials

        # Get all partners
        partners = Partner.objects.all()  # Fetch all partners

    else:
        # If no 'published' status exists, handle gracefully
        popular_categories = []
        popular_microcredentials = []
        partners = []  # If no published courses, no partners are needed

    # Pagination: Show 6 partners per page
    paginator = Paginator(partners, 6)  # You can adjust the number of partners per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    return render(request, 'home/index.html', {
        'popular_categories': popular_categories,
        'popular_microcredentials': popular_microcredentials,
        'partners': page_obj,  # Send the paginated partners to the template
    })


def dasbord(request):
    if not request.user.is_authenticated:
        return redirect("/login/?next=%s" % request.path)

    # Get page number from GET parameters
    courses_page = request.GET.get('courses_page', 1)

    # Initialize variables for partner-specific data
    partner_courses = None
    partner_enrollments = None
    total_enrollments = 0
    total_courses = 0
    total_instructors = 0
    total_learners = 0
    total_partners = 0
    total_published_courses = 0
    publish_status = CourseStatus.objects.get(status='published')

    # Logic based on user role
    if request.user.is_superuser:
        # For superuser, count data for all partners
        total_enrollments = Enrollment.objects.count()
        total_courses = Course.objects.count()
        total_instructors = Instructor.objects.count()
        total_learners = User.objects.filter(is_learner=True).count()
        total_published_courses = Course.objects.filter(status_course=publish_status).count()
        partner_courses = Course.objects.all()  # Superuser sees all courses
        total_partners =  Partner.objects.count()  # Set total_partners to 1 if the user is a partner
    elif request.user.partner_user:  # Check if the user has a partner associated
        # For partner, get data specific to the partner
        partner = request.user.partner_user  # Access the partner instance linked to the user       

        # Filter courses based on the partner's organization
        partner_courses = Course.objects.filter(org_partner=partner)      
        
        
        # Filter enrollments based on the partner's courses
        partner_enrollments = Enrollment.objects.filter(course__org_partner=partner)        

        # Calculate total counts for the partner's data
        total_enrollments = partner_enrollments.count()
        total_courses = partner_courses.count()
        # Retrieve instructors for the partner's courses (linking through the courses)
        total_instructors = Instructor.objects.filter(provider__user=request.user).annotate(num_courses=Count('courses')).count()        

        # Count total learners (users enrolled in courses of the partner)
        total_learners = User.objects.filter(
            enrollments__course__org_partner=partner,  # Use 'enrollments' instead of 'enrollment'
            is_learner=True  # Ensure the user is a learner
        ).distinct().count()  # Use .distinct() to ensure each learner is counted only once        

        # Count published courses for the partner
        total_published_courses = partner_courses.filter(status_course=publish_status).count()     

    # Get the current date
    today = timezone.now().date()
    # Ensure the QuerySet is ordered for courses created today
    courses_created_today = Course.objects.filter(created_at__date=today).order_by('created_at')
    # Pagination for courses created today
    courses_paginator = Paginator(courses_created_today, 5)  # 5 courses per page
    courses_created_today = courses_paginator.get_page(courses_page)

    # Context for the template
    context = {
        'courses_page': courses_page,
        'total_enrollments': total_enrollments,
        'total_courses': total_courses,
        'total_instructors': total_instructors,
        'total_learners': total_learners,
        'total_partners': total_partners,  # Correct total_partners value
        'total_published_courses': total_published_courses,
        'courses_created_today': courses_created_today,
        'partner_courses': partner_courses,  # Pass partner-specific courses if available
    }

    return render(request, 'home/dasbord.html', context)


#dashboard for student
def dashbord(request):
    # Initialize variables
    if request.user.is_authenticated:
        enrollments = None
        search_query = request.GET.get('search', '')  # Get search query from the request
        enrollments_page = request.GET.get('enrollments_page', 1)  # Page number for enrollments
        
        # Fetch enrollments for the currently logged-in user and order by enrolled_at
        enrollments = Enrollment.objects.filter(user=request.user).order_by('-enrolled_at')  # Order by enrolled_at field

        # Search logic for enrollments (by username or course name)
        if search_query:
            enrollments = enrollments.filter(
                user__username__icontains=search_query
            ) | enrollments.filter(
                course__course_name__icontains=search_query
            )  # Search by user username or course name
        
        # Count of total enrollments
        total_enrollments = enrollments.count()

        # Fetch active courses that the user is enrolled in with "published" status
        active_courses = Course.objects.filter(
            id__in=enrollments.values('course'),
            status_course__status='published',
            start_enrol__lte=timezone.now(),  # Enrolment start date is in the past
            end_enrol__gte=timezone.now()     # Enrolment end date is in the future
        )

        # Completed Courses (assuming the course has a boolean 'is_completed' field)
        completed_courses = CourseProgress.objects.filter(user=request.user, progress_percentage=100)

        # Pagination for enrollments
        enrollments_paginator = Paginator(enrollments, 5)  # Show 5 enrollments per page
        enrollments = enrollments_paginator.get_page(enrollments_page)

        # Render the dashboard with the appropriate data
        return render(request, 'learner/dashbord.html', {
            'enrollments': enrollments,
            'search_query': search_query,  # Pass the search query to the template
            'enrollments_page': enrollments_page,
            'total_enrollments': total_enrollments,  # Total enrollments count
            'active_courses': active_courses,
            'completed_courses':completed_courses
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

            return redirect(reverse('authentication:edit-photo', args=[pk]))

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
    
    
