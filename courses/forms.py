# forms.py
import requests
import xml.etree.ElementTree as ET
from django import forms
from django.forms import inlineformset_factory
from django.core.cache import cache
from .models import MicroCredentialComment,MicroCredentialReview,LTIExternalTool,Course,SosPost,CourseStatus,CourseRating,MicroCredential, AskOra,Partner,Category, Section,Instructor,TeamMember,GradeRange, Material,Question, Choice,Assessment,PricingType, CoursePrice
from django_ckeditor_5.widgets import CKEditor5Widget
import os
from authentication.models import CustomUser, Universiti
import logging
from django.utils.text import slugify
from django.core.files.base import ContentFile
from PIL import Image as PILImage
import io
from datetime import date
from django.core.exceptions import ValidationError
from django.utils import timezone
from captcha.fields import CaptchaField
import xml.etree.ElementTree as ET
import hashlib
from django_select2.forms import ModelSelect2MultipleWidget
logger = logging.getLogger(__name__)





class MicroCredentialCommentForm(forms.ModelForm):
    class Meta:
        model = MicroCredentialComment
        fields = ['content']  # Form hanya meminta konten komentar

    def __init__(self, *args, **kwargs):
        super(MicroCredentialCommentForm, self).__init__(*args, **kwargs)
        self.fields['content'].widget.attrs.update({'class': 'form-control', 'placeholder': 'Write your comment here...'})

class MicroCredentialReviewForm(forms.ModelForm):
    class Meta:
        model = MicroCredentialReview
        fields = ['rating', 'review_text']
        widgets = {
            'review_text': forms.Textarea(attrs={'rows': 4, 'placeholder': 'Write your review here...'}),
        }
        
class LTIExternalToolForm(forms.ModelForm):
    class Meta:
        model = LTIExternalTool
        fields = ['name', 'platform', 'custom_params']  # gunakan platform, bukan consumer key
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'LTI Tool Name (e.g., H5P Integration)'
            }),
            'platform': forms.Select(attrs={
                'class': 'form-control'
            }),
            'custom_params': forms.Textarea(attrs={
                'class': 'form-control',
                'placeholder': 'Contoh: {"context_id": "abc", "user_id": "xyz"}',
                'rows': 3
            }),
        }

    def clean_custom_params(self):
        import json
        custom_params = self.cleaned_data.get('custom_params')
        if custom_params:
            try:
                json.loads(custom_params)
            except Exception:
                raise forms.ValidationError("Format harus berupa JSON yang valid.")
        return custom_params



class CourseRatingForm(forms.ModelForm):
    class Meta:
        model = CourseRating
        fields = ['rating', 'comment']
        widgets = {
            'rating': forms.Select(attrs={'class': 'form-select'}),
            'comment': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }

class SosPostForm(forms.ModelForm):
    #captcha = CaptchaField()
    
    class Meta:
        model = SosPost
        fields = ['content']
        widgets = {
            'content': forms.Textarea(attrs={
                'rows': 2,
                'maxlength': 150,
                'class': 'form-control',
                'placeholder': 'Apa yang ada di pikiranmu?',
                'hx-target': '#post-list',
                'hx-swap': 'prepend'
            }),
        }

    def clean_content(self):
        content = self.cleaned_data['content']
        if len(content) > 150:
            raise forms.ValidationError("Maksimum 150 karakter!")
        return content

class MicroCredentialForm(forms.ModelForm):
    description = forms.CharField(widget=CKEditor5Widget())
    class Meta:
        model = MicroCredential
        fields = ['title', 'slug', 'description', 'required_courses', 'status', 'start_date', 'end_date', 'image', 'category', 'min_total_score']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control', 'style': 'width: 100%; font-size: 18px;',"oninput": "listingslug(value)"}),
             "slug": forms.HiddenInput(attrs={
                "class": "form-control",
                "maxlength": "200"
            }),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
            'start_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'end_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'status': forms.Select(attrs={'class': 'form-control'}),
            'required_courses': forms.SelectMultiple(attrs={'class': 'form-control select2'}),
            'category': forms.Select(attrs={'class': 'form-control'}),
            'min_total_score': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.1'}),
            'image': forms.ClearableFileInput(attrs={'class': 'form-control-file'}),
        }

