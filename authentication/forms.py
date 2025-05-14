from django import forms
from captcha.fields import CaptchaField
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm, PasswordResetForm, SetPasswordForm,UserChangeForm
from authentication.models import CustomUser, Universiti
import re
from .models import CustomUser
from django.core.exceptions import ValidationError
import imghdr

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
            'first_name', 'last_name', 'email', 'phone', 'gender', 'birth',
            'country', 'photo', 'address', 'hobby', 'education', 'university',
            'tiktok', 'youtube', 'facebook', 'instagram', 'linkedin', 'twitter'
        ]
        widgets = {
            'first_name': forms.TextInput(attrs={'class': 'form-control', 'required': True}),
            'last_name': forms.TextInput(attrs={'class': 'form-control', 'required': True}),
            'email': forms.EmailInput(attrs={'class': 'form-control', 'required': True}),
            'phone': forms.TextInput(attrs={'class': 'form-control', 'required': True}),
            'gender': forms.Select(attrs={'class': 'form-select', 'required': True}),
            'birth': forms.DateInput(attrs={'class': 'form-control', 'type': 'date', 'required': True}),
            'country': forms.Select(attrs={'class': 'form-select'}),
            'photo': forms.FileInput(attrs={'class': 'form-control'}),
            'address': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
            'hobby': forms.TextInput(attrs={'class': 'form-control'}),
            'education': forms.Select(attrs={'class': 'form-select'}),
            'university': forms.Select(attrs={'class': 'form-select'}),
            'tiktok': forms.URLInput(attrs={'class': 'form-control'}),
            'youtube': forms.URLInput(attrs={'class': 'form-control'}),
            'facebook': forms.URLInput(attrs={'class': 'form-control'}),
            'instagram': forms.URLInput(attrs={'class': 'form-control'}),
            'linkedin': forms.URLInput(attrs={'class': 'form-control'}),
            'twitter': forms.URLInput(attrs={'class': 'form-control'}),
        }
        labels = {
            'first_name': 'Nama Depan',
            'last_name': 'Nama Belakang',
            'email': 'Email',
            'phone': 'Nomor Telepon',
            'gender': 'Jenis Kelamin',
            'birth': 'Tanggal Lahir',
            'country': 'Negara',
            'photo': 'Foto Profil',
            'address': 'Alamat',
            'hobby': 'Hobi',
            'education': 'Pendidikan',
            'university': 'Universitas',
            'tiktok': 'TikTok',
            'youtube': 'YouTube',
            'facebook': 'Facebook',
            'instagram': 'Instagram',
            'linkedin': 'LinkedIn',
            'twitter': 'Twitter',
        }

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if CustomUser.objects.filter(email=email).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError("Email ini sudah digunakan.")
        return email

    def clean_phone(self):
        phone = self.cleaned_data.get('phone')
        if not phone:
            raise forms.ValidationError("Nomor telepon wajib diisi.")
        import re
        if not re.match(r'^\+?\d{8,15}$', phone):
            raise forms.ValidationError("Nomor telepon tidak valid.")
        return phone

    def clean_birth(self):
        birth = self.cleaned_data.get('birth')
        if not birth:
            raise forms.ValidationError("Tanggal lahir wajib diisi.")
        return birth

    def clean_gender(self):
        gender = self.cleaned_data.get('gender')
        if not gender:
            raise forms.ValidationError("Jenis kelamin wajib diisi.")
        return gender


       
class UserPhoto(UserChangeForm):
    class Meta:
        model = CustomUser
        fields = ['photo']

    def __init__(self, *args, **kwargs):
        super(UserPhoto, self).__init__(*args, **kwargs)
        self.fields['photo'].widget.attrs.update({
            'class': 'form-control',
            'placeholder': 'Upload your photo',
            'required': True
        })

    def clean_photo(self):
        photo = self.cleaned_data.get('photo')
        if not photo:
            raise ValidationError("Foto wajib diunggah.")

        if photo.size > 100 * 1024:
            raise ValidationError("Ukuran file tidak boleh lebih dari 100KB.")

        # Validasi tipe file
        if not photo.content_type.startswith('image/'):
            raise ValidationError("Hanya file gambar yang diperbolehkan.")

        # Validasi format file (opsional, lebih ketat)
        if imghdr.what(photo) not in ['jpeg', 'png','webp']:
            raise ValidationError("Format gambar tidak dikenali atau tidak didukung.")

        return photo