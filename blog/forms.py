from django import forms
from django.core.exceptions import ValidationError
from django.utils.text import slugify
from .models import BlogPost, Tag, BlogComment
from courses.models import BlacklistedKeyword, Course, Category
from django_ckeditor_5.widgets import CKEditor5Widget
from django.utils import timezone
from datetime import timedelta

class BlogPostForm(forms.ModelForm):
    content = forms.CharField(widget=CKEditor5Widget())
    class Meta:
        model = BlogPost
        fields = ['title', 'content', 'image', 'category', 'tags', 'related_courses', 'status']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter post title'}),
            'content': forms.Textarea(attrs={'class': 'form-control', 'rows': 8, 'placeholder': 'Write your content here'}),
            'image': forms.ClearableFileInput(attrs={'class': 'form-control'}),
            'category': forms.Select(attrs={'class': 'form-select'}),
            'tags': forms.SelectMultiple(attrs={'class': 'form-select', 'multiple': 'multiple'}),
            'related_courses': forms.SelectMultiple(attrs={'class': 'form-select', 'multiple': 'multiple'}),
            'status': forms.Select(attrs={'class': 'form-select'}),
        }

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        self.fields['category'].queryset = Category.objects.all()
        self.fields['tags'].queryset = Tag.objects.all()
        self.fields['related_courses'].queryset = Course.objects.all()

    def clean(self):
        cleaned_data = super().clean()
        title = cleaned_data.get('title')
        if title and self.user:
            base_slug = slugify(title)
            slug = base_slug
            counter = 1
            while BlogPost.objects.filter(slug=slug).exclude(id=self.instance.id if self.instance else None).exists():
                slug = f"{base_slug}-{counter}"
                counter += 1
            cleaned_data['slug'] = slug

            recent_posts = BlogPost.objects.filter(
                author=self.user,
                title=title,
                date_posted__gte=timezone.now() - timedelta(minutes=5)
            ).exclude(id=self.instance.id if self.instance else None)
            if recent_posts.exists():
                raise ValidationError("You recently posted an article with the same title. Please use a different title or wait a few minutes.")

        return cleaned_data

    def clean_content(self):
        content = self.cleaned_data.get('content')
        if not content:
            raise ValidationError("Content cannot be empty.")
        if len(content.strip()) < 10:
            raise ValidationError("Content is too short. Please write at least 10 characters.")
        blacklisted_keywords = BlacklistedKeyword.objects.all()
        content_lower = content.lower()
        for keyword in blacklisted_keywords:
            if keyword.keyword.lower() in content_lower:
                raise ValidationError(
                    f"Content contains inappropriate word: '{keyword.keyword}'. Please revise your content."
                )
        return content

    def save(self, commit=True):
        instance = super().save(commit=False)
        if 'slug' in self.cleaned_data:
            instance.slug = self.cleaned_data['slug']
        if commit:
            instance.save()
            self.save_m2m()
        return instance

# NewCommentForm tetap sama
class NewCommentForm(forms.ModelForm):
    class Meta:
        model = BlogComment
        fields = ['content']
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
        if len(content.strip()) < 5:
            raise ValidationError("Comment is too short. Please write something meaningful.")
        blacklisted_keywords = BlacklistedKeyword.objects.all()
        content_lower = content.lower()
        for keyword in blacklisted_keywords:
            if keyword.keyword.lower() in content_lower:
                raise ValidationError(
                    f"Comment contains inappropriate word: '{keyword.keyword}'. Please revise your comment."
                )
        return content