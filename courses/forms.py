# forms.py
from django import forms
from django.forms import inlineformset_factory
from django.core.cache import cache
from .models import Course, Partner, Section,Instructor,TeamMember, Material,Question, Choice,Assessment
from django_ckeditor_5.widgets import CKEditor5Widget
from django.contrib.auth.models import User
import logging
from django.utils.text import slugify
from django.core.files.base import ContentFile
from PIL import Image as PILImage
import io

# Initialize the logger
logger = logging.getLogger(__name__)

class AssessmentForm(forms.ModelForm):
    class Meta:
        model = Assessment
        fields = ['name','flag']
        widgets = {
            'name': forms.TextInput(attrs={
                'placeholder': 'Enter name assessment here',
                'class': 'form-control'
            }),
        }
        labels = {
            'flag': 'Enable editor visual',  # Custom label for the flag field
        }


class QuestionForm(forms.ModelForm):
    text = forms.CharField(required=True)  # Default field is optional

    class Meta:
        model = Question
        fields = ['text']

    def __init__(self, *args, **kwargs):
        # Extract the assessment object from kwargs
        assessment = kwargs.pop('assessment', None)
        super().__init__(*args, **kwargs)

        # Conditionally set widget based on the assessment flag
        if assessment and assessment.flag:
            self.fields['text'].widget = CKEditor5Widget("extends")  # CKEditor widget
        else:
            self.fields['text'].widget = forms.TextInput(attrs={'class': 'form-control'})  # Plain text widget
    
       
class ChoiceForm(forms.ModelForm):
    text = forms.CharField(required=True)  # Default field is optional

    class Meta:
        model = Choice
        fields = ['text', 'is_correct']

    def __init__(self, *args, **kwargs):
        # Extract the assessment object from kwargs
        assessment = kwargs.pop('assessment', None)
        super().__init__(*args, **kwargs)

        # Conditionally set widget based on the assessment flag
        if assessment and assessment.flag:
            self.fields['text'].widget = CKEditor5Widget("extends")  # CKEditor widget
        else:
            self.fields['text'].widget = forms.TextInput(attrs={'class': 'form-control'})  # Plain text widget
       
ChoiceFormSet = inlineformset_factory(
    Question,
    Choice,
    form=ChoiceForm,
    fields=['text', 'is_correct'],
    extra=1,
    can_delete=True
)
#add section
class SectionForm(forms.ModelForm):
    class Meta:
        model = Section
        fields = ['title','courses','parent']

class MatrialForm(forms.ModelForm):
    description = forms.CharField(widget=CKEditor5Widget())
    class Meta:
        model = Material
        fields = ['title','description']
        widgets = {
            
            'title': forms.TextInput(attrs={'placeholder': 'Enter short title here', 'class': 'form-control'}),
            #'description': CKEditor5Widget(attrs={'placeholder': 'Enter full description here', 'class': 'django_ckeditor_5'}),
            'image': forms.ClearableFileInput(attrs={'class': 'form-control-file'}),
            
        }

class ProfilForm(forms.ModelForm):
    description = forms.CharField(widget=CKEditor5Widget())
    class Meta:
        model = Course
        fields = ['sort_description','description','image','link_video','hour','language','level','start_date','end_date','start_enrol','end_enrol']

        
        widgets = {
            
            'sort_description': forms.TextInput(attrs={'placeholder': 'Enter short description here', 'class': 'form-control'}),
            #'description': CKEditor5Widget(attrs={'placeholder': 'Enter full description here', 'class': 'django_ckeditor_5'}),
            'image': forms.ClearableFileInput(attrs={'class': 'form-control-file'}),
            'link_video': forms.URLInput(attrs={'placeholder': 'Enter video URL here', 'class': 'form-control'}),
            'hour': forms.NumberInput(attrs={'class': 'form-control'}),
            'language': forms.Select(attrs={'class': 'form-control'}),
            'level': forms.Select(choices=[('beginner', 'Beginner'), ('intermediate', 'Intermediate'), ('advanced', 'Advanced')], attrs={'class': 'form-control'}),           
            'start_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'end_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'start_enrol': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'end_enrol': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
        }
    def __init__(self, *args, **kwargs):

        super(ProfilForm, self).__init__(*args, **kwargs)


    def save(self, commit=True):

        course = super(ProfilForm, self).save(commit=False)


        # If the image field has changed, delete the old image

        if self.cleaned_data.get('image') and course.pk:

            old_course = Course.objects.get(pk=course.pk)

            if old_course.image != self.cleaned_data['image']:

                old_course.delete_old_image()


        # Convert the uploaded image to WebP format

        if self.cleaned_data.get('image'):

            image_file = self.cleaned_data['image']

            image = PILImage.open(image_file)


            # Create a BytesIO object to hold the WebP image

            webp_image_io = io.BytesIO()

            image.save(webp_image_io, format='WEBP')

            webp_image_io.seek(0)


            # Create a new ContentFile to save the WebP image

            webp_image_file = ContentFile(webp_image_io.read(), name=image_file.name.rsplit('.', 1)[0] + '.webp')

            course.image.save(webp_image_file.name, webp_image_file, save=False)


        if commit:

            course.save()

        return course

