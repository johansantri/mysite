import os
from io import BytesIO
from PIL import Image
from django.conf import settings
from django.core.files.base import ContentFile
from django.core.cache import cache
from django.shortcuts import render, redirect, get_object_or_404
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.db.models import Q
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required
from .forms import CoursePriceForm,CourseForm,CourseRerunForm, PartnerForm,PartnerFormUpdate,CourseInstructorForm, SectionForm,GradeRangeForm, ProfilForm,InstructorForm,InstructorAddCoruseForm,TeamMemberForm, MatrialForm,QuestionForm,ChoiceFormSet,AssessmentForm
from django.http import JsonResponse
from .models import Course,CoursePrice,PricingType, Partner,GradeRange,Category, Section,Instructor,TeamMember,Material,Question,Assessment
from django.contrib.auth.models import User, Universiti
from django.template.loader import render_to_string
from django.views.decorators.cache import cache_page
from django.urls import reverse
from django.contrib import messages
from django.db.models import F
from django.http import HttpResponseForbidden
from django_ckeditor_5.widgets import CKEditor5Widget
from django import forms
from django.http import JsonResponse
from decimal import Decimal
from django.db.models import Sum
from datetime import datetime
from django.db.models import Count
from django.utils.text import slugify
from django.utils import timezone

def course_reruns(request, id):
    """ View for creating a re-run of a course """

    course = get_object_or_404(Course, id=id)

    # Check if the user has permission to create a re-run
    if not (request.user.is_superuser or request.user == course.org_partner.user or request.user == course.instructor.user):
        messages.error(request, "You do not have permission to create a re-run for this course.")
        return redirect('courses:studio', id=course.id)

    if request.method == 'POST':
        form = CourseRerunForm(request.POST)

        if form.is_valid():
            # Check if a re-run already exists for today
            today = timezone.now().date()
            existing_rerun = Course.objects.filter(
                course_name=course.course_name,  # Same course name
                course_run__startswith="Run",  # Check if it's a re-run
                created_at__date=today  # Check if it's the same day
            ).exists()

            if existing_rerun:
                messages.error(request, "A re-run for this course has already been created today.")
                return redirect('courses:studio', id=course.id)

            # Proceed to create re-run
            new_course = form.save(commit=False)

            # Manually assign the fields that should be copied from the original course
            new_course.course_name = course.course_name  # Keep original course name
            new_course.org_partner = course.org_partner  # Keep original partner
            new_course.image = course.image  # Copy the image
            new_course.description = course.description  # Copy the description
            new_course.language = course.language  # Copy the language
            new_course.sort_description = course.sort_description  # Copy sort_description
            new_course.hour = course.hour  # Copy hour
            new_course.author = request.user  # Set the current user as the author
            new_course.link_video = course.link_video  # Copy the link_video

            new_course.slug = f"{slugify(new_course.course_name)}-{new_course.course_run.lower().replace(' ', '-')}"
            new_course.created_at = timezone.now()
            new_course.status_course = "draft"  # Start as draft

            new_course.save()

            messages.success(request, f"Re-run of course '{new_course.course_name}' created successfully!")
            return redirect('courses:studio', id=new_course.id)

        else:
            messages.error(request, "There was an error with the form. Please correct the errors below.")
            print(form.errors)  # Optional: print form errors for debugging

    else:
        form = CourseRerunForm(instance=course)

        # Add values to hidden inputs for course_name and org_partner
        form.fields['course_name_hidden'].initial = course.course_name
        form.fields['org_partner_hidden'].initial = course.org_partner

    return render(request, 'courses/course_reruns.html', {'form': form, 'course': course})




#add course price
def add_course_price(request, id):
    print("🔄 Form submitted!")  # Debugging

    if not request.user.is_authenticated:
        return redirect(f"/login/?next={request.path}")

    if request.user.is_superuser:
        course = get_object_or_404(Course, id=id)
        existing_price = None
    elif hasattr(request.user, 'is_partner') and request.user.is_partner:
        course = get_object_or_404(Course, id=id, org_partner__user_id=request.user.id)
        existing_price = CoursePrice.objects.filter(course=course, price_type__name="Beli Langsung").first()
    else:
        messages.error(request, "Anda tidak memiliki izin untuk menambahkan harga ke kursus ini.")
        return redirect('authentication:dashboard')

    if request.method == 'POST':
        print("✅ POST request received")  # Debugging
        print("📨 Data yang dikirim:", request.POST)  # Debugging, lihat isi form yang dikirim

        form = CoursePriceForm(request.POST, user=request.user, course=course, instance=existing_price)
        if form.is_valid():
            print("✅ Form is valid")  # Debugging
            course_price = form.save(commit=False)
            course_price.course = course

            if hasattr(request.user, 'is_partner') and request.user.is_partner:
                try:
                    course_price.price_type = PricingType.objects.get(name="Beli Langsung")
                except PricingType.DoesNotExist:
                    messages.error(request, "Tipe harga 'Beli Langsung' tidak ditemukan! Tambahkan di database.")
                    return redirect(reverse('courses:add_course_price', args=[course.id]))

            course_price.save()
            messages.success(request, "✅ Harga kursus berhasil disimpan!")
            print("✅ Data berhasil disimpan!")  # Debugging
            return redirect(reverse('courses:add_course_price', args=[course.id]))  # Harusnya Redirect 302
        else:
            print("❌ Form is NOT valid")  # Debugging
            print(form.errors)  # Debugging, lihat kenapa form tidak valid
            for error in form.errors.get("__all__", []):
                messages.error(request, error)
        
    else:
        form = CoursePriceForm(user=request.user, course=course, instance=existing_price)

    return render(request, 'courses/course_price_form.html', {'form': form, 'course': course})

#instrcutor profile
def instructor_profile(request, username):
    # Fetch the instructor object
    instructor = get_object_or_404(Instructor, user__username=username)

    # Ensure that the instructor has a provider (Partner) with a slug in the related Universiti
    if not instructor.provider or not hasattr(instructor.provider.name, 'slug'):
        # Handle the case where there is no provider or slug
        partner_slug = None
    else:
        partner_slug = instructor.provider.name.slug  # Access slug from Universiti model

    # Get the search term from the GET request (if any)
    search_term = request.GET.get('search', '')

    # Filter courses based on the search term, published status, and end_date
    courses = instructor.courses.filter(
        Q(course_name__icontains=search_term) &  # Search by course name
        Q(status_course='published') &           # Only show published courses
        Q(end_date__gte=datetime.now())  # Only courses that haven't ended yet
    ).order_by('start_date')  # Optional: Order by start date or any other field

    # Get the count of filtered courses
    courses_count = courses.count()

    # Implement pagination: Show 6 courses per page
    paginator = Paginator(courses, 6)

    # Get the current page number from GET params (default to 1 if invalid)
    page_number = request.GET.get('page', 1)  # Default to page 1 if not specified

    # Ensure the page number is a positive integer
    try:
        page_number = int(page_number)
        if page_number < 1:
            page_number = 1  # If the page number is less than 1, set it to 1
    except ValueError:
        page_number = 1  # If the page number is not a valid integer, set it to 1

    # Get the page object
    try:
        page_obj = paginator.get_page(page_number)
    except EmptyPage:
        page_obj = paginator.get_page(1)  # If page number is out of range, show first page

    # Pass the instructor, courses, paginated courses, and courses count to the template
    return render(request, 'home/instructor_profile.html', {
        'instructor': instructor,
        'page_obj': page_obj,
        'courses_count': courses_count,  # Pass the count to the template
        'search_term': search_term,
        'partner_slug': partner_slug  # Pass partner_slug to the template
    })
