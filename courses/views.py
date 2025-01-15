from django.shortcuts import render, redirect, get_object_or_404
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.db.models import Q
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required
from .forms import CourseForm, PartnerForm, SectionForm, ProfilForm,InstructorForm,InstructorAddCoruseForm,TeamMemberForm, MatrialForm,QuestionForm,ChoiceFormSet,AssessmentForm
from django.http import JsonResponse
from .models import Course, Partner, Section,Instructor,TeamMember,Material,Question,Assessment
from django.contrib.auth.models import User,Univer
from django.template.loader import render_to_string
from django.views.decorators.cache import cache_page
from django.urls import reverse
from django.contrib import messages
from django.db.models import F

from django_ckeditor_5.widgets import CKEditor5Widget
from django import forms

#creat assesment
@login_required
@csrf_exempt
def create_assessment(request, idcourse, idsection):
    course = get_object_or_404(Course, id=idcourse)
    section = get_object_or_404(Section, id=idsection)
    
    
    if request.method == 'POST':
        form = AssessmentForm(request.POST)
        if form.is_valid():
            # Create the assessment instance but don't save it yet
            assessment = form.save(commit=False)
            # Set the section field
            assessment.section = section
            # Save the assessment
            assessment.save()
            messages.success(request, "Assessment created successfully!")
            return redirect('courses:studio',id=course.id)
    else:
        form = AssessmentForm()
    
    return render(request, 'courses/course_assessement.html', {'form': form, 'course': course, 'section': section})

#edit assesment
@login_required
@csrf_exempt
def edit_assessment(request, idcourse, idsection, idassessment):
    course = get_object_or_404(Course, id=idcourse)
    section = get_object_or_404(Section, id=idsection)
    assessment = get_object_or_404(Assessment, id=idassessment)

    if request.method == 'POST':
        form = AssessmentForm(request.POST, instance=assessment)
        if form.is_valid():
            # Save the form data to the assessment instance
           
            form.save()
            messages.success(request, "Assessment updated successfully!")
            return redirect('courses:studio', id=course.id)
    else:
        # Populate the form with the existing assessment data
        form = AssessmentForm(instance=assessment)

    return render(request, 'courses/course_assessement_edit.html', {
        'form': form,
        'course': course,
        'section': section,
        'assessment': assessment
    })

