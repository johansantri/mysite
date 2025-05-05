# licensing/forms.py
from django import forms
from .models import Invitation, License

class InvitationForm(forms.Form):
    invitee_emails = forms.CharField(
        label="Invitee's Emails (separate by space or newline)",
        widget=forms.Textarea(attrs={'class': 'form-control', 'placeholder': 'Enter emails separated by space or newline'}),
    )

    def clean_invitee_emails(self):
        """Validasi dan bersihkan input email."""
        emails = self.cleaned_data['invitee_emails']
        
        if not emails:
            raise forms.ValidationError("Please provide at least one email address.")
        
        # Pisahkan berdasarkan newline atau spasi dan hilangkan spasi ekstra di sekitar email
        email_list = [email.strip() for email in emails.replace(',', ' ').split()]
        
        # Validasi apakah format email valid untuk setiap entri
        for email in email_list:
            if '@' not in email:  # Cek sederhana apakah email valid (bisa diganti dengan validasi lebih kuat)
                raise forms.ValidationError(f"'{email}' is not a valid email address.")
        
        return email_list

class InvitationSearchForm(forms.Form):
    search_email = forms.EmailField(required=False, label="Search by Email")
    status = forms.ChoiceField(choices=[('', 'All'), ('Pending', 'Pending'), ('Accepted', 'Accepted'), ('Expired', 'Expired')],
                               required=False, label="Status")