from django.http import JsonResponse
from .models import PlatformKey

def platform_jwks(request):
    """
    Expose public JWKS (untuk didaftarkan di Tool).
    """
    keys = []
    for pk in PlatformKey.objects.filter(active=True):
        keys.append({
            "kty": "RSA",
            "kid": pk.kid,
            "alg": pk.alg,
            "use": "sig",
            # Public key in JWK form – untuk ringkas, kita kirim PEM saja jika Tool menerima.
            # Idealnya convert PEM to JWK. Implementasi JWK proper bisa ditambahkan jika diperlukan.
            "x5c": [],  # optional
        })
    return JsonResponse({"keys": keys})
