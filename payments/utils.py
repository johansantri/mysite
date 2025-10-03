# payments/utils.py

import requests
import logging
from payments.models import Voucher
logger = logging.getLogger(__name__)

def get_client_ip(request):
    """Ambil IP address dari request"""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0].strip()
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip

def get_geo_from_ip(ip):
    """Ambil data lokasi dari IP address menggunakan ip-api"""
    try:
        response = requests.get(f"http://ip-api.com/json/{ip}", timeout=2)
        data = response.json()
        if data.get('status') == 'success':
            return {
                'ip': ip,
                'city': data.get('city', ''),
                'region': data.get('regionName', ''),
                'country': data.get('country', ''),
                'lat': data.get('lat'),
                'lon': data.get('lon'),
                'isp': data.get('isp', ''),
            }
        else:
            logger.warning(f"IP geo lookup failed: {data.get('message')}")
    except Exception as e:
        logger.exception(f"GeoIP lookup failed for IP {ip}")
    return None
def validate_voucher(voucher_code, user):
    if not voucher_code:
        return None, None
    voucher_obj = Voucher.objects.filter(code__iexact=voucher_code).first()
    if not voucher_obj:
        return None, "Kode voucher tidak valid."
    is_valid, error_msg = voucher_obj.is_valid_for_user(user)
    if not is_valid:
        return None, error_msg
    return voucher_obj, None
