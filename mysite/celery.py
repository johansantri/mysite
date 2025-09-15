# mysite/mysite/celery.py
import os
from celery import Celery

# Setel modul pengaturan default Django untuk Celery
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mysite.settings')

# Buat instance aplikasi Celery
app = Celery('mysite')

# Muat konfigurasi dari settings.py dengan namespace 'CELERY'
app.config_from_object('django.conf:settings', namespace='CELERY')

# Auto-discover tasks di semua aplikasi Django yang terinstal
app.autodiscover_tasks()