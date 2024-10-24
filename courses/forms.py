from .models import Course, Partner
from django import forms

class CourseForm(forms.ModelForm):
    class Meta:        
        model = Course
        fields = ('course_name','org_partner','course_number','course_run','slug','category','author')
        label = {
                "course_name" : "Course_name",
                "org_partner" : "org_partner",
                "course_number" : "course_number",
                "course_run" : "course_run",
                "slug" : "slug",
                "category" : "category",
               # "author" : "author",
            
                }

        widgets ={
        "course_name" : forms.TextInput(attrs={"placeholder":"full stack d","class":"form-control","oninput":"listingslug(value)"}),
        "slug" : forms.HiddenInput(attrs={"placeholder":"full stack","class":"form-control","type":"hidden",'maxlength':'10'}),
        "course_number" : forms.TextInput(attrs={"placeholder":"cs201","class":"form-control"}),
        "course_run" : forms.TextInput(attrs={"placeholder":"2023","class":"form-control"}),
        
        "org_partner" : forms.Select(attrs={"placeholder":"-","class":"form-control js-example-basic-single","id":"id_org_partner"}),
        "category" : forms.Select(attrs={"placeholder":"-","class":"form-control js-example-basic-single"}),
        #"author" : forms.SelectMultiple(attrs={"placeholder":"-","class":"form-control js-example-basic-single"}),
        
        } 

    def clean(self):
        cleaned_data= super().clean()
        course_name = cleaned_data.get("course_name")
        if course_name and len (course_name) < 3:
            self.add_error('course_name','name should be at least 3')

        if course_name and len (course_name) > 200:
            self.add_error('course_name','name should be at least 5')

        
            
        

    