#ernroll
def enroll_course(request, course_id):
    course = get_object_or_404(Course, id=course_id)
    result = course.enroll_user(request.user)
    return JsonResponse(result)

def draft_lms(request, id):
    if not request.user.is_authenticated:
        return redirect("/login/?next=%s" % request.path)  # Redirect to login if not authenticated

    user = request.user
    course = None

    # Determine the course based on the user's role
    if request.user.is_superuser:
        course = get_object_or_404(Course, id=id)
    elif user.is_partner:
        course = get_object_or_404(Course, id=id, org_partner__user_id=user.id)
    elif user.is_instructor:
        course = get_object_or_404(Course, id=id, instructor__user_id=user.id)

    # If no course is found, redirect to the homepage
    if not course:
        return redirect('/')  # Redirect to the homepage if the course is not found

    # If the course is found, render the course page
    return render(request, 'courses/course_draft_view.html', {'course': course})


def course_lms_detail(request, id,slug):
    # Fetch the course by slug
    course = get_object_or_404(Course, id=id, slug=slug)
    
    # Check if the course's status is not 'published'
    if course.status_course != 'published':
        return redirect('/')  # Redirect to the homepage or another page of your choice

    # Find similar courses based on category and level, only if the course is published
    similar_courses = Course.objects.filter(
        category=course.category,
        status_course='published',  # Only published courses
        end_date__gte=datetime.now()  # Only courses with end_date in the future
    ).exclude(id=course.id)[:5]  # Exclude the current course and limit to 5

    # Optionally, add instructor as another similarity criterion
    if course.instructor:
        similar_courses_by_instructor = Course.objects.filter(
            instructor=course.instructor,
            status_course='published',  # Only published courses
            end_date__gte=datetime.now()  # Only courses with end_date in the future
        ).exclude(id=course.id)[:5]
        similar_courses = similar_courses | similar_courses_by_instructor  # Combine queries (union)

    # Render the course page with the similar courses
    return render(request, 'home/course_detail.html', {
        'course': course,
        'similar_courses': similar_courses
    })

def course_instructor(request,id):
    if not request.user.is_authenticated:
        return redirect("/login/?next=%s" % request.path)
    user = request.user
    course = None
    # Determine the course based on the user's role
    if request.user.is_superuser:
        course = get_object_or_404(Course, id=id)
    elif user.is_partner:
        #course = Course.objects.filter(id=id, org_partner_id=request.user.id).first()
        course = get_object_or_404(Course, id=id, org_partner__user_id=user.id)
        print(course)
    elif user.is_instructor:
        messages.error(request, "You have do not have permission.")
        #course = get_object_or_404(Course, id=id, instructor__user_id=user.id)
    # If no course is found, redirect to the courses list page
        print(course)
    if not course:
        return redirect('/courses')
    

    course = get_object_or_404(Course, id=id)

    if request.method == 'POST':
        form = CourseInstructorForm(request.POST, instance=course, request=request)
        if form.is_valid():
            form.save()
            messages.success(request, "You have add instructor to this course.")
            return redirect('courses:course_instructor', id=course.id)
    else:
        form = CourseInstructorForm(instance=course, request=request)  # For GET requests, display the form with existing course data

    
    return render(request,'instructor/course_instructor.html',{'course': course, 'form': form})
#create grade
#@login_required
def course_grade(request, id):
    # Check if the user is authenticated
    if not request.user.is_authenticated:
        return redirect("/login/?next=%s" % request.path)
    

    user = request.user
    course = None

  
    # Determine the course based on the user's role
    if request.user.is_superuser:
        course = get_object_or_404(Course, id=id)
    elif user.is_partner:
        #course = Course.objects.filter(id=id, org_partner_id=request.user.id).first()
        course = get_object_or_404(Course, id=id, org_partner__user_id=user.id)
        #print(course)
    elif user.is_instructor:
        course = get_object_or_404(Course, id=id, instructor__user_id=user.id)
    # If no course is found, redirect to the courses list page
        #print(course)
    if not course:
        return redirect('/courses')
    
    course = get_object_or_404(Course, id=id)

   # Ensure grade ranges exist; create defaults if necessary
    grade_fail, created_fail = course.grade_ranges.get_or_create(
        name="Fail",
        defaults={"min_grade": 0, "max_grade": 59},
    )
    grade_pass, created_pass = course.grade_ranges.get_or_create(
        name="Pass",
        defaults={"min_grade": 60, "max_grade": 100},
    )

    # Compute widths for display
    total_grade_range = 100
    fail_width = (grade_fail.max_grade / total_grade_range) * 100
    pass_width = 100 - fail_width

    # Compute grade ranges
    fail_range_max = int(grade_fail.max_grade)
    pass_range_min = fail_range_max + 1

    return render(request, 'courses/course_grade.html', {
        'course': course,
        "fail_width": fail_width,
        "pass_width": pass_width,
        "fail_range_max": fail_range_max,
        "pass_range_min": pass_range_min,
    })


#@login_required
def update_grade_range(request, id):
    # Check if the user is authenticated
    if not request.user.is_authenticated:
        return redirect("/login/?next=%s" % request.path)
    
    user = request.user
    course = None

     # Determine the course based on the user's role
    if request.user.is_superuser:
        course = get_object_or_404(Course, id=id)
    elif user.is_partner:
        #course = Course.objects.filter(id=id, org_partner_id=request.user.id).first()
        course = get_object_or_404(Course, id=id, org_partner__user_id=user.id)
        #print(course)
    elif user.is_instructor:
        course = get_object_or_404(Course, id=id, instructor__user_id=user.id)
    # If no course is found, redirect to the courses list page
        #print(course)
    if not course:
        # Instructors can delete sections only for their own courses
        if course.instructor.user_id != request.user.id:
            return JsonResponse({'status': 'error', 'message': 'Permission denied.'})



    if request.method == "POST":
        try:
            # Fetch course
            course = get_object_or_404(Course, id=id)

            # Get Fail and Pass widths from the AJAX request
            fail_width = Decimal(request.POST.get("fail_width", 50))  # Example: 40.0
            pass_width = Decimal(request.POST.get("pass_width", 50))  # Example: 60.0

            # Get Fail and Pass grade ranges
            grade_fail = course.grade_ranges.filter(name="Fail").first()
            grade_pass = course.grade_ranges.filter(name="Pass").first()

            if not grade_fail or not grade_pass:
                return JsonResponse({"success": False, "message": "Fail or Pass grade range not found!"})

            # Dynamically calculate and update ranges
            grade_fail.max_grade = int((fail_width / 100) * 100)  # Fail max_grade = % of total grade
            grade_pass.min_grade = grade_fail.max_grade + 1  # Pass starts right after Fail's max_grade
            grade_pass.max_grade = 100  # Pass always ends at 100

            # Save updates
            grade_fail.save()
            grade_pass.save()

            return JsonResponse({"success": True, "message": "Grade ranges updated dynamically!"})

        except Exception as e:
            return JsonResponse({"success": False, "message": str(e)})
    return JsonResponse({"success": False, "message": "Invalid request"})


