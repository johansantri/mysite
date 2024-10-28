from django.contrib.auth.models import User
from django import forms

class LearnerForm(forms.ModelForm):
    class Meta:        
        model = User
        fields = ('first_name','last_name','username','email','hobby','birth','address','country','phone','gender','education','photo')
        label = {
                "email" : "email",
                "first_name" : "first_name",
                "last_name" : "last_name",
                "username" : "username",
                "hobby" : "hobby",
                "birth" : "birth",
                "address" : "address",
                "country" : "country",
                "phone" : "phone",
                "gender" : "gender",
                "education" :"education",
                "photo" : "photo",
            
                }

        widgets ={
       
        "first_name" : forms.TextInput(attrs={"placeholder":"jhon","class":"form-control","type":"text",'maxlength':'10'}),
        "last_name" : forms.TextInput(attrs={"placeholder":"wik","class":"form-control"}),
        "email" : forms.EmailInput(attrs={"placeholder":"@","class":"form-control"}),
        "username" : forms.TextInput(attrs={"placeholder":"jhon","class":"form-control"}),
        
        "hobby" : forms.TextInput(attrs={"placeholder":"Mancing","class":"form-control"}),
        "birth" : forms.DateInput(attrs={"placeholder":"2023","class":"form-control","type":"date"}),
        "address" : forms.Textarea(attrs={"placeholder":"-","class":"form-control ","row":"3","cols":"40"}),
        "country" : forms.TextInput(attrs={"placeholder":"Mancing","class":"form-control"}),
        "phone" : forms.TextInput(attrs={"placeholder":"Mancing","class":"form-control"}),
        "gender" : forms.Select(attrs={"placeholder":"Mancing","class":"form-select"}),
        "education" : forms.Select(attrs={"placeholder":"Mancing","class":"form-select"}),
        "photo" : forms.ClearableFileInput(attrs={"class":"form-control-file"}),

        
        
        } 

    def clean(self):
        cleaned_data= super().clean()
        email = cleaned_data.get("email")
        if email and len (email) < 3:
            self.add_error('email','name should be at least 3')

        if email and len (email) > 200:
            self.add_error('email','name should be at least 5')

        
            
        

    
