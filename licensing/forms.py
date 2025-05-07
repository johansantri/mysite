# licensing/forms.py
from django import forms
from .models import Invitation, License


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