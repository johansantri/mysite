import time
import json
import uuid
import base64
import logging
from typing import Dict, Any, Optional
import requests
import jwt
from jwt import PyJWKClient
from django.core.cache import cache
from django.conf import settings
from cryptography.hazmat.primitives import serialization

logger = logging.getLogger(__name__)

CACHE_TIMEOUT = 60 * 60  # 1 hour


def _cache_get(key):
    try:
        return cache.get(key)
    except Exception:
        return None


def _cache_set(key, value, timeout=CACHE_TIMEOUT):
    try:
        cache.set(key, value, timeout=timeout)
    except Exception:
        pass


def fetch_jwks(jwks_url: str) -> Dict[str, Any]:
    cache_key = f"lti_jwks::{jwks_url}"
    cached = _cache_get(cache_key)
    if cached:
        return cached
    resp = requests.get(jwks_url, timeout=15)
    resp.raise_for_status()
    jwks = resp.json()
    _cache_set(cache_key, jwks, CACHE_TIMEOUT)
    return jwks


def verify_id_token(id_token: str, tool) -> Dict[str, Any]:
    """
    Verifies id_token from Tool (Provider) using its JWKS.
    """
    # Get KID from header
    try:
        unverified_header = jwt.get_unverified_header(id_token)
        kid = unverified_header.get("kid")
        alg = unverified_header.get("alg", "RS256")
    except Exception as e:
        raise ValueError(f"Invalid JWT header: {e}")

    if alg != "RS256":
        raise ValueError(f"Unsupported alg {alg}")

    # Load JWKS
    jwks = fetch_jwks(tool.jwks_url)
    jwk_client = PyJWKClient(tool.jwks_url)
    signing_key = jwk_client.get_signing_key_from_jwt(id_token).key

    # Verify claims
    try:
        payload = jwt.decode(
            id_token,
            key=signing_key,
            algorithms=["RS256"],
            audience=tool.client_id,
            issuer=tool.issuer,
            options={
                "require": ["iss", "aud", "exp", "iat", "nonce"],
            },
        )
    except Exception as e:
        raise ValueError(f"JWT verification failed: {e}")

    return payload


def get_active_platform_key(tool) -> Optional[Dict[str, Any]]:
    pk = tool.platform_key or getattr(tool, "platform_key", None)
    if not pk:
        # fallback: active key
        from .models import PlatformKey
        pk = PlatformKey.objects.filter(active=True).order_by("-created_at").first()
    if not pk:
        return None
    return {
        "kid": pk.kid,
        "alg": pk.alg,
        "private_key_pem": pk.private_key_pem,
        "public_key_pem": pk.public_key_pem,
    }


def build_client_assertion(tool, token_url: str, now: Optional[int] = None) -> str:
    """
    Client Assertion JWT for OAuth2 client_credentials to the Tool's token endpoint.
    The Tool validates using Platform's public key (registered during tool registration).
    """
    key = get_active_platform_key(tool)
    if not key:
        raise RuntimeError("No active PlatformKey configured.")

    iat = int(now or time.time())
    exp = iat + 300  # 5 minutes
    payload = {
        "iss": tool.client_id,
        "sub": tool.client_id,
        "aud": token_url,
        "jti": uuid.uuid4().hex,
        "iat": iat,
        "exp": exp,
    }

    private_key = serialization.load_pem_private_key(
        key["private_key_pem"].encode("utf-8"),
        password=None,
    )
    headers = {"kid": key["kid"], "alg": key["alg"], "typ": "JWT"}

    assertion = jwt.encode(payload, private_key, algorithm=key["alg"], headers=headers)
    return assertion


def get_access_token(tool, scopes: Optional[str] = None) -> Dict[str, Any]:
    """
    Fetch OAuth2 access token from the Tool using client_credentials + JWT client_assertion.
    """
    assertion = build_client_assertion(tool, token_url=tool.auth_token_url)

    scope_str = scopes or (tool.scopes or "").replace("\n", " ").strip()
    data = {
        "grant_type": "client_credentials",
        "client_assertion_type": "urn:ietf:params:oauth:client-assertion-type:jwt-bearer",
        "client_assertion": assertion,
    }
    if scope_str:
        data["scope"] = scope_str

    resp = requests.post(tool.auth_token_url, data=data, timeout=20)
    try:
        resp.raise_for_status()
    except Exception as e:
        logger.exception("Token request failed: %s", resp.text)
        raise
    return resp.json()


def post_score_ags(tool, lineitem_url: str, score_payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Example: post a score to AGS /scores endpoint for a given lineitem.
    score_payload example (IMS spec):
    {
      "userId": "sub-123",
      "scoreGiven": 85,
      "scoreMaximum": 100,
      "activityProgress": "Completed",
      "gradingProgress": "FullyGraded",
      "timestamp": "2025-08-14T01:02:03Z"
    }
    """
    token = get_access_token(tool, scopes="https://purl.imsglobal.org/spec/lti-ags/scope/score")
    access_token = token["access_token"]
    url = lineitem_url.rstrip("/") + "/scores"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/vnd.ims.lis.v1.score+json",
    }
    resp = requests.post(url, headers=headers, json=score_payload, timeout=20)
    try:
        resp.raise_for_status()
    except Exception:
        logger.exception("Post score failed: %s", resp.text)
        raise
    return resp.json() if resp.text else {"status": "ok"}
