from openedx_rest_api_client.client import OpenEdXAPIClient

# Konfigurasi API (ganti dengan kredensial Open edX Anda)
BASE_URL = "https://satu.icei.ac.id"
ACCESS_TOKEN = "NrXIsNCRGi0qfZF7mgf6T1aqRlD3Lq"

def fetch_openedx_courses():
    """Mengambil data courses dari Open edX API."""
    client = OpenEdXAPIClient(BASE_URL, ACCESS_TOKEN)
    courses = client.courses.get()
    return courses
