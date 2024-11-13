from .models import Partner
from django import forms

class PartnerForm(forms.ModelForm):
    class Meta:        
        model = Partner
        fields = ('partner_name','abbreviation','phone','address','e_mail')
     

     

    def clean_e_mail(self):
        e_mail_value = self.cleaned_data.get('e_mail')
        if Partner.objects.filter(e_mail=e_mail_value).exists():
            raise forms.ValidationError("This value already exists. Please choose another.")
        return e_mail_value


    