class AskOraForm(forms.ModelForm):
    class Meta:
        model = AskOra
        fields = ['title','question_text','response_deadline']  # Menyesuaikan field dengan model AskOra
        
        widgets = {
            'title':forms.TextInput(attrs={'class':'form-control','placeholder':'title '}),
            "question_text": CKEditor5Widget(
                attrs={"class": "django_ckeditor_5"},
                config_name="extends",
            ),
            #'question_text': forms.Textarea(attrs={'class': 'form-control', 'placeholder': 'Insert Question hare', 'rows': 4}),
            'response_deadline': forms.DateTimeInput(attrs={'class': 'form-control', 'placeholder': 'Select response deadline', 'type': 'datetime-local'})
           
           
        }
        def clean_response_deadline(self):
            response_deadline = self.cleaned_data['response_deadline']
            if response_deadline < timezone.now():
                raise ValidationError("The response deadline cannot be in the past.")
            return response_deadline

#form re-runs
class CourseRerunForm(forms.ModelForm):
    class Meta:
        model = Course
        fields = ['course_number', 'category', 'level', 'course_run']

    course_name_hidden = forms.CharField(required=False, widget=forms.HiddenInput())
    org_partner_hidden = forms.ModelChoiceField(queryset=Partner.objects.all(), required=False, widget=forms.HiddenInput())

    # Editable fields
    course_number = forms.CharField(widget=forms.TextInput(attrs={'class': 'form-control', 'style': 'width: 100%'}))  
    course_run = forms.CharField(max_length=250, widget=forms.TextInput(attrs={'class': 'form-control', 'style': 'width: 100%'}))

    category = forms.ModelChoiceField(queryset=Category.objects.all(), widget=forms.Select(attrs={'class': 'form-control', 'style': 'width: 100%'}))
    level = forms.ChoiceField(choices=[('basic', 'Basic'), ('middle', 'Middle'), ('advanced', 'Advanced')], widget=forms.Select(attrs={'class': 'form-control', 'style': 'width: 100%'}))


class CoursePriceForm(forms.ModelForm):
    class Meta:
        model = CoursePrice
        fields = ['partner_price', 'discount_percent', 'price_type']

        widgets = {
            'partner_price': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': 'Masukkan harga...',
                'min': '0',
                'step': '0.01'
            }),
            'discount_percent': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': 'Masukkan diskon...',
                'min': '0',
                'max': '100',
                'step': '0.01'
            }),
        }

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        self.course = kwargs.pop('course', None)
        super().__init__(*args, **kwargs)

        if self.user:
            price_type_queryset = PricingType.objects.filter(name__in=[
                'free', 'pay_for_certificate', 'pay_for_exam', 'buy_first'
            ])

            if self.user.is_superuser:
                self.fields['price_type'] = forms.ModelChoiceField(
                    queryset=PricingType.objects.all(),
                    widget=forms.Select(attrs={'class': 'form-control'}),
                    empty_label="Pilih Jenis Harga"
                )
                self.fields['start_date'] = forms.DateField(
                    widget=forms.DateInput(attrs={
                        'class': 'form-control',
                        'type': 'date'
                    }),
                    required=False
                )
                self.fields['duration_days'] = forms.IntegerField(
                    widget=forms.NumberInput(attrs={
                        'class': 'form-control',
                        'placeholder': 'Durasi dalam hari',
                        'min': '1'
                    }),
                    required=False
                )
                self.fields['end_date'] = forms.DateField(
                    widget=forms.DateInput(attrs={
                        'class': 'form-control',
                        'type': 'date'
                    }),
                    required=False
                )
            elif hasattr(self.user, 'is_partner') and self.user.is_partner:
                self.fields['price_type'] = forms.ModelChoiceField(
                    queryset=price_type_queryset,
                    widget=forms.Select(attrs={'class': 'form-control'}),
                    empty_label="Pilih Jenis Harga"
                )

    def clean(self):
        cleaned_data = super().clean()
        price_type = cleaned_data.get('price_type')
        partner_price = cleaned_data.get('partner_price')
        discount_percent = cleaned_data.get('discount_percent')

        if hasattr(self.user, 'is_partner') and self.user.is_partner:
            if not price_type:
                raise forms.ValidationError("Jenis harga harus dipilih.")

            if price_type and price_type.name == 'free':
                cleaned_data['partner_price'] = 0
                cleaned_data['discount_percent'] = 0
            else:
                if partner_price is None or partner_price <= 0:
                    raise forms.ValidationError("Harga harus diisi dengan nilai lebih dari 0 untuk jenis harga berbayar.")
                if discount_percent is None:
                    cleaned_data['discount_percent'] = 0

            existing_price = CoursePrice.objects.filter(course=self.course, price_type=price_type).first()
            if existing_price and existing_price.pk != self.instance.pk:
                raise forms.ValidationError(
                    f"❌ Anda sudah memiliki harga untuk kursus ini dengan jenis harga '{price_type.name}'."
                )

        return cleaned_data

    def save(self, commit=True):
        instance = super().save(commit=False)

        if hasattr(self.user, 'is_partner') and self.user.is_partner:
            if not instance.partner_id:
                instance.partner = self.user.partner_user
            instance.start_date = date.today()
            instance.duration_days = None
            if self.course:
                instance.end_date = self.course.end_date

            if instance.price_type.name == 'free':
                instance.partner_price = 0
                instance.discount_percent = 0

        instance.calculate_prices()

        if commit:
            instance.save()
        return instance


