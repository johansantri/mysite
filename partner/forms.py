from django import forms
from courses.models import Partner
from django.core.exceptions import ValidationError

class PartnerRequestForm(forms.ModelForm):
    class Meta:
        model = Partner
        fields = [
            'name', 'phone', 'address', 'description',
            'npwp', 'npwp_file', 'business_type',
            'account_number', 'account_holder_name', 'bank_name',
            'logo', 'is_pkp', 'agreed_to_terms'
        ]
        widgets = {
            'name': forms.Select(attrs={'class': 'border border-gray-300 rounded px-3 py-2 w-full'}),
            'phone': forms.TextInput(attrs={'class': 'border border-gray-300 rounded px-3 py-2 w-full'}),
            'address': forms.Textarea(attrs={'class': 'border border-gray-300 rounded px-3 py-2 w-full', 'rows': 3}),
            'description': forms.Textarea(attrs={'class': 'border border-gray-300 rounded px-3 py-2 w-full', 'rows': 3}),
            'npwp': forms.TextInput(attrs={'class': 'border border-gray-300 rounded px-3 py-2 w-full'}),
            'npwp_file': forms.ClearableFileInput(attrs={'class': 'border border-gray-300 rounded px-3 py-2 w-full'}),
            'business_type': forms.Select(attrs={'class': 'border border-gray-300 rounded px-3 py-2 w-full'}),
            'account_number': forms.TextInput(attrs={'class': 'border border-gray-300 rounded px-3 py-2 w-full'}),
            'account_holder_name': forms.TextInput(attrs={'class': 'border border-gray-300 rounded px-3 py-2 w-full'}),
            'bank_name': forms.TextInput(attrs={'class': 'border border-gray-300 rounded px-3 py-2 w-full'}),
            'logo': forms.ClearableFileInput(attrs={'class': 'border border-gray-300 rounded px-3 py-2 w-full'}),
            'is_pkp': forms.CheckboxInput(attrs={'class': 'h-5 w-5'}),
            'agreed_to_terms': forms.CheckboxInput(attrs={'class': 'h-5 w-5', 'id': 'id_agreed_to_terms'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            if field_name != 'is_pkp':  # is_pkp tidak wajib
                field.required = True
            else:
                field.required = False

    def clean_agreed_to_terms(self):
        agreed = self.cleaned_data.get('agreed_to_terms')
        if not agreed:
            raise ValidationError(
                "You must agree to the contract terms and applicable rules to proceed."
            )
        return agreed


