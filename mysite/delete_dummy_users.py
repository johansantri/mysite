#!/usr/bin/env python3
import os
import django

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mysite.settings')
django.setup()

from authentication.models import CustomUser
from django.db import transaction

# Konfigurasi
BATCH_SIZE = 10000

def delete_dummy_users():
    queryset = CustomUser.objects.filter(email__endswith='@example.com')
    total = queryset.count()

    print(f"🔍 Menemukan {total} user dengan email @example.com")

    deleted = 0
    while queryset.exists():
        batch = queryset[:BATCH_SIZE]
        with transaction.atomic():
            batch.delete()
        deleted += len(batch)
        print(f"✅ Terhapus: {deleted} dari {total}")

    print("🎉 Semua user dummy berhasil dihapus.")

if __name__ == "__main__":
    delete_dummy_users()
