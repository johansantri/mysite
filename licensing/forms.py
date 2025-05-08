# licensing/forms.py
from django import forms
from .models import Invitation, License
from authentication.models import CustomUser

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
    class Meta:
        model = License
        fields = ['name', 'license_type', 'subscription_type', 'subscription_frequency', 'max_users']
        
        # Adding widgets for each field
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'style': 'width: 300px;'}),
            'license_type': forms.Select(attrs={'class': 'form-control', 'style': 'width: 300px;'}),
            'subscription_type': forms.Select(attrs={'class': 'form-control', 'style': 'width: 300px;'}),
            'subscription_frequency': forms.Select(attrs={'class': 'form-control', 'style': 'width: 300px;'}),
            'max_users': forms.NumberInput(attrs={'class': 'form-control', 'style': 'width: 100px;'}),
            'email': forms.EmailInput(attrs={'class': 'form-control', 'style': 'width: 300px;', 'autocomplete': 'off'})  # Adding autocomplete="off"
        }

    email = forms.EmailField()

    def clean_email(self):
        email = self.cleaned_data.get('email')
        try:
            user = CustomUser.objects.get(email=email, is_active=True)
        except CustomUser.DoesNotExist:
            raise forms.ValidationError("User with this email was not found or is inactive.")
        return user