class CourseInstructorForm(forms.ModelForm):
    instructor = forms.ModelChoiceField(
        queryset=Instructor.objects.none(),
        required=True,
        widget=forms.Select(attrs={'class': 'form-control select2'})
    )

    class Meta:
        model = Course
        fields = ['instructor']

    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop('request', None)
        super().__init__(*args, **kwargs)
        if self.request and self.request.user.is_authenticated:
            if self.request.user.is_superuser:
                self.fields['instructor'].queryset = Instructor.objects.all()
            elif self.request.user.is_partner:
                self.fields['instructor'].queryset = Instructor.objects.filter(provider__user=self.request.user)
            elif self.request.user.is_instructor:
                self.fields['instructor'].queryset = Instructor.objects.none()

    def clean_instructor(self):
        instructor = self.cleaned_data.get('instructor')
        if not instructor:
            raise forms.ValidationError("Please select a valid instructor.")
        return instructor


class GradeRangeForm(forms.ModelForm):
    class Meta:
        model = GradeRange
        fields = ['name', 'min_grade', 'max_grade']
        widgets = {
            'name': forms.TextInput(attrs={
                'placeholder': 'Enter name of assessment here',
                'class': 'form-control'
            }),
            'min_grade': forms.NumberInput(attrs={
                'placeholder': '0',
                'class': 'form-control',
                'type': 'number',
                'min': '0',  # Optional: Add minimum value
                'max': '100',  # Optional: Add maximum value
            }),
            'max_grade': forms.NumberInput(attrs={
                'placeholder': '0',
                'class': 'form-control',
                'type': 'number',
                'min': '0',  # Optional: Add minimum value
                'max': '100',  # Optional: Add maximum value
            }),
        }

class AssessmentForm(forms.ModelForm):
    class Meta:
        model = Assessment
        fields = ['name', 'weight', 'flag', 'duration_in_minutes']  # Menambahkan durasi
        widgets = {
            'name': forms.TextInput(attrs={
                'placeholder': 'Enter name of assessment here',
                'class': 'form-control'
            }),
            'weight': forms.NumberInput(attrs={
                'placeholder': '0',
                'class': 'form-control',
                'type': 'number',
                'min': '0',  # Optional: Add minimum value
                'max': '100',  # Optional: Add maximum value
            }),
            'duration_in_minutes': forms.NumberInput(attrs={
                'placeholder': 'Enter duration in minutes',
                'class': 'form-control',
                'type': 'number',
                'min': '0',  # Durasi tidak boleh negatif
            }),
        }
        labels = {
            'flag': 'Enable editor visual',  # Custom label for the flag field
        }
        help_texts = {
            'weight': 'Enter the weight of the assessment (a percentage, 0-100).',
            'duration_in_minutes': 'Enter the duration of the assessment in minutes. (e.g., 0, 5, 10, 30, 60, 120)'
        }

    def clean_weight(self):
        weight = self.cleaned_data.get('weight')
        
        if weight < 0 or weight > 100:
            raise forms.ValidationError("Weight must be between 0 and 100.")
        
        return weight

    def clean_duration_in_minutes(self):
        duration = self.cleaned_data.get('duration_in_minutes')
        
        if duration is None:
            raise forms.ValidationError("Duration cannot be empty.")
        if duration < 0:
            raise forms.ValidationError("Duration must be a non-negative number.")
        
        return duration

    def clean(self):
        cleaned_data = super().clean()
        weight = cleaned_data.get('weight')
        duration_in_minutes = cleaned_data.get('duration_in_minutes')
        
        # You could add additional cross-field validation here if needed
        
        return cleaned_data

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
    #description = forms.CharField(widget=CKEditor5Widget())
    class Meta:
        model = Material
        fields = ['title','description']
        widgets = {
            
            'title': forms.TextInput(attrs={'placeholder': 'Enter short title here', 'class': 'form-control'}),
            "description": CKEditor5Widget(
                attrs={"class": "django_ckeditor_5"},
                config_name="extends",
            ),
            #'description': CKEditor5Widget(attrs={'placeholder': 'Enter full description here', 'class': 'django_ckeditor_5'}),
            'image': forms.ClearableFileInput(attrs={'class': 'form-control-file'}),
            
        }

