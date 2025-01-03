from django.shortcuts import render, get_object_or_404

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User

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
from courses.models import Instructor
from django.http import HttpResponse,JsonResponse


# Create your views here.


def home(request):
    return render(request,'home/index.html')

def dasbord(request):
    
    return render(request,'home/dasbord.html')

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
    

@login_required

def edit_photo(request, pk):

    # Retrieve the user instance based on the primary key

    user = get_object_or_404(User, pk=pk)


    if request.method == "GET":

        # Render the form with the user's current data

        form = UserPhoto(instance=user)

        return render(request, 'home/edit_photo.html', {'form': form})


    elif request.method == "POST":

        # Populate the form with POST data and the user instance

        form = UserPhoto(request.POST, request.FILES, instance=user)

        if form.is_valid():

            # Save the form but do not commit to the database yet

            user_profile = form.save(commit=False)

            if not request.FILES.get('photo'):

                # If no new photo, keep the existing one

                user_profile.photo = user.photo  # Use the existing user's photo

            user_profile.save()  # Now save the user profile

            #return JsonResponse({'success': True, 'message': 'Profile updated successfully!'})
            return redirect('authentication:dasbord')

        else:

            # If the form is invalid, re-render the form with errors

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
    
    