#edit question
@login_required
def edit_question(request, idcourse, idquestion, idsection, idassessment):
    course = get_object_or_404(Course, id=idcourse)
    question = get_object_or_404(Question, id=idquestion)
    section = get_object_or_404(Section, id=idsection)
    assessment = get_object_or_404(Assessment, id=idassessment)

    # Pass the assessment to the forms
    form = QuestionForm(request.POST or None, instance=question, assessment=assessment)
    choice_formset = ChoiceFormSet(request.POST or None, instance=question)

    # Pass assessment to each form in the formset
    for choice_form in choice_formset.forms:
        choice_form.fields['text'].widget = (
            CKEditor5Widget("default") if assessment.flag else forms.TextInput(attrs={'class': 'form-control'})
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

#create question
@login_required
def create_question_view(request, idcourse, idsection, idassessment):
    course = get_object_or_404(Course, id=idcourse)
    section = get_object_or_404(Section, id=idsection)
    assessment = get_object_or_404(Assessment, id=idassessment)

    # Pass the assessment object to the form
    question_form = QuestionForm(request.POST or None, assessment=assessment)
    choice_formset = ChoiceFormSet(request.POST or None, instance=Question())

    # Pass the assessment object to each form in the formset
    for choice_form in choice_formset.forms:
        choice_form.fields['text'].widget = (
            CKEditor5Widget("default") if assessment.flag else forms.TextInput(attrs={'class': 'form-control'})
        )

    if request.method == 'POST':
        if question_form.is_valid() and choice_formset.is_valid():
            # Save the question and link it to the section
            question = question_form.save(commit=False)
            question.section = section
            question.save()

            # Save the related choices
            choice_formset.instance = question
            choice_formset.save()

            messages.success(request, "Question and choices created successfully!")

            # Check for "save and add another" button
            if 'save_and_add_another' in request.POST:
                return redirect('courses:create-question', idcourse=course.id, idsection=section.id, idassessment=assessment.id)

            # Redirect to a success page (or list view)
            return redirect('courses:view-question', idcourse=course.id, idsection=section.id, idassessment=assessment.id)

    return render(request, 'courses/create_question.html', {
        'course': course,
        'section': section,
        'question_form': question_form,
        'choice_formset': choice_formset,
    })


#create question
@login_required
def question_view(request, idcourse,idsection, idassessment):
    course = get_object_or_404(Course, id=idcourse)
    section = get_object_or_404(Section, id=idsection)
    assessment = get_object_or_404(Assessment, id=idassessment)

   
    assessment = get_object_or_404(Assessment.objects.prefetch_related('questions__choices'), id=idassessment)
   

    return render(request, 'courses/view_question.html', {
        'course': course,
        'section': section,
        'assessment': assessment,
        
    })


#add quiz
@login_required

def add_quiz (request,idcourse, idsection):
    course = get_object_or_404(Course, id=idcourse)

    section = get_object_or_404(Section, id=idsection)


    if request.method == 'POST':

        form = MatrialForm(request.POST)  # Include request.FILES for file uploads

        if form.is_valid():

            material = form.save(commit=False)

            material.section = section  # Associate the material with the section

            material.courses = course  # Associate the material with the course

            material.save()
            messages.success(request, "sucess add matrial course.")
            return redirect('courses:studio',id=course.id)

        else:
            messages.error(request, "canot add matrial.")
            #return JsonResponse({'status': 'error', 'errors': form.errors})


    # If GET request, render the form

    form = MatrialForm()

    return render(request, 'courses/course_matrial.html', {'form': form, 'course': course, 'section': section})


#upprove user
@login_required
def instructor_check(request, instructor_id):
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
@login_required
def instructor_detail(request, id):
    instructor = get_object_or_404(Instructor, id=id)
    return render(request, 'instructor/instructor_detail.html', {'instructor': instructor})

#view instructor
@login_required

def instructor_view(request):

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
@login_required
def delete_instructor(request, instructor_id):
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


#intructor form
@login_required
def become_instructor(request):
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


@login_required

def course_team(request, id):

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
@login_required

def remove_team_member(request, member_id):

    team_member = get_object_or_404(TeamMember, id=member_id)

    course_id = team_member.course.id


    # Check if the user is the instructor or the organization partner

    is_instructor = getattr(team_member.course.instructor, 'user', None) == request.user

    is_partner = getattr(team_member.course.org_partner, 'user', None) == request.user
    is_superuser = request.user.is_superuser
    
    if is_instructor or is_partner or is_superuser:

        team_member.delete()  # Remove the team member


    return redirect('courses:course_team', id=course_id)  # Redir

#coruse profile
@csrf_exempt  # Be cautious with this decorator; it's better to avoid using it if unnecessary
def course_profile(request, id):
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

#add matrial course
@login_required
@csrf_exempt
def add_matrial(request,idcourse, idsection):
    course = get_object_or_404(Course, id=idcourse)

    section = get_object_or_404(Section, id=idsection)


    if request.method == 'POST':

        form = MatrialForm(request.POST)  # Include request.FILES for file uploads

        if form.is_valid():

            material = form.save(commit=False)

            material.section = section  # Associate the material with the section

            material.courses = course  # Associate the material with the course

            material.save()
            messages.success(request, "sucess add matrial course.")
            return redirect('courses:studio',id=course.id)

        else:
            messages.error(request, "canot add matrial.")
            #return JsonResponse({'status': 'error', 'errors': form.errors})


    # If GET request, render the form

    form = MatrialForm()

    return render(request, 'courses/course_matrial.html', {'form': form, 'course': course, 'section': section})

#edit matrial
@login_required

@csrf_exempt

def edit_matrial(request, idcourse,idmaterial):

    course = get_object_or_404(Course, id=idcourse)

    material = get_object_or_404(Material, id=idmaterial)  # Use Material model to get the material

    print(f"Editing Material ID: {idmaterial}, Course ID: {idcourse}")  # Debugging line
    section = material.section  # Get the associated section


    if request.method == 'POST':

        form = MatrialForm(request.POST, request.FILES, instance=material)  # Populate the form with the existing material

        if form.is_valid():

            form.save()  # Save the updated material

            messages.success(request, "Successfully updated material.")

            return redirect('courses:studio', id=course.id)  # Redirect to the course studio page

        else:

            messages.error(request, "Cannot update material.")

    else:

        form = MatrialForm(instance=material)  # Populate the form with the existing material


    return render(request, 'courses/edit_matrial_course.html', {

        'form': form,

        'course': course,

        'section': section,

        'material': material

    })

#delete matrial course
@login_required

@csrf_exempt

def delete_matrial(request, pk):

    # Ensure the request is a POST request

    if request.method == 'POST':

        item = get_object_or_404(Material, id=pk)

        item.delete()

        return JsonResponse({'status': 'success', 'message': 'Material deleted!'})

    else:

        return JsonResponse({'status': 'error', 'message': 'Invalid request method.'})

def courseView(request):
    # Check if the user is authenticated
    if not request.user.is_authenticated:
        return redirect('/')
    user = request.user

    if user.is_superuser:

        # Superadmin: Show all courses

        courses = Course.objects.all()

    elif user.is_partner:

        # Partner: Show only their own courses

        courses = Course.objects.filter(org_partner__user=user)  # Use org_partner to filter

    elif user.is_instructor:

        # Instructor: Show only their own courses

        courses = Course.objects.filter(instructor__user=user)  # Assuming instructor is related to user

    else:

        # Optionally handle other user types or set courses to none

        courses = Course.objects.none()

    search_query = request.GET.get('search', '').strip()
    if search_query:
        courses = courses.filter(course_name__icontains=search_query)
    courses = courses.order_by('-id')  # To order by ascending order
    # Fetch only necessary fields
    #courses = courses.values('id', 'course_name', 'course_number','course_run','org_partner__name','status_course')
    courses = courses.annotate(org_partner_name=F('org_partner__name')).values('id', 'course_name', 'course_number', 'course_run', 'org_partner__name__name', 'status_course')
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
@login_required

def course_create_view(request):

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
).prefetch_related('materials', 'assesments')  # Add all necessary relationships

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
def search_partner(request):
    query = request.GET.get('q', '')
    
    # If query is empty, return no users or all active users (depending on your use case)
    if query:
        partners = Univer.objects.filter(Q(name__icontains=query)).only('id', 'name')
    else:
        partners = Univer.objects.filter(Q(name__icontains=query)).only('id', 'name')

    # Optional: Implement pagination (if needed)
    paginator = Paginator(partners, 20)  # Show 20 users per page
    page_number = request.GET.get('page')  # Get the page number from the query params
    page_obj = paginator.get_page(page_number)

    # Prepare data for response
    partners_data = [{'id': univer.id, 'text': univer.name} for univer in page_obj]

    return JsonResponse({
        'partners': partners_data,
        'page': page_obj.number,
        'total_pages': paginator.num_pages,
        'total_partners': paginator.count,
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
