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

    amount = int(transaction.total_amount * 100) / 100  # Pastikan integer rupiah, tapi Decimal OK
    merchant_ref = transaction.merchant_ref

    # Generate signature sesuai docs
    signature_str = merchant_code + merchant_ref + str(int(amount))
    signature = hmac.new(
        private_key.encode('utf-8'),
        signature_str.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()

    # Buat order_items
    order_items = []
    for payment in transaction.payments.all():
        order_items.append({
            "name": payment.course.course_name,
            "price": int(payment.amount),  # snapshot_user_payment atau amount
            "quantity": 1,
        })

    # Tambahkan platform fee sebagai item
    if transaction.platform_fee > 0:
        order_items.append({
            "name": "Platform Fee",
            "price": int(transaction.platform_fee),
            "quantity": 1,
        })

    # Payload lengkap sesuai docs Tripay
    payload = {
        "method": payment_method,
        "merchant_ref": merchant_ref,
        "amount": int(amount),
        "customer_name": user.get_full_name() or "Pelanggan",
        "customer_email": user.email,
        "order_items": order_items,
        "return_url": "https://ini.icei.ac.id/payments/return/",  # Ganti dengan domain real (redirect setelah bayar)
        "callback_url": "https://ini.icei.ac.id/payments/tripay-callback/",  # Webhook untuk update status
        "expired_time": expired_time,
        "signature": signature,
    }

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    # API endpoint (sandbox; ganti ke production kalau live)
    url = "https://tripay.co.id/api-sandbox/transaction/create"

    try:
        resp = requests.post(url, json=payload, headers=headers, timeout=30)
        result = resp.json()
        logger.info(f"Tripay response: {result}")
    except requests.RequestException as e:
        logger.error(f"Request error: {e}")
        raise Exception(f"Gagal terhubung ke Tripay: {str(e)}")
    except ValueError as e:
        logger.error(f"JSON parse error: {e}")
        raise Exception("Respon dari Tripay tidak valid")

    if result.get('success'):
        data = result.get('data', {})
        if not data or not isinstance(data, dict):
            raise Exception("Data Tripay kosong atau tidak valid")

        va_number = (
            data.get('pay_code') or
            data.get('virtual_account') or
            data.get('payment_no') or
            data.get('va_number') or
            ""
        )
        bank_name = data.get('payment_name', '')
        payment_url = data.get('checkout_url') or data.get('pay_url') or ""
        tripay_transaction_id = data.get('reference', '')
        instructions = data.get('instructions', [])
        tripay_expired_time = data.get('expired_time', expired_time)
        
        return va_number, bank_name, payment_url, tripay_transaction_id, instructions, tripay_expired_time
    else:
        error_msg = result.get('message', 'Tidak diketahui')
        raise Exception(f"Tripay error: {error_msg}")