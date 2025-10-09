# payments/utils.py

import requests
from django.conf import settings
import logging
from payments.models import Voucher
import json
import hashlib
import hmac
import json
import time
import requests
from django.conf import settings

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




#untuk get merchant api tripay


def get_tripay_payment_channels():
    url = "https://tripay.co.id/api-sandbox/merchant/payment-channel"
    headers = {
        "Authorization": f"Bearer {settings.TRIPAY_API_KEY}",
    }

    try:
        print("➡️  Request to:", url)
        print("🔐  Using API Key:", settings.TRIPAY_API_KEY[:8] + "..." if settings.TRIPAY_API_KEY else "Not set")
        print("📨  Headers:", headers)

        response = requests.get(url, headers=headers)

        print("📥 Status Code:", response.status_code)
        print("📦 Response Text:", response.text)  # INI YANG HARUS KAMU KIRIM
        try:
            parsed = response.json()
            print("📦 Parsed JSON:", json.dumps(parsed, indent=2))
        except Exception as e:
            print("❌ Gagal parse JSON:", e)

        if response.status_code == 200:
            return parsed.get('data', [])

        # Error message dari Tripay
        print("⚠️ Tripay Error Message:", parsed.get("message", "Tidak diketahui"))

    except requests.RequestException as e:
        print("🔥 Request error:", e)

    return []

def create_tripay_transaction(transaction, payment_method, user):
    merchant_code = settings.TRIPAY_MERCHANT_CODE
    private_key = settings.TRIPAY_PRIVATE_KEY
    api_key = settings.TRIPAY_API_KEY
    expired_time = int(time.time()) + 3600  # 1 jam dari sekarang

    amount = int(transaction.total_amount)
    merchant_ref = transaction.merchant_ref

    # Generate signature
    signature_str = merchant_code + merchant_ref + str(amount)
    signature = hmac.new(
        private_key.encode(),
        signature_str.encode(),
        hashlib.sha256
    ).hexdigest()

    # Buat item pesanan
    order_items = []
    for payment in transaction.payments.all():
        order_items.append({
            "name": payment.course.course_name,
            "price": int(payment.snapshot_user_payment),
            "quantity": 1,
        })

    # Tambahkan biaya platform sebagai item tambahan
    order_items.append({
        "name": "Platform Fee",
        "price": int(transaction.platform_fee),
        "quantity": 1,
    })

    # Payload yang akan dikirim ke Tripay
    payload = {
        "method": payment_method,
        "merchant_ref": merchant_ref,
        "amount": amount,
        "customer_name": user.get_full_name(),
        "customer_email": user.email,
        "order_items": order_items,
        "return_url": "https://yourdomain.com/payment/return/",  # <- Ganti dengan URL yang sesuai
        "expired_time": expired_time,
        "signature": signature,
    }

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    try:
        resp = requests.post("https://tripay.co.id/api-sandbox/transaction/create", json=payload, headers=headers)
        result = resp.json()
    except requests.RequestException as e:
        raise Exception(f"Gagal terhubung ke Tripay: {str(e)}")
    except ValueError:
        raise Exception("Respon dari Tripay tidak valid")

    if result.get('success'):
        data = result.get('data', {})
        va_number = (
            data.get('pay_code') or
            data.get('payment_no') or
            data.get('virtual_account') or
            data.get('va_number') or
            
            ""
        )
        payment_url = data.get('checkout_url') or ""
        bank_name = data.get('payment_name', '')  # ← tambahkan ini
        return va_number, bank_name, payment_url
    else:
        raise Exception(f"Tripay error: {result.get('message', 'Tidak diketahui')}")