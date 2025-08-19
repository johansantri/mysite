import uuid
import logging
from urllib.parse import urlencode
from django.shortcuts import redirect, get_object_or_404, render
from django.views.decorators.csrf import csrf_exempt
from django.http import HttpResponseBadRequest, HttpResponse
from django.conf import settings
from django.utils import timezone

from .models import LTIExternalTool, LTILink, LTILaunchLog
from .utils import verify_id_token

logger = logging.getLogger(__name__)

def _platform_iss(request) -> str:
    """
    ISS milik Platform (LMS kamu). Pastikan sesuai registrasi di Tool.
    Contoh: https://lms.example.com
    """
    return getattr(settings, "LTI_PLATFORM_ISS", "").rstrip("/")


def lti_launch_request(request, link_id: int):
    """
    Login Initiation (Platform -> Tool).
    """
    link = get_object_or_404(LTILink, pk=link_id)
    tool = link.tool

    if not request.user.is_authenticated:
        # kamu bisa redirect ke login dulu
        return redirect(f"/login/?next={request.get_full_path()}")

    state = uuid.uuid4().hex
    nonce = uuid.uuid4().hex

    request.session["lti_state"] = state
    request.session["lti_nonce"] = nonce
    request.session["lti_link_id"] = link.id

    # Untuk OIDC login initiation
    params = {
        "iss": _platform_iss(request),
        "login_hint": str(request.user.pk),
        "target_link_uri": link.target_link_uri,  # URL di LMS yang menerima id_token
        "lti_message_hint": tool.deployment_id,  # opsional tapi umum dipakai
        "client_id": tool.client_id,
        "state": state,
        "nonce": nonce,
    }
    # custom params (opsional)
    if link.custom_params:
        for k, v in link.custom_params.items():
            params[f"custom_{k}"] = v

    # Simpan log awal
    LTILaunchLog.objects.create(
        tool=tool,
        link=link,
        user_id_hint=str(request.user.pk),
        state=state,
        nonce=nonce,
        success=False,
    )

    return redirect(f"{tool.auth_login_url}?{urlencode(params)}")


@csrf_exempt
def lti_launch_response(request):
    """
    Menerima id_token (Tool -> Platform).
    """
    id_token = request.POST.get("id_token")
    state = request.POST.get("state")

    if not id_token or not state:
        return HttpResponseBadRequest("Missing id_token or state")

    saved_state = request.session.get("lti_state")
    saved_nonce = request.session.get("lti_nonce")
    link_id = request.session.get("lti_link_id")

    if not saved_state or state != saved_state:
        return HttpResponseBadRequest("Invalid state")

    link = None
    tool = None
    if link_id:
        link = LTILink.objects.filter(pk=link_id).select_related("tool").first()
        tool = link.tool if link else None
    if not tool:
        # fallback kalau link tidak ditemukan—di environment nyata, mapping bisa via `aud/client_id` atau `iss`
        tool = LTIExternalTool.objects.first()

    if not tool:
        return HttpResponseBadRequest("Tool not configured")

    # Verifikasi id_token
    try:
        payload = verify_id_token(id_token, tool)
    except Exception as e:
        LTILaunchLog.objects.filter(state=saved_state).update(success=False, error=str(e), raw_payload={"raw": "verify_failed"})
        return HttpResponseBadRequest(f"Token verification failed: {e}")

    # Validasi nonce
    token_nonce = payload.get("nonce")
    if token_nonce != saved_nonce:
        LTILaunchLog.objects.filter(state=saved_state).update(success=False, error="Nonce mismatch", raw_payload=payload)
        return HttpResponseBadRequest("Invalid nonce")

    # Validasi deployment_id
    deployment = payload.get("https://purl.imsglobal.org/spec/lti/claim/deployment_id")
    if deployment and deployment != tool.deployment_id:
        LTILaunchLog.objects.filter(state=saved_state).update(success=False, error="Deployment mismatch", raw_payload=payload)
        return HttpResponseBadRequest("Invalid deployment_id")

    # Extract important claims
    message_type = payload.get("https://purl.imsglobal.org/spec/lti/claim/message_type")
    version = payload.get("https://purl.imsglobal.org/spec/lti/claim/version")
    resource_link = (payload.get("https://purl.imsglobal.org/spec/lti/claim/resource_link") or {}).get("id")
    roles = payload.get("https://purl.imsglobal.org/spec/lti/claim/roles") or []
    sub = payload.get("sub")
    name = (payload.get("name")) or (payload.get("given_name"))  # depends on tool
    email = payload.get("email")

    # SSO / sinkronisasi user lokal (opsional)
    # - mapping sub-> user lokal
    # - enroll otomatis ke course, dsb.

    # Tandai success
    LTILaunchLog.objects.filter(state=saved_state).update(success=True, error=None, raw_payload=payload)

    # Deep Linking flow (opsional)
    if message_type == "LtiDeepLinkingResponse":
        # Ambil content-items dan buat LTILink baru berdasarkan deep link result
        deep_linking_data = payload.get("https://purl.imsglobal.org/spec/lti-dl/claim/content_items") or []
        # TODO: parse & simpan sesuai kebutuhanmu
        return render(request, "lti_consumer/deep_link_success.html", {"items": deep_linking_data})

    # ResourceLinkRequest (umum)
    if message_type in ("LtiResourceLinkRequest", "LtiSubmissionReviewRequest"):
        # Render halaman container (iframe) atau redirect ke tampilan course kamu.
        context = {
            "who": name or email or sub,
            "roles": roles,
            "resource_link_id": resource_link,
            "payload": payload,
            "now": timezone.now(),
        }
        return render(request, "lti_consumer/launch_success.html", context)

    # Message type lain
    return HttpResponse(f"LTI Launch OK. message_type={message_type}, version={version}")
