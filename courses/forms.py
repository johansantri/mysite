# forms.py
from django import forms
from django.core.cache import cache
from .models import Course, Partner, Section

from django.contrib.auth.models import User

#add section
class SectionForm(forms.ModelForm):
    class Meta:
        model = Section
        fields = ['title','courses','parent']

class CourseForm(forms.ModelForm):
    class Meta:
        model = Course
        fields = ['course_name', 'course_number', 'course_run', 'slug', 'category', 'level', 'status_course', 'org_partner']

        
        widgets = {
            "course_name": forms.TextInput(attrs={
                "placeholder": "Full Stack Development",
                "class": "form-control",
                "oninput": "listingslug(value)"
            }),
            "slug": forms.HiddenInput(attrs={
                "class": "form-control",
                "maxlength": "10"
            }),
            "course_number": forms.TextInput(attrs={
                "placeholder": "CS201",
                "class": "form-control"
            }),
            "course_run": forms.TextInput(attrs={
                "placeholder": "2023",
                "class": "form-control"
            }),
            "org_partner": forms.Select(attrs={
                "class": "form-control js-example-basic-single",
                "id": "id_org_partner"
            }),
            "category": forms.Select(attrs={
                "class": "form-control js-example-basic-single"
            })
        }
    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)  # Get the logged-in user from the view
        super().__init__(*args, **kwargs)
        if user:
            # Filter org_partner to show only partners associated with the logged-in user
            self.fields['org_partner'].queryset = Partner.objects.filter(user=user)

class PartnerForm(forms.ModelForm):
    class Meta:
        model = Partner
        fields = ['name', 'abbreviation', 'user']

        widgets = {
        "name": forms.TextInput(attrs={
            "placeholder": "Full Stack Development",
            "class": "form-control",
            "oninput": "listingslug(value)"
        }),
        "abbreviation": forms.TextInput(attrs={
            "class": "form-control",
            "maxlength": "10"
        }),
        "user": forms.Select(attrs={
            "placeholder": "CS201",
            "class": "form-control"
        })
    }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Cache user queryset
        user_cache_key = 'user_queryset_active'
        user_queryset = cache.get(user_cache_key)
        
        if not user_queryset:
            # Query only active users, limit the number of users
            user_queryset = User.objects.filter(is_active=True).only('id', 'username')[:10]  # Limit to 500 users
            cache.set(user_cache_key, user_queryset, timeout=60*60)  # Cache for 1 hour
        
        # Set the queryset in the form
        self.fields['user'].queryset = user_queryset

    def clean_user(self):
        user_value = self.cleaned_data.get('user')
        if Partner.objects.filter(user=user_value).exists():
            raise forms.ValidationError("This user already exists. Please choose another.")
        return user_value