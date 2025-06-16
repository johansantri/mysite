# partner/utils.py
import requests

def get_geo_from_ip(ip):
    try:
        response = requests.get(f"http://ip-api.com/json/{ip}")
        data = response.json()
        if data['status'] == 'success':
            return data['country'], data['city']
    except Exception:
        pass
    return None, None