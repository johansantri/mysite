###########
What is MYSITE
###########

MYSITE merupakan pengembangan aplikasi LMS berbasis Python Django.

*******************
Release Information
*******************

Repo ini dirancang untuk bekerja team dalam pembuatan LMS
<https://github.com/johansantri/mysite>`_ page.

**************************
Perubahan dan Pengembangan Aplikasi LMS
**************************

*******************
Kebutuhan Requirements
*******************

Django 5.1.

Aplikasi ini berjalan di Python 3 dengan framework Django 5.1.

************
Installasi
************

Perhatikan Panduan dibawah ini untuk memulai aplikasi

***************
# Testing Website
Proyek eksplorasi Python menggunakan framework Django.

## Akses Role
- Superuser
- Staf
- Partner
- Instructor
- Learner
- Dan lainnya

## Instalasi

Pastikan Anda telah menginstal **Python** dan **pip** di sistem Anda sebelum memulai.

### 1. Clone repositori ini:
```shell
git clone https://github.com/johansantri/mysite.git
```
### 2. Pindah ke direktori proyek:
```shell
cd mysite
```
### 3. Buat virtual environment:
Anda bisa melihat referensi berikut <https://packaging.python.org/en/latest/guides/installing-using-pip-and-virtual-environments/> jenis OS dalam menggunakan virtual environment ini menggunakan Windows
```shell
py -m venv .venv
```
### 4. Aktifkan virtual environment:
```shell
.venv\Scripts\activate
```

### 5. Install requests:
```shell
py -m pip install requests
```
### 6. Install dependencies dari requirements.txt:
```shell
py -m pip install -r requirements.txt
```
### 7. Freeze requirements (untuk mencatat versi package):
```shell
py -m pip freeze
```
### 8.Jalankan server
``` shell
python manage.py runserver
```
jika mengalami kendala, coba ikuti langkah dibawah ini
### 9. Salin data dari models.py:

