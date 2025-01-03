# forms.py
import re
from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm, PasswordResetForm, SetPasswordForm,UserChangeForm
from django.contrib.auth.models import User
from django.forms import ModelForm

class Userprofile(forms.ModelForm):
    
    class Meta:
        model = User
        fields = [
        'first_name', 'last_name', 'email', 
        'hobby', 'birth', 'address', 'country', 
        'phone', 'gender', 'education','university','photo'
        ]

        
        widgets = {
            
            'first_name': forms.TextInput(attrs={'class': 'form-control', 'type': 'text'}),  
            'last_name': forms.TextInput(attrs={'class': 'form-control', 'type': 'text'}), 
            'email': forms.EmailInput(attrs={'class': 'form-control', 'type': 'email'}),   
            'hobby': forms.TextInput(attrs={'class': 'form-control', 'type': 'text'}),     
            'birth': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'address': forms.Textarea(attrs={'class': 'form-control', 'type': 'text','rows':4}),
            'country': forms.TextInput(attrs={'class': 'form-control', 'type': 'text'}),
            'phone': forms.TextInput(attrs={'class': 'form-control', 'type': 'text'}), 
            'gender': forms.Select(attrs={'class': 'form-control', 'type': 'text'}), 
            'education': forms.Select(attrs={'class': 'form-control', 'type': 'text'}), 
            'university': forms.Select(attrs={'class': 'form-control', 'type': 'text'}),
            
            
        }
        def clean_phone(self):

            phone = self.cleaned_data.get('phone')

            if phone:

                # Example regex for validating phone numbers (adjust as needed)

                if not re.match(r'^\+?1?\d{9,15}$', phone):

                    raise forms.ValidationError("Invalid phone number format. Please enter a valid phone number.")

            return phone
        
    def __init__(self, *args, **kwargs):
        super(Userprofile, self).__init__(*args, **kwargs)


       
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
