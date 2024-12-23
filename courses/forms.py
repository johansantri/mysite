# forms.py
from django import forms
from django.core.cache import cache
from .models import Course, Partner, Section
from django_ckeditor_5.widgets import CKEditor5Widget
from django.contrib.auth.models import User
import logging

# Initialize the logger
logger = logging.getLogger(__name__)

#add section
class SectionForm(forms.ModelForm):
    class Meta:
        model = Section
        fields = ['title','courses','parent']

class ProfilForm(forms.ModelForm):
    description = forms.CharField(widget=CKEditor5Widget())
    class Meta:
        model = Course
        fields = ['sort_description','description','image','link_video','hour','language','level','start_date','end_date','start_enrol','end_enrol']

        
        widgets = {
            
            'sort_description': forms.TextInput(attrs={'placeholder': 'Enter short description here', 'class': 'form-control'}),
            #'description': CKEditor5Widget(attrs={'placeholder': 'Enter full description here', 'class': 'django_ckeditor_5'}),
            'image': forms.ClearableFileInput(attrs={'class': 'form-control-file'}),
            'link_video': forms.URLInput(attrs={'placeholder': 'Enter video URL here', 'class': 'form-control'}),
            'hour': forms.NumberInput(attrs={'class': 'form-control'}),
            'language': forms.Select(attrs={'class': 'form-control'}),
            'level': forms.Select(choices=[('beginner', 'Beginner'), ('intermediate', 'Intermediate'), ('advanced', 'Advanced')], attrs={'class': 'form-control'}),           
            'start_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'end_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'start_enrol': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'end_enrol': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
        }
    def __init__(self, *args, **kwargs):
        super(ProfilForm, self).__init__(*args, **kwargs)

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
            "class": "form-control select2"
        })
    }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Cache user queryset
        user_cache_key = 'user_queryset_active'
        user_queryset_ids = cache.get(user_cache_key)

        if user_queryset_ids is None:
            # Log the cache miss for debugging purposes
            logger.debug("Cache miss for user queryset.")
            
            # Query only active users, limit the number of users
            user_queryset = User.objects.filter(is_active=True).only('id', 'username')[:100]
            
            # Cache only the user IDs to minimize cache size
            user_queryset_ids = list(user_queryset.values_list('id', flat=True))  # List of user IDs
            cache.set(user_cache_key, user_queryset_ids, timeout=60*60)  # Cache for 1 hour
            
            # Set the queryset in the form
            self.fields['user'].queryset = user_queryset
        else:
            # If the IDs are in the cache, reconstruct the queryset
            self.fields['user'].queryset = User.objects.filter(id__in=user_queryset_ids)



    def clean_user(self):
        user_value = self.cleaned_data.get('user')
        if not user_value:
            raise forms.ValidationError("This field is required.")
        if Partner.objects.filter(user=user_value).exists():
            raise forms.ValidationError("This user already exists. Please choose another.")
        return user_value
