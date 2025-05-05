# licensing/forms.py
from django import forms
from .models import Invitation, License

class InvitationForm(forms.Form):
    invitee_emails = forms.CharField(
        widget=forms.Textarea(attrs={'rows': 5, 'class':'form-control', 'placeholder': 'Masukkan email (satu per baris atau dipisahkan koma)'}),
        label="Email Penerima",
        required=True
    )