#creat assesment type name
#@login_required
@csrf_exempt
def create_assessment(request, idcourse, idsection):
    # Check if the user is authenticated
    if not request.user.is_authenticated:
        return redirect("/login/?next=%s" % request.path)

    # Determine the course based on the user's role
    if request.user.is_superuser:
        course = get_object_or_404(Course, id=idcourse)
    elif request.user.is_partner:
        # Ensure the course is associated with the partner
        course = get_object_or_404(Course, id=idcourse, org_partner__user_id=request.user.id)
    elif request.user.is_instructor:
        # Ensure the course is associated with the instructor
        course = get_object_or_404(Course, id=idcourse, instructor__user_id=request.user.id)
    else:
        # Unauthorized access
        messages.error(request, "You do not have permission to create assessments for this course.")
        return redirect('courses:home')  # Redirect to a safe page

    # Ensure the section belongs to the course
    section = get_object_or_404(Section, id=idsection, courses=course)

    if request.method == 'POST':
        form = AssessmentForm(request.POST)
        if form.is_valid():
            # Convert new_weight to Decimal
            new_weight = Decimal(form.cleaned_data['weight'])
            total_weight = Assessment.objects.filter(section=section).aggregate(Sum('weight'))['weight__sum'] or Decimal('0')

            if total_weight + new_weight > Decimal('100'):
                messages.error(request, "Total bobot untuk penilaian dalam section ini tidak boleh melebihi 100")
                return render(request, 'courses/course_assessement.html', {'form': form, 'course': course, 'section': section})

            # Create the assessment instance but don't save it yet
            assessment = form.save(commit=False)
            # Set the section field
            assessment.section = section
            # Save the assessment
            assessment.save()
            messages.success(request, "Assessment created successfully!")
            return redirect('courses:view-question', idcourse=course.id, idsection=section.id, idassessment=assessment.id)
    else:
        form = AssessmentForm()

    return render(request, 'courses/course_assessement.html', {'form': form, 'course': course, 'section': section})
#edit assesment type name
#@login_required
@csrf_exempt
def edit_assessment(request, idcourse, idsection, idassessment):
    # Check if the user is authenticated
    if not request.user.is_authenticated:
        return redirect("/login/?next=%s" % request.path)

    # Determine the course based on the user's role
    if request.user.is_superuser:
        course = get_object_or_404(Course, id=idcourse)
    elif request.user.is_partner:
        course = get_object_or_404(Course, id=idcourse, org_partner__user_id=request.user.id)
    elif request.user.is_instructor:
        course = get_object_or_404(Course, id=idcourse, instructor__user_id=request.user.id)
    else:
        # Unauthorized access
        messages.error(request, "You do not have permission to edit assessments for this course.")
        return redirect('courses:home')  # Redirect to a safe page

    # Ensure the section belongs to the course
    section = get_object_or_404(Section, id=idsection, courses=course)

    # Fetch the assessment based on its ID
    assessment = get_object_or_404(Assessment, id=idassessment, section=section)

    if request.method == 'POST':
        form = AssessmentForm(request.POST, instance=assessment)  # Populate the form with current assessment data
        if form.is_valid():
            # Save without committing
            assessment = form.save(commit=False)

            # Check total weight
            total_weight = Assessment.objects.filter(section=section).exclude(id=idassessment).aggregate(Sum('weight'))['weight__sum'] or Decimal('0')
            if total_weight + Decimal(form.cleaned_data['weight']) > Decimal('100'):
                messages.error(request, "Total bobot untuk penilaian dalam section ini tidak boleh melebihi 100")
                return render(request, 'courses/course_assessement_edit.html', {
                    'form': form,
                    'course': course,
                    'section': section,
                    'assessment': assessment,
                })

            # Now save the assessment
            assessment.save()
            messages.success(request, "Assessment updated successfully!")
            return redirect('courses:view-question', idcourse=course.id, idsection=section.id, idassessment=assessment.id)

    else:
        # Create an empty form or pre-populated form with existing data
        form = AssessmentForm(instance=assessment)

    return render(request, 'courses/course_assessement_edit.html', {
        'form': form,
        'course': course,
        'section': section,
        'assessment': assessment,
    })

#delete assesment type name
#@login_required
@csrf_exempt
def delete_assessment(request, idcourse, idsection, idassessment):
    # Check if the user is authenticated
    if not request.user.is_authenticated:
        return redirect("/login/?next=%s" % request.path)
    # Determine the course based on the user's role
    if request.user.is_superuser:
        course = get_object_or_404(Course, id=idcourse)
    elif request.user.is_partner:
        # Ensure the course is associated with the partner
        course = get_object_or_404(Course, id=idcourse, org_partner__user_id=request.user.id)
    elif request.user.is_instructor:
        # Ensure the course is associated with the instructor
        course = get_object_or_404(Course, id=idcourse, instructor__user_id=request.user.id)
    else:
        # Unauthorized access
        messages.error(request, "You do not have permission to delete assessments for this course.")
        return redirect('courses:home')  # Redirect to a safe page

    # Ensure the section belongs to the course
    section = get_object_or_404(Section, id=idsection, courses=course)

    # Fetch the assessment
    assessment = get_object_or_404(Assessment, id=idassessment, section=section)

    if request.method == 'POST':
        # Perform the deletion
        assessment.delete()
        messages.success(request, "Assessment deleted successfully!")
        return redirect('courses:studio', id=course.id)

    # Render confirmation page for GET requests
    return render(request, 'courses/confirm_delete_assessment.html', {
        'course': course,
        'section': section,
        'assessment': assessment,
    })


