from django import forms
from captcha.fields import CaptchaField
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm, PasswordResetForm, SetPasswordForm,UserChangeForm
from authentication.models import CustomUser, Universiti
import re
from .models import CustomUser
from django.core.exceptions import ValidationError

class RegistrationForm(forms.ModelForm):
    password1 = forms.CharField(
        label="Password",  # Ubah label di sini
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Enter your password'})
    )
    password2 = forms.CharField(
        label="Confirm Password",  # Ubah label di sini
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Confirm your password'})
    )
    captcha = CaptchaField()  # This assumes you have django-recaptcha installed

    class Meta:
        model = CustomUser
        fields = ['email', 'username', 'password1', 'password2', 'captcha']

        widgets = {
            'email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'Enter your email'}),
            'username': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter your username'}),
            # password widgets are already added above
        }

    def clean_password2(self):
        password1 = self.cleaned_data.get("password1")
        password2 = self.cleaned_data.get("password2")
        if password1 != password2:
            raise ValidationError("Passwords don't match.")
        return password2



class LoginForm(forms.Form):
    email = forms.EmailField(
    widget=forms.EmailInput(attrs={'placeholder': 'Enter your email', 'class': 'form-control'})
    )
    password = forms.CharField(
    widget=forms.PasswordInput(attrs={'placeholder': 'Enter your password', 'class': 'form-control'})
    )
    captcha = CaptchaField()  # Add the captcha field here




class Userprofile(forms.ModelForm):
    
    class Meta:
        model = CustomUser
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

        model = CustomUser

        fields = ['photo']


    def __init__(self, *args, **kwargs):

        super(UserPhoto, self).__init__(*args, **kwargs)  # Correct superclass call

        self.fields['photo'].widget.attrs.update({

            'class': 'form-control',

            'placeholder': 'Upload your photo',  # More relevant placeholder

            'required': True  # Set required as a boolean

        })