*****
Sebelum menjalankan aplikasi, salin data dari models.py **mysite\.venv\lib\site-packages\django\contrib\auth.** ke path Anda atau path sama seperti Anda salin
Pastikan untuk menyalin seluruh isi **models.py.**
```shell
from collections.abc import Iterable
from django.conf import settings
from django.apps import apps
from django.contrib import auth
from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.contrib.auth.hashers import make_password
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import PermissionDenied
from django.core.mail import send_mail
from django.db import models
from django.db.models.manager import EmptyManager
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
import datetime
import os
from django_cleanup import cleanup

from .validators import UnicodeUsernameValidator

class Universiti(models.Model):
    name = models.CharField(max_length=200, blank=True, null=True)
    slug = models.SlugField(unique=True)
    location = models.CharField(max_length=100, blank=True, null=True)

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name
        
def update_last_login(sender, user, **kwargs):
    """
    A signal receiver which updates the last_login date for
    the user logging in.
    """
    user.last_login = timezone.now()
    user.save(update_fields=["last_login"])


class PermissionManager(models.Manager):
    use_in_migrations = True

    def get_by_natural_key(self, codename, app_label, model):
        return self.get(
            codename=codename,
            content_type=ContentType.objects.db_manager(self.db).get_by_natural_key(
                app_label, model
            ),
        )


class Permission(models.Model):
    """
    The permissions system provides a way to assign permissions to specific
    users and groups of users.

    The permission system is used by the Django admin site, but may also be
    useful in your own code. The Django admin site uses permissions as follows:

        - The "add" permission limits the user's ability to view the "add" form
          and add an object.
        - The "change" permission limits a user's ability to view the change
          list, view the "change" form and change an object.
        - The "delete" permission limits the ability to delete an object.
        - The "view" permission limits the ability to view an object.

    Permissions are set globally per type of object, not per specific object
    instance. It is possible to say "Mary may change news stories," but it's
    not currently possible to say "Mary may change news stories, but only the
    ones she created herself" or "Mary may only change news stories that have a
    certain status or publication date."

    The permissions listed above are automatically created for each model.
    """

    name = models.CharField(_("name"), max_length=255)
    content_type = models.ForeignKey(
        ContentType,
        models.CASCADE,
        verbose_name=_("content type"),
    )
    codename = models.CharField(_("codename"), max_length=100)

    objects = PermissionManager()

    class Meta:
        verbose_name = _("permission")
        verbose_name_plural = _("permissions")
        unique_together = [["content_type", "codename"]]
        ordering = ["content_type__app_label", "content_type__model", "codename"]

    def __str__(self):
        return "%s | %s" % (self.content_type, self.name)

    def natural_key(self):
        return (self.codename,) + self.content_type.natural_key()

    natural_key.dependencies = ["contenttypes.contenttype"]


class GroupManager(models.Manager):
    """
    The manager for the auth's Group model.
    """

    use_in_migrations = True

    def get_by_natural_key(self, name):
        return self.get(name=name)


class Group(models.Model):
    """
    Groups are a generic way of categorizing users to apply permissions, or
    some other label, to those users. A user can belong to any number of
    groups.

    A user in a group automatically has all the permissions granted to that
    group. For example, if the group 'Site editors' has the permission
    can_edit_home_page, any user in that group will have that permission.

    Beyond permissions, groups are a convenient way to categorize users to
    apply some label, or extended functionality, to them. For example, you
    could create a group 'Special users', and you could write code that would
    do special things to those users -- such as giving them access to a
    members-only portion of your site, or sending them members-only email
    messages.
    """

    name = models.CharField(_("name"), max_length=150, unique=True)
    permissions = models.ManyToManyField(
        Permission,
        verbose_name=_("permissions"),
        blank=True,
    )

    objects = GroupManager()

    class Meta:
        verbose_name = _("group")
        verbose_name_plural = _("groups")

    def __str__(self):
        return self.name

    def natural_key(self):
        return (self.name,)


class UserManager(BaseUserManager):
    use_in_migrations = True

    def _create_user(self, username, email, password, **extra_fields):
        """
        Create and save a user with the given username, email, and password.
        """
        if not username:
            raise ValueError("The given username must be set")
        email = self.normalize_email(email)
        # Lookup the real model class from the global app registry so this
        # manager method can be used in migrations. This is fine because
        # managers are by definition working on the real model.
        GlobalUserModel = apps.get_model(
            self.model._meta.app_label, self.model._meta.object_name
        )
        username = GlobalUserModel.normalize_username(username)
        user = self.model(username=username, email=email, **extra_fields)
        user.password = make_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, username, email=None, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)
        return self._create_user(username, email, password, **extra_fields)

    def create_superuser(self, username, email=None, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)

        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True.")

        return self._create_user(username, email, password, **extra_fields)

    def with_perm(
        self, perm, is_active=True, include_superusers=True, backend=None, obj=None
    ):
        if backend is None:
            backends = auth._get_backends(return_tuples=True)
            if len(backends) == 1:
                backend, _ = backends[0]
            else:
                raise ValueError(
                    "You have multiple authentication backends configured and "
                    "therefore must provide the `backend` argument."
                )
        elif not isinstance(backend, str):
            raise TypeError(
                "backend must be a dotted import path string (got %r)." % backend
            )
        else:
            backend = auth.load_backend(backend)
        if hasattr(backend, "with_perm"):
            return backend.with_perm(
                perm,
                is_active=is_active,
                include_superusers=include_superusers,
                obj=obj,
            )
        return self.none()


# A few helper functions for common logic between User and AnonymousUser.
def _user_get_permissions(user, obj, from_name):
    permissions = set()
    name = "get_%s_permissions" % from_name
    for backend in auth.get_backends():
        if hasattr(backend, name):
            permissions.update(getattr(backend, name)(user, obj))
    return permissions


def _user_has_perm(user, perm, obj):
    """
    A backend can raise `PermissionDenied` to short-circuit permission checking.
    """
    for backend in auth.get_backends():
        if not hasattr(backend, "has_perm"):
            continue
        try:
            if backend.has_perm(user, perm, obj):
                return True
        except PermissionDenied:
            return False
    return False


def _user_has_module_perms(user, app_label):
    """
    A backend can raise `PermissionDenied` to short-circuit permission checking.
    """
    for backend in auth.get_backends():
        if not hasattr(backend, "has_module_perms"):
            continue
        try:
            if backend.has_module_perms(user, app_label):
                return True
        except PermissionDenied:
            return False
    return False


class PermissionsMixin(models.Model):
    """
    Add the fields and methods necessary to support the Group and Permission
    models using the ModelBackend.
    """

    is_superuser = models.BooleanField(
        _("superuser status"),
        default=False,
        help_text=_(
            "Designates that this user has all permissions without "
            "explicitly assigning them."
        ),
    )
    groups = models.ManyToManyField(
        Group,
        verbose_name=_("groups"),
        blank=True,
        help_text=_(
            "The groups this user belongs to. A user will get all permissions "
            "granted to each of their groups."
        ),
        related_name="user_set",
        related_query_name="user",
    )
    user_permissions = models.ManyToManyField(
        Permission,
        verbose_name=_("user permissions"),
        blank=True,
        help_text=_("Specific permissions for this user."),
        related_name="user_set",
        related_query_name="user",
    )

    class Meta:
        abstract = True

    def get_user_permissions(self, obj=None):
        """
        Return a list of permission strings that this user has directly.
        Query all available auth backends. If an object is passed in,
        return only permissions matching this object.
        """
        return _user_get_permissions(self, obj, "user")

    def get_group_permissions(self, obj=None):
        """
        Return a list of permission strings that this user has through their
        groups. Query all available auth backends. If an object is passed in,
        return only permissions matching this object.
        """
        return _user_get_permissions(self, obj, "group")

    def get_all_permissions(self, obj=None):
        return _user_get_permissions(self, obj, "all")

    def has_perm(self, perm, obj=None):
        """
        Return True if the user has the specified permission. Query all
        available auth backends, but return immediately if any backend returns
        True. Thus, a user who has permission from a single auth backend is
        assumed to have permission in general. If an object is provided, check
        permissions for that object.
        """
        # Active superusers have all permissions.
        if self.is_active and self.is_superuser:
            return True

        # Otherwise we need to check the backends.
        return _user_has_perm(self, perm, obj)

    def has_perms(self, perm_list, obj=None):
        """
        Return True if the user has each of the specified permissions. If
        object is passed, check if the user has all required perms for it.
        """
        if not isinstance(perm_list, Iterable) or isinstance(perm_list, str):
            raise ValueError("perm_list must be an iterable of permissions.")
        return all(self.has_perm(perm, obj) for perm in perm_list)

    def has_module_perms(self, app_label):
        """
        Return True if the user has any permissions in the given app label.
        Use similar logic as has_perm(), above.
        """
        # Active superusers have all permissions.
        if self.is_active and self.is_superuser:
            return True

        return _user_has_module_perms(self, app_label)


def filepath(request, filename):
    old_filename = filename
    timeNow = datetime.datetime.now().strftime('%Y%m%d%H:%M:%S')
    filename = "%s%s" % (timeNow, old_filename)
    return os.path.join('uploads/', filename)
@cleanup.select
class AbstractUser(AbstractBaseUser, PermissionsMixin):
    """
    An abstract base class implementing a fully featured User model with
    admin-compliant permissions.

    Username and password are required. Other fields are optional.
    """

    username_validator = UnicodeUsernameValidator()

    username = models.CharField(
        _("username"),
        max_length=150,
        unique=False,
        help_text=_(
            "Required. 150 characters or fewer. Letters, digits and @/./+/-/_ only."
        ),
        validators=[username_validator],
        error_messages={
            "unique": _("A user with that username already exists."),
        },
    )

    gen = {
        "male":"male",
        "female":"female",
    }
    edu = {
        "Basic":"Basic",
        "Secondary":"Secondary",
        "Higher":"Higher",
        "Diploma":"Diploma",
        "Bachelor's":"Bachelor",
        "Master":"Master",
        "Doctorate":"Doctorate",
    }
    
    first_name = models.CharField(_("first name"), max_length=150, blank=True)
    last_name = models.CharField(_("last name"), max_length=150, blank=True)
    email = models.EmailField(_("email address"), unique = True, help_text=_("Required. 150 characters or fewer. Letters and reqiured @"))
    hobby = models.CharField(_("hobby"), max_length=150, blank=True)
    birth = models.DateField(_("birth"),null=True,  blank=True)
    address = models.CharField(_("address"), max_length=200, blank=True)
    country = models.CharField(_("country"), max_length=150, blank=True)
    phone = models.IntegerField(_("phone"), blank=True, default=0)
    gender = models.CharField(_("gender"), max_length=8, choices=gen,blank=True)
    education = models.CharField(_("education"), max_length=10, choices=edu,blank=True)
    university = models.ForeignKey(Universiti, on_delete=models.CASCADE, blank=True,null=True, verbose_name=_("university"))
    tiktok = models.CharField(_("tiktok"), max_length=200, blank=True)
    youtube = models.CharField(_("youtube"), max_length=200, blank=True)
    facebook = models.CharField(_("facebook"), max_length=200, blank=True)
    instagram = models.CharField(_("instagram"), max_length=200, blank=True)
    linkedin = models.CharField(_("linkedin"), max_length=200, blank=True)
    twitter = models.CharField(_("twitter"), max_length=200, blank=True)
    
    photo = models.ImageField(upload_to=filepath, null=True, blank=True)
    is_staff = models.BooleanField(
        _("staff status"),
        default=False,
        help_text=_("Designates whether the user can log into this admin site."),
    )
    is_member = models.BooleanField(
        _("member status"),
        default=False,
        help_text=_("Designates whether the user can log into this admin member."),
    )
    is_subscription = models.BooleanField(
        _("subscription status"),
        default=False,
        help_text=_("Designates whether the user can log into this admin subscription."),
    )
    is_instructor = models.BooleanField(
        _("instructor status"),
        default=False,
        help_text=_("Designates whether the user can log into this admin instructor."),
    )
    is_partner = models.BooleanField(
        _("partner status"),
        default=False,
        help_text=_("Designates whether the user can log into this admin partner."),
    )
    is_audit = models.BooleanField(
        _("audit status"),
        default=False,
        help_text=_("Designates whether the user can log into this admin audit."),
    )
    is_learner = models.BooleanField(
        _("learner status"),
        default=True,
        help_text=_("Designates whether the user can log into this admin learner."),
    )
    is_note = models.BooleanField(
        _("note status"),
        default=False,
        help_text=_("Designates whether the user can log into this admin note."),
    )
    is_active = models.BooleanField(
        _("active"),
        default=True,
        help_text=_(
            "Designates whether this user should be treated as active. "
            "Unselect this instead of deleting accounts."
        ),
    )

    date_joined = models.DateTimeField(_("date joined"), default=timezone.now)

    objects = UserManager()

    EMAIL_FIELD = "email"
    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["username"]

    class Meta:
        verbose_name = _("user")
        verbose_name_plural = _("users")
        abstract = True

    def clean(self):
        super().clean()
        self.email = self.__class__.objects.normalize_email(self.email)

    def get_full_name(self):
        """
        Return the first_name plus the last_name, with a space in between.
        """
        full_name = "%s %s" % (self.first_name, self.last_name)
        return full_name.strip()

    def get_short_name(self):
        """Return the short name for the user."""
        return self.first_name

    def email_user(self, subject, message, from_email=None, **kwargs):
        """Send an email to this user."""
        send_mail(subject, message, from_email, [self.email], **kwargs)

    def delete_old_photo(self):
        if self.pk:  # Hanya jika instance sudah ada di database
            old_photo = User.objects.filter(pk=self.pk).values_list('photo', flat=True).first()
            if old_photo and old_photo != self.photo.name:
                old_photo_path = os.path.join(settings.MEDIA_ROOT, old_photo)
                if os.path.exists(old_photo_path):
                    os.remove(old_photo_path)

    def save(self, *args, **kwargs):
        self.delete_old_photo()  # Hapus logo lama sebelum menyimpan
        super().save(*args, **kwargs)


class User(AbstractUser):
    """
    Users within the Django authentication system are represented by this
    model.

    Username and password are required. Other fields are optional.
    """

    class Meta(AbstractUser.Meta):
        swappable = "AUTH_USER_MODEL"


class AnonymousUser:
    id = None
    pk = None
    username = ""
    is_staff = False
    is_active = False
    is_superuser = False
    _groups = EmptyManager(Group)
    _user_permissions = EmptyManager(Permission)

    def __str__(self):
        return "AnonymousUser"

    def __eq__(self, other):
        return isinstance(other, self.__class__)

    def __hash__(self):
        return 1  # instances always return the same hash value

    def __int__(self):
        raise TypeError(
            "Cannot cast AnonymousUser to int. Are you trying to use it in place of "
            "User?"
        )

    def save(self):
        raise NotImplementedError(
            "Django doesn't provide a DB representation for AnonymousUser."
        )

    def delete(self):
        raise NotImplementedError(
            "Django doesn't provide a DB representation for AnonymousUser."
        )

    def set_password(self, raw_password):
        raise NotImplementedError(
            "Django doesn't provide a DB representation for AnonymousUser."
        )

    def check_password(self, raw_password):
        raise NotImplementedError(
            "Django doesn't provide a DB representation for AnonymousUser."
        )

    @property
    def groups(self):
        return self._groups

    @property
    def user_permissions(self):
        return self._user_permissions

    def get_user_permissions(self, obj=None):
        return _user_get_permissions(self, obj, "user")

    def get_group_permissions(self, obj=None):
        return set()

    def get_all_permissions(self, obj=None):
        return _user_get_permissions(self, obj, "all")

    def has_perm(self, perm, obj=None):
        return _user_has_perm(self, perm, obj=obj)

    def has_perms(self, perm_list, obj=None):
        if not isinstance(perm_list, Iterable) or isinstance(perm_list, str):
            raise ValueError("perm_list must be an iterable of permissions.")
        return all(self.has_perm(perm, obj) for perm in perm_list)

    def has_module_perms(self, module):
        return _user_has_module_perms(self, module)

    @property
    def is_anonymous(self):
        return True

    @property
    def is_authenticated(self):
        return False

    def get_username(self):
        return self.username
    
```
*****
### 10. Jalankan makemigrations:
```shell
python manage.py makemigrations
```

Catatan:
Pastikan Anda sudah menginstal **Python** sebelum menjalankan perintah ini.
dan Anda sudah menghapus semua isi dari folder migrations [course, auth, authentication]
**mysite\authentication\migrations**
contoh 001_ sd angka terbesar

### 11. Jalankan migrasi database:
```shell
python manage.py migrate
```
### 12. Jalankan server:
```shell
python manage.py runserver
```
### 13. Untuk membuat superuser:
```shell
python manage.py createsuperuser
```
****
Langkah-langkah untuk membuat superuser:

Masukkan email Anda, contoh: admin@admin.com
Masukkan username Anda, contoh: admin
Masukkan password Anda, contoh: admin
Ulangi password Anda
Pilih yes untuk melanjutkan
****
### 14. Jalankan Server:
```shell
python manage.py runserver
```
Akses url **http://127.0.0.1:8000/**