#edit question and choice
#@login_required
@csrf_exempt
def edit_question(request, idcourse, idquestion, idsection, idassessment):
    # Check if the user is authenticated
    if not request.user.is_authenticated:
        return redirect("/login/?next=%s" % request.path)
    # Determine the course based on the user's role
    if request.user.is_superuser:
        course = get_object_or_404(Course, id=idcourse)
    elif request.user.is_partner:
        # Ensure the course is associated with the partner
        course = get_object_or_404(Course, id=idcourse, org_partner__user_id=request.user.id)
    elif request.user.is_instructor:
        # Ensure the course is associated with the instructor
        course = get_object_or_404(Course, id=idcourse, instructor__user_id=request.user.id)
    else:
        # Unauthorized access
        messages.error(request, "You do not have permission to edit questions for this course.")
        return redirect('courses:home')  # Redirect to a safe page

    # Ensure the section belongs to the course
    section = get_object_or_404(Section, id=idsection, courses=course)

    # Ensure the assessment belongs to the section
    assessment = get_object_or_404(Assessment, id=idassessment, section=section)

    # Ensure the question belongs to the assessment
    question = get_object_or_404(Question, id=idquestion, assessment=assessment)

    # Pass the assessment to the forms
    form = QuestionForm(request.POST or None, instance=question, assessment=assessment)
    choice_formset = ChoiceFormSet(request.POST or None, instance=question)

    # Pass assessment to each form in the formset
    for choice_form in choice_formset.forms:
        choice_form.fields['text'].widget = (
            CKEditor5Widget("extends") if assessment.flag else forms.TextInput(attrs={'class': 'form-control'})
        )

    if request.method == 'POST':
        if form.is_valid() and choice_formset.is_valid():
            # Save the question form
            question = form.save(commit=False)
            question.section = section
            question.save()

            # Save the formset
            choice_formset.instance = question
            choice_formset.save()

            messages.success(request, "Question and choices updated successfully!")

            # Check if 'save and add another' button was clicked
            if 'save_and_add_another' in request.POST:
                return redirect('courses:create_question', idcourse=course.id, idsection=section.id, idassessment=assessment.id)

            return redirect('courses:view-question', idcourse=course.id, idsection=section.id, idassessment=assessment.id)
        else:
            print("Form errors:", form.errors)
            print("Formset errors:", [choice_form.errors for choice_form in choice_formset.forms])
            messages.error(request, "There was an error updating the question. Please check your inputs.")

    return render(request, 'courses/edit_question.html', {
        'form': form,
        'choice_formset': choice_formset,
        'course': course,
        'section': section,
        'assessment': assessment,
    })

#create question and choice
#@login_required
@csrf_exempt
def create_question_view(request, idcourse, idsection, idassessment):
    # Check if the user is authenticated
    if not request.user.is_authenticated:
        return redirect("/login/?next=%s" % request.path)
    
    # Determine the course based on the user's role
    if request.user.is_superuser:
        course = get_object_or_404(Course, id=idcourse)
    elif request.user.is_partner:
        # Ensure the course is associated with the partner
        course = get_object_or_404(Course, id=idcourse, org_partner__user_id=request.user.id)
    elif request.user.is_instructor:
        # Ensure the course is associated with the instructor
        course = get_object_or_404(Course, id=idcourse, instructor__user_id=request.user.id)
    else:
        # Unauthorized access
        messages.error(request, "You do not have permission to create questions for this course.")
        return redirect('courses:home')  # Redirect to a safe page

    # Ensure the section belongs to the course
    section = get_object_or_404(Section, id=idsection, courses=course)

    # Ensure the assessment belongs to the section
    assessment = get_object_or_404(Assessment, id=idassessment, section=section)

    # Initialize forms
    question_form = QuestionForm(request.POST or None, assessment=assessment)
    choice_formset = ChoiceFormSet(request.POST or None, instance=Question())

    # Pass assessment to each form in the formset
    for choice_form in choice_formset.forms:
        choice_form.fields['text'].widget = (
            CKEditor5Widget("extends") if assessment.flag else forms.TextInput(attrs={'class': 'form-control'})
        )

    if request.method == 'POST':
        if question_form.is_valid() and choice_formset.is_valid():
            # Save question instance
            question = question_form.save(commit=False)
            question.section = section
            question.assessment = assessment
            question.save()

            # Link and save choices
            choice_formset.instance = question
            choice_formset.save()

            messages.success(request, "Question and choices created successfully!")

            # Check if 'save and add another' button was clicked
            if 'save_and_add_another' in request.POST:
                return redirect('courses:create_question', idcourse=course.id, idsection=section.id, idassessment=assessment.id)

            # Redirect to a view or list of questions
            return redirect('courses:view-question', idcourse=course.id, idsection=section.id, idassessment=assessment.id)
        else:
            messages.error(request, "There was an error saving the question. Please correct the errors below.")

    # For GET requests or if forms are invalid
    return render(request, 'courses/create_question.html', {
        'course': course,
        'section': section,
        'assessment': assessment,
        'question_form': question_form,
        'choice_formset': choice_formset,
    })



#view question
#@login_required
@csrf_exempt
def question_view(request, idcourse, idsection, idassessment):
    # Check if the user is authenticated
    if not request.user.is_authenticated:
        return redirect("/login/?next=%s" % request.path)
    
    # Determine the course based on the user's role
    if request.user.is_superuser:
        course = get_object_or_404(Course, id=idcourse)
    elif request.user.is_partner:
        # Ensure the course is associated with the partner
        course = get_object_or_404(Course, id=idcourse, org_partner__user_id=request.user.id)
    elif request.user.is_instructor:
        # Ensure the course is associated with the instructor
        course = get_object_or_404(Course, id=idcourse, instructor__user_id=request.user.id)
    else:
        # Unauthorized access
        messages.error(request, "You do not have permission to view questions for this course.")
        return redirect('courses:home')  # Redirect to a safe page

    # Ensure the section belongs to the course
    section = get_object_or_404(Section, id=idsection, courses=course)

    # Ensure the assessment belongs to the section
    assessment = get_object_or_404(
        Assessment.objects.prefetch_related('questions__choices'),
        id=idassessment,
        section=section
    )

    return render(request, 'courses/view_question.html', {
        'course': course,
        'section': section,
        'assessment': assessment,
    })





#upprove user request
#@login_required
def instructor_check(request, instructor_id):
    # Check if the user is authenticated
    if not request.user.is_authenticated:
        return redirect("/login/?next=%s" % request.path)
    # Fetch the instructor object
    instructor = get_object_or_404(Instructor, id=instructor_id)
    
    # Check if the user has permission to approve (e.g., the user must be the provider)
    if request.user.is_partner and instructor.provider.user == request.user:
        # Update instructor status to "Approved"
        instructor.status = 'Approved'
        instructor.save()  # Save the status change

        # Now update the user's `is_partner` field to True
        user = instructor.user  # Get the related User object
        
        # Set is_partner to True
        user.is_instructor = True
        user.save()  # Save the user after the update

        # Success message
        messages.success(request, "Instructor has been approved.")
        
    else:
        # Error message if the user doesn't have permission
        messages.error(request, "You do not have permission to approve this instructor.")

    # Redirect to the instructor list or another page after approval
    return redirect('courses:instructor_view')  # Change this URL to your desired location


#instructor detail
#@login_required
def instructor_detail(request, id):
    # Check if the user is authenticated
    if not request.user.is_authenticated:
        return redirect("/login/?next=%s" % request.path)
    
    # Fetch the instructor object by the provided ID
    instructor = get_object_or_404(Instructor, id=id)

    # Ensure that the instructor has a provider (Partner) with a slug in the related Universiti
    if not instructor.provider or not hasattr(instructor.provider.name, 'slug'):
        # Handle the case where there is no provider or slug
        partner_slug = None
    else:
        partner_slug = instructor.provider.name.slug  # Access slug from Universiti model

    # Get the search term from the GET request (if any)
    search_term = request.GET.get('search', '')

    # Filter courses based on the search term
    courses = instructor.courses.filter(
        Q(course_name__icontains=search_term)  # Search by course name only
    ).order_by('start_date')  # Optional: Order by start date or any other field

    # Get the count of filtered courses
    courses_count = courses.count()

    # Implement pagination: Show 6 courses per page
    paginator = Paginator(courses, 6)

    # Get the current page number from GET params (default to 1 if invalid)
    page_number = request.GET.get('page', 1)  # Default to page 1 if not specified

    # Ensure the page number is a positive integer
    try:
        page_number = int(page_number)
        if page_number < 1:
            page_number = 1  # If the page number is less than 1, set it to 1
    except ValueError:
        page_number = 1  # If the page number is not a valid integer, set it to 1

    # Get the page object
    try:
        page_obj = paginator.get_page(page_number)
    except EmptyPage:
        page_obj = paginator.get_page(1)  # If page number is out of range, show first page

    # Create the context dictionary to pass to the template
    context = {
        'instructor': instructor,
        'page_obj': page_obj,  # Pass the paginated courses to the template
        'courses_count': courses_count,  # Total number of filtered courses
        'search_term': search_term,  # Pass the search query to the template
        'partner_slug': partner_slug,  # Pass the partner slug to the template
    }

    # Render the instructor_detail template with the context
    return render(request, 'instructor/instructor_detail.html', context)