class CourseForm(forms.ModelForm):
    class Meta:
        model = Course
        fields = ['course_name', 'course_number', 'course_run', 'slug', 'category', 'level',  'org_partner']

        
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
            }),
            "level": forms.Select(attrs={
                "class": "form-control js-example-basic-single"
            })
        }
    
    def __init__(self, *args, **kwargs):

        user = kwargs.pop('user', None)  # Get the logged-in user from the view

        super().__init__(*args, **kwargs)


        if user:

            if user.is_superuser:

                # Admin: Show all partners in the dropdown

                self.fields['org_partner'].queryset = Partner.objects.all()
              
            elif user.is_partner:

                # Partner: Show only their own partner

                self.fields['org_partner'].queryset = Partner.objects.filter(user=user)
                
            elif user.is_instructor:

                # Instructor: Show only the partner they are associated with

                instructor = user.instructors.first()  # Get the first instructor instance

                if instructor:

                    self.fields['org_partner'].queryset = Partner.objects.filter(id=instructor.provider.id)
                    
                else:

                    self.fields['org_partner'].queryset = Partner.objects.none()  # No options if no instructor found

            else:

                # Optionally handle other user types or set a default queryset

                self.fields['org_partner'].queryset = Partner.objects.none()  # No options for other users
                


class PartnerForm(forms.ModelForm):
    class Meta:
        model = Partner
        fields = ['name', 'user']

        widgets = {
        "name": forms.Select(attrs={
            "placeholder": "Full Stack Development",
            "class": "form-control select1"
        }),
        "user": forms.Select(attrs={
            "placeholder": "CS201",
            "class": "form-control select2"
        })
    }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Cache user queryset
        user_cache_key = 'user_queryset_active'
        user_queryset_ids = cache.get(user_cache_key)

        if user_queryset_ids is None:
            # Log the cache miss for debugging purposes
            logger.debug("Cache miss for user queryset.")
            
            # Query only active users, limit the number of users
            user_queryset = User.objects.filter(is_active=True).only('id', 'username')[:100]
            
            # Cache only the user IDs to minimize cache size
            user_queryset_ids = list(user_queryset.values_list('id', flat=True))  # List of user IDs
            cache.set(user_cache_key, user_queryset_ids, timeout=60*60)  # Cache for 1 hour
            
            # Set the queryset in the form
            self.fields['user'].queryset = user_queryset
        else:
            # If the IDs are in the cache, reconstruct the queryset
            self.fields['user'].queryset = User.objects.filter(id__in=user_queryset_ids)



    def clean_user(self):
        user_value = self.cleaned_data.get('user')
        if not user_value:
            raise forms.ValidationError("This field is required.")
        if Partner.objects.filter(user=user_value).exists():
            raise forms.ValidationError("This user already exists. Please choose another.")
        return user_value
#instructor
class InstructorForm(forms.ModelForm):
    class Meta:
        model = Instructor
        fields = ['bio', 'expertise', 'experience_years','provider','agreement','tech']
        widgets = {
            'bio': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
            'expertise': forms.Textarea(attrs={'class': 'form-control','row':4}),
            'experience_years': forms.NumberInput(attrs={'class': 'form-control'}),
            'provider': forms.Select(attrs={'class': 'form-control','required':'True'}),
            'tech': forms.URLInput(attrs={'class': 'form-control','required':'True'}),
            'agreement': forms.CheckboxInput(attrs={'class': 'form-check-input','required':'True'}),

        }
    def clean_experience_years(self):
        experience = self.cleaned_data.get('experience_years')
        if experience is not None and experience < 0:
            raise forms.ValidationError("Experience years cannot be negative.")
        return experience
    
#instructor add coruse
class InstructorAddCoruseForm(forms.ModelForm):

    class Meta:

        model = Course

        fields = ['instructor']

        widgets = {

            'instructor': forms.Select(attrs={'class': 'form-control', 'placeholder': 'Enter instructor name'}),

        }



class TeamMemberForm(forms.ModelForm):

    email = forms.EmailField(required=True)  # Add an email field


    class Meta:

        model = TeamMember

        fields = ['email']  # Include only the email field
        widgets = {

            'email': forms.TextInput(attrs={

                'class': 'form-control',  # Bootstrap class for styling

                'placeholder': 'Enter instructor email',  # Placeholder text

                'required': 'required'  # Make the field required

            }),

        }

    def __init__(self, *args, **kwargs):

        super(TeamMemberForm, self).__init__(*args, **kwargs)

        self.fields['email'].queryset = User.objects.all()  # Limit user choices if needed


    def clean_email(self):

        email = self.cleaned_data.get('email')

        if not User.objects.filter(email=email).exists():

            raise forms.ValidationError("No user found with this email.")

        return email