
from django import forms
from .models import Comment
from django.contrib.auth.models import User 
from django.contrib.auth.forms import UserCreationForm 

class CommentForm(forms.ModelForm):
    class Meta:
        model = Comment
        fields = ('name', 'email', 'body')
    
    # overriding default form setting and adding bootstrap class
    def __init__(self, *args, **kwargs):
        super(CommentForm, self).__init__(*args, **kwargs)
        self.fields['name'].widget.attrs = {'placeholder': 'Enter name','class':'form-control'}
        self.fields['email'].widget.attrs = {'placeholder': 'Enter email', 'class':'form-control'}
        self.fields['body'].widget.attrs = {'placeholder': 'Comment here...', 'class':'form-control', 'rows':'5'}

class SignUpForm(UserCreationForm): 
    class Meta: 
        model = User 
        fields = ('username', 'email', 'password1', 'password2', ) 
   