#view instructor
#@login_required

def instructor_view(request):
    # Check if the user is authenticated
    if not request.user.is_authenticated:
        return redirect("/login/?next=%s" % request.path)
    # Check if the user is an admin

    if request.user.is_superuser:  # This checks if the user is an admin

        instructors = Instructor.objects.all()  # Admin sees all instructors

    elif request.user.is_partner:

        # Otherwise, filter based on the user's associated partner or provider

        instructors = Instructor.objects.filter(provider__user=request.user)

    elif request.user.is_instructor:

        messages.error(request, "You do not have permission to view this instructor list.")

        return render(request, 'instructor/instructor_list.html', {'instructors': []})  # Return an empty list or redirect


    else:

        # Handle case where the user does not have any of the above roles

        messages.error(request, "You do not have permission to view this instructor list.")

        return render(request, 'instructor/instructor_list.html', {'instructors': []})  # Return an empty list or redirect


    return render(request, 'instructor/instructor_list.html', {'instructors': instructors})

#delete instructor
#@login_required
def delete_instructor(request, instructor_id):
    # Check if the user is authenticated
    if not request.user.is_authenticated:
        return redirect("/login/?next=%s" % request.path)
   
    # Fetch the instructor object
    instructor = get_object_or_404(Instructor, id=instructor_id)
    
    # Ensure the user has permission to delete the instructor
    if request.user.is_partner and instructor.provider.user == request.user:
        instructor.delete()
        messages.success(request, "Instructor deleted successfully.")
    else:
        messages.error(request, "You do not have permission to delete this instructor.")

    # Redirect to the list of instructors
    return redirect('courses:instructor_view')


#intructor form for new request
#@login_required
def become_instructor(request):
    # Check if the user is authenticated
    if not request.user.is_authenticated:
        return redirect("/login/?next=%s" % request.path)
    # Check if the user is already an instructor
    try:
        application = Instructor.objects.get(user=request.user)
        if application.status == "Pending":
            
            messages.info(request, "Your application is under review.")
        elif application.status == "Approved":
            messages.success(request, "You are already an instructor!")
        return redirect('authentication:dasbord')
    except Instructor.DoesNotExist:
        if request.method == "POST":
            form = InstructorForm(request.POST)
            if form.is_valid():
                application = form.save(commit=False)
                application.user = request.user
                application.save()
                messages.success(request, "Your application has been submitted!")
                return redirect('authentication:dasbord')
        else:
            form = InstructorForm()

    return render(request, 'home/become_instructor.html', {'form': form})

#add course team
#@login_required

def course_team(request, id):
    # Check if the user is authenticated
    if not request.user.is_authenticated:
        return redirect("/login/?next=%s" % request.path)
    # Fetch the course object
    user = request.user

    # Retrieve the course based on the provided ID

    course = get_object_or_404(Course, id=id)


    # Check if the user is either the instructor or an organization partner

    is_instructor = course.instructor is not None and course.instructor.user == user

    is_partner = course.org_partner is not None and course.org_partner.user == user
    is_superuser = user.is_superuser

    if not (is_instructor or is_partner or is_superuser):

        return redirect('/courses')  # Redirect if the user is not authorized


    if request.method == 'POST':

        form = TeamMemberForm(request.POST)

        if form.is_valid():

            email = form.cleaned_data['email']  # Get the email from the form

            try:

                user_instance = User.objects.get(email=email)  # Retrieve the User instance

                team_member = TeamMember(course=course, user=user_instance)

                team_member.save()  # Save the new team member

                return redirect('courses:course_team', id=course.id)

            except User.DoesNotExist:

                form.add_error('email', "No user found with this email.")  # Add an error if user not found

    else:

        form = TeamMemberForm()


    team_members = course.team_members.all()


    return render(request, 'courses/course_team.html', {

        'course': course,

        'form': form,

        'team_members': team_members,

    })
#remove team
#@login_required

def remove_team_member(request, member_id):
    # Check if the user is authenticated
    if not request.user.is_authenticated:
        return redirect("/login/?next=%s" % request.path)
    # Check if the user is authorized to access the course
    team_member = get_object_or_404(TeamMember, id=member_id)

    course_id = team_member.course.id


    # Check if the user is the instructor or the organization partner

    is_instructor = getattr(team_member.course.instructor, 'user', None) == request.user

    is_partner = getattr(team_member.course.org_partner, 'user', None) == request.user
    is_superuser = request.user.is_superuser
    
    if is_instructor or is_partner or is_superuser:

        team_member.delete()  # Remove the team member


    return redirect('courses:course_team', id=course_id)  # Redir

#course profile
@csrf_exempt  # Be cautious with this decorator; it's better to avoid using it if unnecessary
def course_profile(request, id):
    # Check if the user is authenticated
    if not request.user.is_authenticated:
        return redirect("/login/?next=%s" % request.path)
    # Get the course based on the user's role
    user = request.user
    course = None
    # Determine the course based on the user's role
    if request.user.is_superuser:
        course = get_object_or_404(Course, id=id)
    elif user.is_partner:
        #course = Course.objects.filter(id=id, org_partner_id=request.user.id).first()
        course = get_object_or_404(Course, id=id, org_partner__user_id=user.id)
        print(course)
    elif user.is_instructor:
        course = get_object_or_404(Course, id=id, instructor__user_id=user.id)
    # If no course is found, redirect to the courses list page
        print(course)
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
#@login_required
@csrf_exempt
def create_section(request, idcourse):
    # Check if the user is authenticated
    if not request.user.is_authenticated:
        return redirect("/login/?next=%s" % request.path)
    # Get the course based on the user's role
    if request.method == "POST":
        # Check user permissions
        if request.user.is_superuser:
            course = get_object_or_404(Course, id=idcourse)
        elif request.user.is_partner:
            course = get_object_or_404(Course, id=idcourse, org_partner__user_id=request.user.id)
        elif request.user.is_instructor:
            course = get_object_or_404(Course, id=idcourse, instructor__user_id=request.user.id)
        else:
            return JsonResponse({'status': 'error', 'message': 'Permission denied.'})

        form = SectionForm(request.POST)
        if form.is_valid():
            section = form.save(commit=False)
            section.courses = course
            section.save()
            return JsonResponse({'status': 'success', 'message': 'Section created successfully!'})
        else:
            return JsonResponse({'status': 'error', 'message': 'Form is not valid', 'errors': form.errors})

    return JsonResponse({'status': 'error', 'message': 'Invalid request method.'})



