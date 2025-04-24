from django import forms
from django.core.exceptions import ValidationError
from .models import BlogComment
from courses.models import BlacklistedKeyword  # Import from the courses app

class NewCommentForm(forms.ModelForm):
    class Meta:
        model = BlogComment
        fields = ['content']  # Only include 'content' since 'author' and 'blogpost_connected' are set in the view

        widgets = {
            'content': forms.Textarea(attrs={
                'class': 'form-control',
                'placeholder': 'Write your comment here...',
                'rows': 5,
                'aria-label': 'Comment',
                'required': True
            }),
        }

        labels = {
            'content': 'Comment',
        }

        help_texts = {
            'content': 'Keep your comment respectful and relevant.',
        }

    def clean_content(self):
        content = self.cleaned_data.get('content')
        if not content:
            raise ValidationError("Comment cannot be empty.")

        # Check minimum length
        if len(content.strip()) < 5:
            raise ValidationError("Comment is too short. Please write something meaningful.")

        # Check for blacklisted keywords
        blacklisted_keywords = BlacklistedKeyword.objects.all()
        content_lower = content.lower()  # Case-insensitive comparison
        for keyword in blacklisted_keywords:
            if keyword.keyword.lower() in content_lower:
                raise ValidationError(f"Comment contains inappropriate word: '{keyword.keyword}'. Please revise your comment.")

        return content