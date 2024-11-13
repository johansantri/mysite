from django import forms
from .models import Course

class CourseForm(forms.ModelForm):
    class Meta:
        model = Course
        fields = ('course_name', 'org_partner', 'course_number', 'course_run', 'slug', 'category')
        labels = {
            "course_name": "Course Name",
            "org_partner": "Organization Partner",
            "course_number": "Course Number",
            "course_run": "Course Run",
            "slug": "Slug",
            "category": "Category",
        }
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

    def clean(self):
        cleaned_data = super().clean()
        course_name = cleaned_data.get("course_name")

        if course_name:
            if len(course_name) < 3:
                self.add_error('course_name', 'Name should be at least 3 characters long.')
            elif len(course_name) > 200:
                self.add_error('course_name', 'Name should be no more than 200 characters.')

