from django import forms
from django.core.exceptions import ValidationError
from django.utils.text import slugify
from .models import BlogPost, Tag, BlogComment
from courses.models import BlacklistedKeyword, Course, Category
from django_ckeditor_5.widgets import CKEditor5Widget
from django.utils import timezone
from datetime import timedelta
from PIL import Image as PILImage
import io
from django.core.files.base import ContentFile

class BlogPostForm(forms.ModelForm):
    content = forms.CharField(widget=CKEditor5Widget())
    
    class Meta:
        model = BlogPost
        fields = ['title', 'content', 'image', 'category', 'tags', 'related_courses', 'status']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter post title'}),
            'content': forms.Textarea(attrs={'class': 'form-control', 'rows': 8, 'placeholder': 'Write your content here'}),
            'image': forms.ClearableFileInput(attrs={'class': 'form-control-file'}),
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
        blog_post = super().save(commit=False)

        # If the image field has changed, delete the old image
        if self.cleaned_data.get('image') and blog_post.pk:
            old_post = BlogPost.objects.get(pk=blog_post.pk)
            if old_post.image and old_post.image != self.cleaned_data['image']:
                old_post.image.delete(save=False)  # Delete old image file

        # Convert and resize image
        if self.cleaned_data.get('image'):
            image_file = self.cleaned_data['image']
            image = PILImage.open(image_file)

            # Convert to RGB if image is in RGBA mode (e.g., PNG with transparency)
            if image.mode == 'RGBA':
                image = image.convert('RGB')

            # Resize the image to 1200x628 pixels using LANCZOS resampling
            image = image.resize((1200, 628), PILImage.Resampling.LANCZOS)

            # Save the image to a BytesIO object
            image_io = io.BytesIO()
            image.save(image_io, format='WEBP', quality=85)  # Start with quality=85
            image_io.seek(0)

            # Check if image size exceeds 100KB, adjust quality if necessary
            quality = 85
            while image_io.tell() > 100 * 1024 and quality > 10:  # 100KB in bytes
                image_io = io.BytesIO()  # Reset BytesIO
                quality -= 5  # Reduce quality incrementally
                image.save(image_io, format='WEBP', quality=quality)
                image_io.seek(0)

            # Create a new ContentFile for the WebP image
            webp_image_file = ContentFile(
                image_io.read(),
                name=image_file.name.rsplit('.', 1)[0] + '.webp'
            )

            # Save the processed image to the blog_post instance
            blog_post.image.save(webp_image_file.name, webp_image_file, save=False)

        if commit:
            blog_post.save()
            self.save_m2m()  # Save ManyToMany fields (tags, related_courses)
        return blog_post

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