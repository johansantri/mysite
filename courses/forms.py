from .models import Course
from django import forms

class CourseForm(forms.ModelForm):
    class Meta:
        model = Course
        fields = ('course_name','org_partner','course_number','course_run','slug','category')

        label = {
        "course_name" : "Course_name",
        "org_partner" : "org_partner",
        "course_number" : "course_number",
        "course_run" : "course_run",
        "slug" : "slug",
        "category" : "category",
       
        }

        widgets ={
        "course_name" : forms.TextInput(attrs={"placeholder":"full stack d","class":"form-control","oninput":"listingslug(value)"}),
        "slug" : forms.HiddenInput(attrs={"placeholder":"full stack","class":"form-control","type":"hidden",'maxlength':'10'}),
        "course_number" : forms.TextInput(attrs={"placeholder":"cs201","class":"form-control"}),
        "course_run" : forms.TextInput(attrs={"placeholder":"2023","class":"form-control"}),
        
        "org_partner" : forms.Select(attrs={"placeholder":"-","class":"form-control js-example-basic-single","id":"id_org_partner"}),
        "category" : forms.Select(attrs={"placeholder":"-","class":"form-control js-example-basic-single"}),
        
        }

    
