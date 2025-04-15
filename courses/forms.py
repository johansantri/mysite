# forms.py
from django import forms
from django.forms import inlineformset_factory
from django.core.cache import cache
from .models import LTIExternalTool, LTIPlatformConfiguration,Course,SosPost,CourseStatus,CourseRating,MicroCredential, AskOra,Partner,Category, Section,Instructor,TeamMember,GradeRange, Material,Question, Choice,Assessment,PricingType, CoursePrice
from django_ckeditor_5.widgets import CKEditor5Widget

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


class LTIExternalToolForm(forms.ModelForm):
    class Meta:
        model = LTIExternalTool
        fields = ['name', 'launch_url', 'platform_config', 'has_grade', 'max_grade']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Misalnya: Kuis Moodle'}),
            'launch_url': forms.URLInput(attrs={'class': 'form-control', 'placeholder': 'https://moodle.example.com/mod/lti/launch.php'}),
            'platform_config': forms.Select(attrs={'class': 'form-select'}),
            'has_grade': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'max_grade': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Misalnya: 50', 'min': 0, 'max': 100}),
        }
        labels = {
            'name': 'Nama Alat',
            'launch_url': 'Link Peluncuran',
            'platform_config': 'Platform LTI',
            'has_grade': 'Mengembalikan Nilai',
            'max_grade': 'Nilai Maksimum',
        }

    def clean(self):
        cleaned_data = super().clean()
        has_grade = cleaned_data.get('has_grade')
        max_grade = cleaned_data.get('max_grade')
        if has_grade and not max_grade:
            raise forms.ValidationError("Harap masukkan nilai maksimum jika LTI mengembalikan nilai.")
        if max_grade and max_grade <= 0:
            raise forms.ValidationError("Nilai maksimum harus lebih dari 0.")
        return cleaned_data

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

#add course price
class CoursePriceForm(forms.ModelForm):
    class Meta:
        model = CoursePrice
        fields = ['partner_price', 'discount_percent']  # Partner hanya bisa isi harga dan diskon

        widgets = {
            'partner_price': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Masukkan harga...', 'min': '0', 'step': '0.01'}),
            'discount_percent': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Masukkan diskon...', 'min': '0', 'max': '100', 'step': '0.01'}),
        }

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        self.course = kwargs.pop('course', None)
        super().__init__(*args, **kwargs)

        if self.user:
            if self.user.is_superuser:
                self.fields['price_type'] = forms.ModelChoiceField(
                    queryset=PricingType.objects.all(),
                    widget=forms.Select(attrs={'class': 'form-control'}),
                    empty_label="Pilih Jenis Harga"
                )
                self.fields['start_date'] = forms.DateField(
                    widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
                    required=False
                )
                self.fields['duration_days'] = forms.IntegerField(
                    widget=forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Durasi dalam hari', 'min': '1'}),
                    required=False
                )
                self.fields['end_date'] = forms.DateField(
                    widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
                    required=False
                )

            elif hasattr(self.user, 'is_partner') and self.user.is_partner:
                try:
                    regular_type = PricingType.objects.get(name="Beli Langsung")
                    self.fields['price_type'] = forms.ModelChoiceField(
                        queryset=PricingType.objects.filter(name="Beli Langsung"),
                        initial=regular_type,
                        widget=forms.HiddenInput()
                    )
                except PricingType.DoesNotExist:
                    raise forms.ValidationError("Tipe harga 'Beli Langsung' tidak ditemukan! Tambahkan di database.")

    def clean(self):
        cleaned_data = super().clean()

        if hasattr(self.user, 'is_partner') and self.user.is_partner:
            existing_price = CoursePrice.objects.filter(course=self.course, price_type__name="Beli Langsung").first()
            
            # Jika partner sudah punya harga, hanya bisa mengedit
            if existing_price and existing_price.pk != self.instance.pk:
                raise forms.ValidationError("❌ Anda hanya dapat menambahkan satu harga untuk kursus ini.")

        return cleaned_data

    def save(self, commit=True):
        """Tetapkan nilai otomatis sebelum menyimpan"""
        instance = super().save(commit=False)

        if hasattr(self.user, 'is_partner') and self.user.is_partner:
            # ✅ Pastikan `partner` otomatis diisi
            if not instance.partner_id:
                instance.partner = self.user.partner_user  # Gunakan relasi OneToOneField dari model Partner
            
            instance.start_date = date.today()
            instance.duration_days = None
            if self.course:
                instance.end_date = self.course.end_date
            
            # ✅ Pastikan `price_type` otomatis diisi
            if not instance.price_type_id:
                try:
                    instance.price_type = PricingType.objects.get(name="Beli Langsung")
                except PricingType.DoesNotExist:
                    raise ValueError("Tipe harga 'Beli Langsung' tidak ditemukan! Tambahkan di database.")

        # Hitung harga otomatis
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
    #description = forms.CharField(widget=CKEditor5Widget())
    class Meta:
        model = Course
        fields = ['sort_description','description','image','link_video','hour','language','level','start_date','end_date','start_enrol','end_enrol']

        
        widgets = {
            
            'sort_description': forms.TextInput(attrs={'placeholder': 'Enter short description here', 'class': 'form-control'}),
            "description": CKEditor5Widget(
                attrs={"class": "django_ckeditor_5"},
                config_name="extends",
            ),
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