class ProfilForm(forms.ModelForm):
    class Meta:
        model = Course
        fields = ['sort_description', 'description', 'image', 'link_video', 'hour', 'language', 'level', 'start_date', 'end_date', 'start_enrol', 'end_enrol']

        widgets = {
            'sort_description': forms.TextInput(attrs={'placeholder': 'Enter short description here', 'class': 'form-control'}),
            "description": CKEditor5Widget(attrs={"class": "django_ckeditor_5"}, config_name="extends"),
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

    if self.cleaned_data.get('image') and course.pk:
        old_course = Course.objects.get(pk=course.pk)
        old_image_path = old_course.image.name  # Simpan path lama
        if old_course.image != self.cleaned_data['image']:
            old_course.delete_old_image()
    else:
        old_image_path = None

    if self.cleaned_data.get('image'):
        image_file = self.cleaned_data['image']
        image = PILImage.open(image_file)

        image = image.resize((1200, 628), PILImage.Resampling.LANCZOS)
        image_io = io.BytesIO()
        image.save(image_io, format='WEBP', quality=100)
        image_io.seek(0)

        while image_io.tell() > 100 * 1024:
            image_io.seek(0)
            image.save(image_io, format='WEBP', quality=90)
            image_io.seek(0)

        # Gunakan nama dan path lama jika ada
        if old_image_path:
            base_dir = os.path.dirname(old_image_path)  # direktori lama
            new_image_name = os.path.splitext(os.path.basename(old_image_path))[0] + '.webp'
            final_path = os.path.join(base_dir, new_image_name)
        else:
            new_image_name = image_file.name.rsplit('.', 1)[0] + '.webp'
            final_path = new_image_name  # akan disimpan di path default

        webp_image_file = ContentFile(image_io.read(), name=final_path)
        course.image.save(webp_image_file.name, webp_image_file, save=False)

    if commit:
        course.save()

    return course
class CourseForm(forms.ModelForm):
    class Meta:
        model = Course
        fields = ['course_name', 'course_number', 'course_run', 'slug', 'category', 'level',  'org_partner']
       # fields = ['course_name', 'course_number', 'course_run', 'org_partner', 'instructor', 'status_course', 'description']
        
        widgets = {
            "course_name": forms.TextInput(attrs={
                "placeholder": "Full Stack Development",
                "class": "form-control",
                "oninput": "listingslug(value)"
            }),
           
            "slug": forms.HiddenInput(attrs={
                "class": "form-control",
                "maxlength": "200"
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
    description = forms.CharField(widget=CKEditor5Widget())

    class Meta:
        model = Partner
        fields = ['name', 'user', 'phone', 'tax', 'iceiprice', 'logo', 'address', 'description']
        widgets = {
            "name": forms.Select(
                attrs={"class": "form-control pilihA", "data-placeholder": "Pilih Universitas"}
            ),
            "user": forms.Select(
                attrs={"class": "form-control pilihB", "data-placeholder": "Pilih Pengguna"}
            ),
            "phone": forms.TextInput(attrs={"placeholder": "Phone Number", "class": "form-control"}),
            "address": forms.Textarea(attrs={"placeholder": "Address", "class": "form-control"}),
            "description": forms.Textarea(attrs={"placeholder": "Description", "class": "form-control"}),
            "tax": forms.NumberInput(attrs={"placeholder": "Tax Number", "class": "form-control"}),
            "iceiprice": forms.NumberInput(attrs={"placeholder": "Ice Price %", "class": "form-control"}),
            "logo": forms.ClearableFileInput(attrs={'class': 'form-control', 'accept': 'image/*'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Set nilai awal untuk Select2 dari instance
        if self.instance.pk:  # Jika ada instance (update)
            if self.instance.name:
                self.fields['name'].initial = self.instance.name.id
            if self.instance.user:
                self.fields['user'].initial = self.instance.user.id

        # Set queryset untuk 'name' dan 'user'
        self.fields['name'].queryset = Universiti.objects.all()
        self.fields['user'].queryset = CustomUser.objects.filter(is_active=True)

    def clean_user(self):
        user_value = self.cleaned_data.get('user')
        
        # Jika user tidak dipilih, beri error
        if not user_value:
            raise forms.ValidationError("This field is required.")
        
        # Jika partner dengan user yang sama sudah ada, beri error
        if Partner.objects.filter(user=user_value).exists() and (not self.instance.pk or self.instance.user != user_value):
            raise forms.ValidationError("This user already exists as a partner. Please choose another.")
        
        return user_value

    def save(self, commit=True):
        # Simpan instance partner terlebih dahulu
        partner = super().save(commit=False)

        # Cek apakah ada perubahan user
        if self.instance.pk and self.instance.user != partner.user:
            # Jika ada perubahan user, update user lama
            old_user = self.instance.user
            if old_user:  # Pastikan old_user ada
                old_user.is_partner = False
                old_user.save()  # Simpan perubahan status old_user menjadi False

        # Pastikan user baru mendapatkan status is_partner=True
        if partner.user:
            partner.user.is_partner = True
            partner.user.save()  # Simpan perubahan status user baru menjadi True

        # Simpan partner jika commit=True
        if commit:
            partner.save()

        return partner
    

#selfupdatepartner
class PartnerFormUpdate(forms.ModelForm):
    description = forms.CharField(widget=CKEditor5Widget())
    class Meta:
        model = Partner
        fields = [
            'account_number', 'account_holder_name','bank_name','phone', 'tax','logo', 'address', 'description', 
              
            'tiktok', 'youtube', 'twitter', 'facebook'
        ]

        widgets = {
            'phone': forms.TextInput(attrs={
                'placeholder': 'Phone Number',
                'class': 'form-control'
            }),
            'address': forms.Textarea(attrs={
                'placeholder': 'Address',
                'class': 'form-control',
                'rows': 3
            }),
            'description': CKEditor5Widget(attrs={
                'class': 'form-control', 
                'placeholder': 'Description'
            }),
            'tax': forms.NumberInput(attrs={
                'placeholder': 'Tax Number',
                'class': 'form-control'
            }),
            
            'logo': forms.ClearableFileInput(attrs={
                'class': 'form-control-file',
                'accept': 'image/*',
            }),
            'account_number': forms.TextInput(attrs={
                'placeholder': 'Account Number',
                'class': 'form-control'
            }),
            'account_holder_name': forms.TextInput(attrs={
                'placeholder': 'Account Holder Name',
                'class': 'form-control'
            }),
             'bank_name': forms.TextInput(attrs={
                'placeholder': 'bank_name',
                'class': 'form-control'
            }),
            'tiktok': forms.URLInput(attrs={
                'placeholder': 'TikTok URL',
                'class': 'form-control'
            }),
            'youtube': forms.URLInput(attrs={
                'placeholder': 'YouTube URL',
                'class': 'form-control'
            }),
            'twitter': forms.URLInput(attrs={
                'placeholder': 'Twitter URL',
                'class': 'form-control'
            }),
            'facebook': forms.URLInput(attrs={
                'placeholder': 'Facebook URL',
                'class': 'form-control'
            }),
        }


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

        self.fields['email'].queryset = CustomUser.objects.all()  # Limit user choices if needed


    def clean_email(self):

        email = self.cleaned_data.get('email')

        if not CustomUser.objects.filter(email=email).exists():

            raise forms.ValidationError("No user found with this email.")

        return email