# Delete section
#@login_required
@csrf_exempt
def delete_section(request, pk):
    # Check if the user is authenticated
    if not request.user.is_authenticated:
        return redirect("/login/?next=%s" % request.path)
    # Fetch the section
    section = get_object_or_404(Section, pk=pk)
    course = section.courses  # Use the correct relationship field name

    # Check user roles
    if request.user.is_superuser:
        # Superusers can delete any section
        pass
    elif request.user.is_partner:
        # Partners can delete sections only for their associated courses
        if course.org_partner.user_id != request.user.id:
            return JsonResponse({'status': 'error', 'message': 'Permission denied.'})
    elif request.user.is_instructor:
        # Instructors can delete sections only for their own courses
        if course.instructor.user_id != request.user.id:
            return JsonResponse({'status': 'error', 'message': 'Permission denied.'})
    else:
        # Unauthorized user
        return JsonResponse({'status': 'error', 'message': 'Permission denied.'})

    # If role check passes, delete the section
    if request.method == 'POST':
        section.delete()
        return JsonResponse({'status': 'success', 'message': 'Section deleted!'})
    else:
        return JsonResponse({'status': 'error', 'message': 'Invalid request method.'})


# Update Section
# Update Section with Role-Based Access
#@login_required
@csrf_exempt
def update_section(request, pk):
    # Check if the user is authenticated
    if not request.user.is_authenticated:
        return redirect("/login/?next=%s" % request.path)
    # Fetch the section
    section = get_object_or_404(Section, pk=pk)
    course = section.courses  # Use the correct relationship field name

    # Check user roles
    if request.user.is_superuser:
        # Superusers can update any section
        pass
    elif request.user.is_partner:
        # Partners can update sections only for their associated courses
        if course.org_partner.user_id != request.user.id:
            return JsonResponse({'status': 'error', 'message': 'Permission denied.'})
    elif request.user.is_instructor:
        # Instructors can update sections only for their own courses
        if course.instructor.user_id != request.user.id:
            return JsonResponse({'status': 'error', 'message': 'Permission denied.'})
    else:
        # Unauthorized user
        return JsonResponse({'status': 'error', 'message': 'Permission denied.'})

    if request.method == "POST":
        # Handle form submission
        form = SectionForm(request.POST, instance=section)
        if form.is_valid():
            # Save the updated section
            form.save()
            return JsonResponse({'status': 'success', 'message': 'Section updated successfully!'})
        else:
            # Return specific form errors for debugging
            return JsonResponse({'status': 'error', 'message': 'Form is not valid', 'errors': form.errors})
    return JsonResponse({'status': 'error', 'message': 'Invalid request method.'})



#add matrial course
#@login_required
@csrf_exempt
def add_matrial(request, idcourse, idsection):
    # Check if the user is authenticated
    if not request.user.is_authenticated:
        return redirect("/login/?next=%s" % request.path)
    # Determine the course based on the user's role
    if request.user.is_superuser:
        course = get_object_or_404(Course, id=idcourse)
    elif request.user.is_partner:
        # Ensure the course is associated with the partner
        course = get_object_or_404(Course, id=idcourse, org_partner__user_id=request.user.id)
    elif request.user.is_instructor:
        # Ensure the course is associated with the instructor
        course = get_object_or_404(Course, id=idcourse, instructor__user_id=request.user.id,instructor__status='Approved')
    else:
        messages.error(request, "You do not have permission to add materials to this course.")
        return redirect('courses:home')  # Redirect to a safe page for unauthorized users

    # Fetch the section (update the field name to 'courses')
    section = get_object_or_404(Section, id=idsection, courses=course)

    if request.method == 'POST':
        # Handle form submission
        form = MatrialForm(request.POST)  # Include file uploads

        if form.is_valid():
            # Save the material and associate it with the course and section
            material = form.save(commit=False)
            material.section = section
            material.courses = course
            material.save()

            messages.success(request, "Material successfully added to the course.")
            return redirect('courses:studio', id=course.id)
        else:
            # Provide error feedback
            messages.error(request, "Failed to add material. Please check the form for errors.")
            print(form.errors)  # Debugging (optional)

    else:
        # Initialize an empty form for GET requests
        form = MatrialForm()

    # Render the form template
    return render(request, 'courses/course_matrial.html', {
        'form': form,
        'course': course,
        'section': section,
    })


#edit matrial course
#@login_required
@csrf_exempt
def edit_matrial(request, idcourse, idmaterial):
    # Check the role of the user and determine access permissions
    # Check if the user is authenticated
    if not request.user.is_authenticated:
        return redirect("/login/?next=%s" % request.path)
    # Superuser can access and edit any material
    if request.user.is_superuser:
        # Superuser can access any material, get the associated course via section
        material = get_object_or_404(Material, id=idmaterial)
        course = get_object_or_404(Course, id=idcourse)
    
    # Partner can only access materials related to their course
    elif request.user.is_partner:
        course = get_object_or_404(Course, id=idcourse, org_partner__user_id=request.user.id)
        # Ensure the material belongs to the course's section
        material = get_object_or_404(Material, id=idmaterial, section__courses=course)
    
    # Instructor can only access and edit materials related to their courses
    elif request.user.is_instructor:
        course = get_object_or_404(Course, id=idcourse, instructor__user_id=request.user.id)
        # Ensure the material belongs to the course's section
        material = get_object_or_404(Material, id=idmaterial, section__courses=course)
    
    else:
        # Unauthorized access for users who are not superuser, partner, or instructor
        messages.error(request, "You do not have permission to edit materials in this course.")
        return redirect('courses:home')

    # Handle POST request to update the material
    if request.method == 'POST':
        form = MatrialForm(request.POST, request.FILES, instance=material)
        if form.is_valid():
            form.save()  # Save the updated material
            messages.success(request, "Successfully updated material.")
            return redirect('courses:studio', id=course.id)  # Redirect to the course studio page
        else:
            messages.error(request, "Failed to update material. Please check the form for errors.")
            print(form.errors)  # Debugging (optional)
    else:
        # For GET requests, populate the form with existing material
        form = MatrialForm(instance=material)

    # Render the template with the form and context
    return render(request, 'courses/edit_matrial_course.html', {
        'form': form,
        'course': course,
        'material': material,
    })





