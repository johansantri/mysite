
from typing import Any
from django import forms
from .models import Course
from django.contrib.auth.models import User 
from django.contrib.auth.forms import UserCreationForm 


def is_anagram(x,y):
   return sorted(x)==sorted(y)

class CourseForm(forms.Form):
   course_name = forms.CharField(
      label='course name',
      max_length=10,
      widget=forms.TextInput(attrs={'class':"input"})
   )
       

   def clean_test_value(self):
      data = self.cleaned_data.get('course_name')
      if not is_anagram(data,'listin'):
         raise forms.ValidationError('this is not an anagram')
      return data

