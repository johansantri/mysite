from django.db import models
from django.core.validators import URLValidator
from django.utils import timezone
from courses.models import Assessment
class PlatformKey(models.Model):
    """
    1 LMS : 1 PlatformKey (sesuai preferensi kamu).
    Jika kamu sudah punya, silakan pakai yang existing dan abaikan model ini.
    """
    kid = models.CharField(max_length=128, unique=True)
    alg = models.CharField(max_length=10, default="RS256")
    private_key_pem = models.TextField()
    public_key_pem = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    active = models.BooleanField(default=True)

    def __str__(self):
        return f"PlatformKey(kid={self.kid}, active={self.active})"


class LTIExternalTool(models.Model):
    """
    Registrasi Tool Provider (LTI 1.3).
    """
    name = models.CharField(max_length=255)
    # Tool assigns a client_id to the Platform (your LMS)
    client_id = models.CharField(max_length=255)
    # Deployment ID associated with placements
    deployment_id = models.CharField(max_length=255)

    # Tool endpoints
    auth_login_url = models.URLField(validators=[URLValidator()])
    auth_token_url = models.URLField(validators=[URLValidator()])
    jwks_url = models.URLField(validators=[URLValidator()])
    issuer = models.CharField(max_length=1024, help_text="The Tool's iss in id_token")

    # Optional for Deep Linking flow
    deep_linking_supported = models.BooleanField(default=False)

    # Scopes (untuk LTI Advantage services)
    scopes = models.TextField(
        blank=True,
        help_text="Space/newline separated scopes, e.g. https://purl.imsglobal.org/spec/lti-ags/scope/score",
    )

    # Platform key to sign client_assertion (or leave null to use active default)
    platform_key = models.ForeignKey(
        PlatformKey, on_delete=models.SET_NULL, null=True, blank=True, related_name="tools"
    )

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} ({self.client_id})"


class LTILink(models.Model):
    """
    Menghubungkan resource di LMS kamu ke Tool resource (resource_link_id atau deep linking result).
    Biasanya dihubungkan ke Course/Assessment kamu (FK disederhanakan).
    """
    tool = models.ForeignKey(LTIExternalTool, on_delete=models.CASCADE, related_name="links")
    assessment = models.OneToOneField('courses.Assessment', on_delete=models.CASCADE, related_name='lti13_link',null=True,blank=True)
    title = models.CharField(max_length=255)
    # Resource Link ID disediakan tool pada launch (claim resource_link)
    resource_link_id = models.CharField(max_length=255, blank=True, null=True)
    # Target link URI untuk kembali saat launch (di LMS)
    target_link_uri = models.URLField(validators=[URLValidator()])
    # Custom params yg ingin kamu kirim saat login initiation (optional)
    custom_params = models.JSONField(default=dict, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"[{self.tool.name}] {self.title}"


class LTILaunchLog(models.Model):
    """
    Log semua launch untuk audit/periksa error.
    """
    tool = models.ForeignKey(LTIExternalTool, on_delete=models.SET_NULL, null=True)
    link = models.ForeignKey(LTILink, on_delete=models.SET_NULL, null=True, blank=True)
    user_id_hint = models.CharField(max_length=128, blank=True, null=True)
    state = models.CharField(max_length=64)
    nonce = models.CharField(max_length=64)
    success = models.BooleanField(default=False)
    error = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(default=timezone.now)
    raw_payload = models.JSONField(default=dict, blank=True)

    def __str__(self):
        status = "OK" if self.success else "ERR"
        return f"{status} {self.tool} {self.created_at:%Y-%m-%d %H:%M:%S}"