#delete matrial course
#@login_required
@csrf_exempt
def delete_matrial(request, pk):
    # Check if the user is authenticated
    if not request.user.is_authenticated:
        return redirect("/login/?next=%s" % request.path)
    # Ensure the request is a POST request
    if request.method == 'POST':
        # Fetch the material and its section
        material = get_object_or_404(Material, id=pk)
        section = material.section
        course = section.courses  # Adjust this if the field name is different

        # Check user roles
        if request.user.is_superuser:
            # Superuser can delete any material
            pass
        elif request.user.is_partner:
            # Partner can delete material only for their associated courses
            if not course.org_partner or course.org_partner.user_id != request.user.id:
                return JsonResponse({'status': 'error', 'message': 'Permission denied. You do not own this course.'})
        elif request.user.is_instructor:
            # Instructor can delete material only for their own courses
            if not course.instructor or course.instructor.user_id != request.user.id:
                return JsonResponse({'status': 'error', 'message': 'Permission denied. This is not your course.'})
        else:
            # Unauthorized user
            return JsonResponse({'status': 'error', 'message': 'Permission denied.'})

        # Delete the material if the role check passes
        material.delete()
        return JsonResponse({'status': 'success', 'message': 'Material deleted successfully!'})
    else:
        # Handle invalid request methods
        return JsonResponse({'status': 'error', 'message': 'Invalid request method. Only POST requests are allowed.'})



#course view 
#@login_required
def courseView(request):
    # Check if the user is authenticated
    if not request.user.is_authenticated:
        return redirect("/login/?next=%s" % request.path)
    user = request.user

    if user.is_superuser:

        # Superadmin: Show all courses

        courses = Course.objects.all()

    elif user.is_partner:

        # Partner: Show only their own courses

        courses = Course.objects.filter(org_partner__user=user)  # Use org_partner to filter

    elif user.is_instructor:

        # Instructor: Show only their own courses

        courses = Course.objects.filter(instructor__user=user, instructor__status='Approved')  # Assuming instructor is related to user
       # print(courses)

    else:

        # Optionally handle other user types or set courses to none

        courses = Course.objects.none()

    search_query = request.GET.get('search', '').strip()
    if search_query:
        courses = courses.filter(course_name__icontains=search_query)
    courses = courses.order_by('-id')  # To order by ascending order
    # Fetch only necessary fields
    #courses = courses.values('id', 'course_name', 'course_number','course_run','org_partner__name','status_course')
    #courses = courses.annotate(org_partner_name=F('org_partner__name')).values('id', 'course_name', 'course_number', 'course_run', 'org_partner__name__name', 'status_course')
    courses = courses.annotate(
        org_partner_name=F('org_partner__name__name'),  # Resolve partner's name
        instructor_email=F('instructor__user__email')  # Annotate instructor email
    ).values(
        'id',
        'course_name',
        'course_number',
        'instructor_email',  # Use the annotation name
        'org_partner_name',  # Use the partner name annotation
        'status_course',
        'course_run'
    ).order_by('-id')

    #print(courses)
    #print(courses)
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
#@login_required

def course_create_view(request):
    # Check if the user is authenticated
    if not request.user.is_authenticated:
        return redirect("/login/?next=%s" % request.path)
    if request.user.is_partner or request.user.is_superuser or request.user.is_instructor:

        if request.method == 'POST':

            form = CourseForm(request.POST, user=request.user)  # Pass the logged-in user to the form

            if form.is_valid():

                course = form.save(commit=False)  # Create a Course instance but don't save to the database yet


                # Set the author to the logged-in user

                course.author = request.user
                

                  # If the user is a partner or superuser, set the org_partner

                if  request.user.is_superuser:

                    partner = form.cleaned_data['org_partner']  # Get the selected partner from the form

                    course.org_partner = partner  # Set the partner for the course

                # If the user is a partner or superuser, set the org_partner

                if request.user.is_partner :

                    partner = form.cleaned_data['org_partner']  # Get the selected partner from the form

                    course.org_partner = partner  # Set the partner for the course


                # If the user is an instructor, set the instructor

                if request.user.is_instructor:

                     instructor = Instructor.objects.get(user=request.user)  # Assuming a one-to-one relationship

                     course.instructor = instructor 

                # Save the course instance to the database

                course.save()

                return redirect('/courses')  # Redirect to a course list page or success page

            else:

                print(form.errors)  # Print form errors to the console for debugging

        else:

            form = CourseForm(user=request.user)  # Pass the logged-in user to the form

    else:

        return redirect('/courses')
    


    return render(request, 'courses/course_add.html', {'form': form})

#studio detail courses

def studio(request, id):
    # Check if the user is authenticated
    if not request.user.is_authenticated:
        return redirect("/login/?next=%s" % request.path)
    user = request.user
    course = None

  
    # Determine the course based on the user's role
    if request.user.is_superuser:
        course = get_object_or_404(Course, id=id)
    elif user.is_partner:
        #course = Course.objects.filter(id=id, org_partner_id=request.user.id).first()
        course = get_object_or_404(Course, id=id, org_partner__user_id=user.id)
        #print(course)
    elif user.is_instructor:
        course = get_object_or_404(Course, id=id, instructor__user_id=user.id)
    # If no course is found, redirect to the courses list page
        #print(course)
    if not course:
        return redirect('/courses')

    # Fetch sections related to the specific course
    #section = Section.objects.filter(parent=None, courses_id=course.id)
    #section = Section.objects.filter(parent=None, courses=course).prefetch_related('materials')
    #section = Section.objects.filter(parent=None, courses=course).prefetch_related('questions')
    section = Section.objects.filter(
    parent=None, courses=course
).prefetch_related('materials', 'assessments')  # Add all necessary relationships

    # Render the page with the course and sections data
    return render(request, 'courses/course_detail.html', {'course': course, 'section': section})



#update_partner

def convert_image_to_webp(uploaded_image):
    """
    Konversi gambar yang diunggah ke format WebP dan kembalikan ContentFile
    """
    img = Image.open(uploaded_image)

    # Pastikan gambar berada dalam mode RGB
    img = img.convert('RGB')

    # Simpan gambar ke buffer dalam format WebP
    buffer = BytesIO()
    img.save(buffer, format='WEBP', quality=85)  # Adjust kualitas sesuai kebutuhan
    buffer.seek(0)

    # Kembalikan file dalam format ContentFile
    return ContentFile(buffer.read(), name='logo.webp')


def update_partner(request, partner_id):
    # Ambil partner dan pastikan user memiliki otoritas
    partner = get_object_or_404(Partner, pk=partner_id)

    # Cek otoritas user
    if not request.user.is_authenticated or (request.user != partner.user and not request.user.is_superuser):
        return redirect("/login/?next=%s" % request.path)

    old_logo = partner.logo.path if partner.logo else None  # Simpan path logo lama

    if request.method == "POST":
        form = PartnerFormUpdate(request.POST, request.FILES, instance=partner, user=request.user)
        if form.is_valid():
            partner_instance = form.save(commit=False)

            # Jika ada logo baru yang diunggah, konversi ke WebP
            if 'logo' in request.FILES:
                uploaded_logo = request.FILES['logo']
                converted_logo = convert_image_to_webp(uploaded_logo)
                partner_instance.logo = converted_logo

            # Simpan perubahan ke instance Partner
            partner_instance.save()

            # Hapus logo lama jika ada dan sudah diganti
            if old_logo and old_logo != partner.logo.path:
                if os.path.exists(old_logo):
                    os.remove(old_logo)

            return redirect('courses:partner_detail', partner_id=partner.id)
    else:
        form = PartnerFormUpdate(instance=partner, user=request.user)

    return render(request, 'partner/update_partner.html', {'form': form, 'partner': partner})
#partner view
#@cache_page(60 * 5)

