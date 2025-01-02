from django.contrib.auth.forms import AuthenticationForm, UserCreationForm, PasswordResetForm, SetPasswordForm,UserChangeForm
from django.contrib.auth.models import User
from django.forms import forms
from django.forms import ModelForm

class Userprofile(UserChangeForm):
    class Meta:
        model = User
        fields = [
            'first_name', 'last_name', 'email', 
            'hobby', 'birth', 'address', 'country', 
            'phone', 'gender', 'education','university','photo'
        ]
    def __init__(self, *args, **kwargs):
        super(UserChangeForm, self).__init__(*args, **kwargs)
        self.fields['first_name'].widget.attrs.update({
            'class': 'form-control',
            'placeholder': 'first',
            'required': 'True'
        })
        self.fields['last_name'].widget.attrs.update({
            'class': 'form-control',
            'placeholder': 'last',
            'required': 'True'
        })
        self.fields['email'].widget.attrs.update({
            'class': 'form-control',
            'placeholder': 'email',
            'required': 'True',
            'type':'email'
        })
        self.fields['hobby'].widget.attrs.update({
            'class': 'form-control',
            'placeholder': 'hobby',
            'required': 'True'
        })
        self.fields['address'].widget.attrs.update({
        'class': 'form-control',
        'placeholder': 'address',
        'required': 'True'
        })
        self.fields['birth'].widget.attrs.update({
            'class': 'form-control',
            'placeholder': 'tai',
            'required': 'True',
            'type': 'date'
        })
        self.fields['country'].widget.attrs.update({
        'class': 'form-control',
        'placeholder': 'country',
        'required': 'True'
        })
        self.fields['phone'].widget.attrs.update({
        'class': 'form-control',
        'placeholder': 'phone',
        'required': 'True'
        })
        self.fields['gender'].widget.attrs.update({
        'class': 'form-control',
        'placeholder': 'gender',
        'required': 'True'
        })
        self.fields['education'].widget.attrs.update({
        'class': 'form-control',
        'placeholder': 'education',
        'required': 'True'
        })
        self.fields['university'].widget.attrs.update({
        'class': 'form-control select1',
        'placeholder': 'university',
        'required': 'True'
        })
       
class UserPhoto(UserChangeForm):

    class Meta:

        model = User

        fields = ['photo']


    def __init__(self, *args, **kwargs):

        super(UserPhoto, self).__init__(*args, **kwargs)  # Correct superclass call

        self.fields['photo'].widget.attrs.update({

            'class': 'form-control',

            'placeholder': 'Upload your photo',  # More relevant placeholder

            'required': True  # Set required as a boolean

        })
       


# uncomment this if you want to change the class/design of the login form
class UserLoginForm(AuthenticationForm):
    class Meta:
        model = User
        fields = ['username', 'password']

    def __init__(self, *args, **kwargs):
        super(UserLoginForm, self).__init__(*args, **kwargs)
        self.fields['username'].widget.attrs.update({
            'class': 'form-control',
            'placeholder': 'email',
            'required': 'True'
        })
        self.fields['password'].widget.attrs.update({
            'class': 'form-control',
            'placeholder': 'Password',
            'required': 'True'
        })



# Customizing Registration Form from UserCreationForm
class UserRegistrationForm(UserCreationForm):
    class Meta:
        model = User
        fields = ['username','email', 'password1', 'password2']

    # uncomment this if you want to change the class/design of the registration form inputs
    def __init__(self, *args, **kwargs):
        super(UserRegistrationForm, self).__init__(*args, **kwargs)
        self.fields['username'].widget.attrs.update({
            'class': 'form-control',
            'placeholder': 'username',
            'required': 'True'
        })
        self.fields['email'].widget.attrs.update({
            'class': 'form-control',
            'placeholder': 'Email',
            'required': 'True'
        })
        self.fields['password1'].widget.attrs.update({
            'class': 'form-control',
            'placeholder': 'Password',
            'required': 'True'
        })
        self.fields['password2'].widget.attrs.update({
            'class': 'form-control',
            'placeholder': 'Retype Password',
            'required': 'True'
        })


class ResetPasswordForm(PasswordResetForm):
    class Meta:
        model = User
        fields = ['email']

    def __init__(self, *args, **kwargs):
        super(ResetPasswordForm, self).__init__(*args, **kwargs)
        self.fields['email'].widget.attrs.update({
            'class': 'form-control',
            'placeholder': 'Email',
            'required': 'True'
        })


class ResetPasswordConfirmForm(SetPasswordForm):
    class Meta:
        model = User
        fields = ['new_password1', 'new_password2']

    def __init__(self, *args, **kwargs):
        super(ResetPasswordConfirmForm, self).__init__(*args, **kwargs)
        self.fields['new_password1'].widget.attrs.update({
            'class': 'form-control',
            'placeholder': 'New Password',
            'required': 'True'
        })
        self.fields['new_password2'].widget.attrs.update({
            'class': 'form-control',
            'placeholder': 'Retype New Password',
            'required': 'True'
        })
