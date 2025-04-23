from django import forms
from .models import BlogComment

class NewCommentForm(forms.ModelForm):
    class Meta:
        model = BlogComment
        fields = ['author', 'content']

        widgets = {
            'author': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter your name',
                'aria-label': 'Author',
                'required': True
            }),
            'content': forms.Textarea(attrs={
                'class': 'form-control',
                'placeholder': 'Write your comment here...',
                'rows': 5,
                'aria-label': 'Comment',
                'required': True
            }),
        }

        labels = {
            'author': 'Name',
            'content': 'Comment',
        }

        help_texts = {
            'content': 'Keep your comment respectful and relevant.',
        }

    def clean_author(self):
        author = self.cleaned_data.get('author')
        if len(author) < 2:
            raise forms.ValidationError("Name must be at least 2 characters long.")
        return author

    def clean_content(self):
        content = self.cleaned_data.get('content')
        if len(content.strip()) < 5:
            raise forms.ValidationError("Comment is too short. Please write something meaningful.")
        return content