def partnerView(request):
    if not request.user.is_authenticated:
        return redirect("/login/?next=%s" % request.path)

    # Get the search query from the GET request
    query = request.GET.get('q', '')

    # Superusers see all partners, others see only their own
    posts = Partner.objects.all() if request.user.is_superuser else Partner.objects.filter(user_id=request.user.id)

    # Apply the search filter if the query is provided
    if query:
        posts = posts.filter(
            Q(name__name__icontains=query) |  # Filter by the 'name' field inside the related Univer model
            Q(user__email__icontains=query) |  # Filter by email of the related User model
            Q(phone__icontains=query)  # Filter by phone number
        )

    # Pagination: Ensure to paginate before fetching data
    paginator = Paginator(posts, 10)  # Show 10 posts per page
    page_number = request.GET.get('page')
    page = paginator.get_page(page_number)

    # Context to send to template
    context = {
        'count': posts.count(),  # Total number of partners
        'page': page,  # Current page object for pagination
        'query': query  # Pass the query to the template for display in search input
    }

    return render(request, 'partner/partner_view.html', context)


#detail_partner
def partner_detail(request, partner_id):
    # Retrieve the partner using the provided partner_id
    partner = get_object_or_404(Partner, id=partner_id)

    # Get the search query and category filter from the request
    search_query = request.GET.get('search', '')
    selected_category = request.GET.get('category', '')
    sort_by = request.GET.get('sort_by', 'name')

    # Filter courses related to the partner
    related_courses = Course.objects.filter(org_partner_id=partner.id)

    # Apply search filter if provided
    if search_query:
        related_courses = related_courses.filter(course_name__icontains=search_query)

    # Apply category filter if provided
    if selected_category:
        related_courses = related_courses.filter(category__name=selected_category)

    # Sort the courses based on the sort_by value
    if sort_by == 'name':
        related_courses = related_courses.order_by('course_name')
    elif sort_by == 'date':
        related_courses = related_courses.order_by('created_at')
    elif sort_by == 'learners':
        related_courses = related_courses.annotate(learner_count=Count('enrollments')).order_by('-learner_count')
    elif sort_by == 'status':
        related_courses = related_courses.order_by('status_course')

    # Count the total number of related courses
    total_courses = related_courses.count()

    # Group courses by category (if category field exists)
    grouped_courses = {}
    for course in related_courses:
        category_name = course.category.name if course.category else 'Uncategorized'
        if category_name not in grouped_courses:
            grouped_courses[category_name] = []
        grouped_courses[category_name].append(course)

    # Fetch categories that have courses linked to this partner
    categories_with_courses = Category.objects.filter(category_courses__org_partner_id=partner.id).distinct()

    # Pagination setup
    page_number = request.GET.get('page')
    paginator = Paginator(related_courses, 10)
    page_obj = paginator.get_page(page_number)

    # Context data
    context = {
        'partner': partner,
        'page_obj': page_obj,
        'total_courses': total_courses,
        'search_query': search_query,
        'grouped_courses': grouped_courses,
        'selected_category': selected_category,
        'categories': categories_with_courses,  # Only categories with courses
        'sort_by': sort_by
    }

    return render(request, 'partner/partner_detail.html', context)



#org partner from lms
def org_partner(request, slug):
    # Retrieve the partner using the provided slug of the Universiti model
    partner = get_object_or_404(Partner, name__slug=slug)  # Use name__slug to access the slug in the Universiti model

    # Get the search query and category filter from the request
    search_query = request.GET.get('search', '')  # Default to empty string if no search query
    selected_category = request.GET.get('category', '')  # Category filter
    sort_by = request.GET.get('sort_by', 'name')  # Default sort by course name

    # Filter courses related to the partner, with status 'published' and end_date in the future
    related_courses = Course.objects.filter(
        org_partner_id=partner.id,
        status_course='published',
        end_date__gte=datetime.now()
    )

    # Apply search filter if provided
    if search_query:
        related_courses = related_courses.filter(course_name__icontains=search_query)

    # Apply category filter if provided
    if selected_category:
        related_courses = related_courses.filter(category__name=selected_category)

    # Sort the courses based on the sort_by value
    if sort_by == 'name':
        related_courses = related_courses.order_by('course_name')
    elif sort_by == 'date':
        related_courses = related_courses.order_by('created_at')  # Assuming 'created_at' is a field
    elif sort_by == 'learners':
        # Count the number of learners (enrollments) and sort by that
        related_courses = related_courses.annotate(learner_count=Count('enrollments')).order_by('-learner_count')

    # Count the total number of related courses after applying filters
    total_courses = related_courses.count()

    # Group courses by category (if category field exists)
    grouped_courses = {}
    for course in related_courses:
        category_name = course.category.name if course.category else 'Uncategorized'
        if category_name not in grouped_courses:
            grouped_courses[category_name] = []
        grouped_courses[category_name].append(course)

    # Implement server-side pagination
    page_number = request.GET.get('page')  # Get the page number from the request
    paginator = Paginator(related_courses, 10)  # Show 10 courses per page

    # Get the current page of courses
    page_obj = paginator.get_page(page_number)

    # Create context dictionary to pass to the template
    context = {
        'partner': partner,
        'page_obj': page_obj,  # Pass the paginated courses to the template
        'total_courses': total_courses,  # Pass the total course count to the template
        'search_query': search_query,  # Pass the search query to the template
        'grouped_courses': grouped_courses,  # Pass grouped courses by category
        'selected_category': selected_category,  # Pass the selected category to the template
        'categories': Category.objects.all(),  # Pass all categories to the template
        'sort_by': sort_by  # Pass the sort_by parameter to the template
    }

    # Render the partner_detail template with the partner and related courses data
    return render(request, 'partner/org_partner.html', context)



#search user
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
#search partner
def search_partner(request):
    query = request.GET.get('q', '')
    
    # If query is empty, return no users or all active users (depending on your use case)
    if query:
        partners = Universiti.objects.filter(
        Q(name__icontains=query) | Q(email__icontains=query)
    ).only('id', 'name', 'email')
    else:
        partners = Universiti.objects.filter(Q(name__icontains=query)).only('id', 'name')

    # Optional: Implement pagination (if needed)
    paginator = Paginator(partners, 20)  # Show 20 users per page
    page_number = request.GET.get('page')  # Get the page number from the query params
    page_obj = paginator.get_page(page_number)

    # Prepare data for response
    partners_data = [{'id': universiti.id, 'text': universiti.name} for universiti in page_obj]

    return JsonResponse({
        'partners': partners_data,
        'page': page_obj.number,
        'total_pages': paginator.num_pages,
        'total_partners': paginator.count,
    })




def partner_create_view(request):
    if not request.user.is_superuser:
     return redirect('/')

    if request.method == 'POST':
        form = PartnerForm(request.POST)  # Pass the logged-in user to the form
        if form.is_valid():
            form = form.save(commit=False)
            form.author_id = request.user.id
            form.save()  # Save the course with the selected partner
                  # Now update the user's `is_partner` field to True
            user = form.user  # Get the related User object

            # Set is_partner to True
            user.is_partner = True
            user.save()  # Save the user after the update
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

