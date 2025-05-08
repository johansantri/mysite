# licensing/forms.py
from django import forms
from .models import Invitation, License
from authentication.models import CustomUser
from django.core.exceptions import ValidationError

class InvitationForm(forms.Form):
    invitee_emails = forms.CharField(
        widget=forms.Textarea(attrs={
            'rows': 5,
            'class': 'form-control',
            'placeholder': 'Enter email addresses (one per line or separated by commas)'
        }),
        label="Invitee Emails",
        required=True
    )

class LicenseForm(forms.ModelForm):
    # Field untuk input satu email pengguna
    user_email = forms.EmailField(
        widget=forms.EmailInput(attrs={'placeholder': 'Masukkan email pengguna'}),
        required=True,  # Wajib diisi
        label='Email Pengguna'
    )

    class Meta:
        model = License
        fields = [
            'name', 'license_type', 'start_date', 'expiry_date', 'status',
            'description', 'university', 'max_users', 'subscription_type',
            'subscription_frequency'
        ]
        widgets = {
            'start_date': forms.DateInput(attrs={'type': 'date'}),
            'expiry_date': forms.DateInput(attrs={'type': 'date'}),
            'description': forms.Textarea(attrs={'rows': 4}),
        }

    def clean_user_email(self):
        email = self.cleaned_data.get('user_email')
        try:
            user = CustomUser.objects.get(email=email)
            return user
        except CustomUser.DoesNotExist:
            raise ValidationError(f"Email {email} tidak ditemukan.")

    def clean(self):
        cleaned_data = super().clean()
        max_users = cleaned_data.get('max_users')
        user = cleaned_data.get('user_email')

        # Validasi bahwa hanya satu pengguna yang diizinkan
        if max_users < 1:
            raise ValidationError("Maksimum pengguna harus minimal 1.")
        if user and self.instance.pk:  # Jika sedang update
            current_users = self.instance.users.count()
            if current_users >= max_users:
                raise ValidationError(f"Jumlah pengguna sudah mencapai batas maksimum ({max_users}).")

        return cleaned_data
    def clean_user_email(self):
        email = self.cleaned_data.get('user_email')
        try:
            user = CustomUser.objects.get(email=email)
            # Cek apakah user sudah terkait dengan lisensi lain
            if License.objects.filter(users=user).exclude(pk=self.instance.pk).exists():
                raise ValidationError(f"Email {email} sudah digunakan di lisensi lain.")
            return user
        except CustomUser.DoesNotExist:
            raise ValidationError(f"Email {email} tidak ditemukan.")

    def save(self, commit=True):
        instance = super().save(commit=False)
        if commit:
            instance.save()
            # Simpan pengguna dan update status is_subscription
            user = self.cleaned_data['user_email']
            if user:
                instance.users.set([user])  # Set hanya satu pengguna
                user.is_subscription = True  # Update status is_subscription
                user.save()
        return instance