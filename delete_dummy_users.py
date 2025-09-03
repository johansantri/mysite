#!/usr/bin/env python3
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mysite.settings')
django.setup()

from authentication.models import CustomUser
from django.db import transaction

BATCH_SIZE = 100000

def delete_dummy_users():
    total = CustomUser.objects.filter(email__endswith='@example.com').count()
    print(f"🔍 Menemukan {total} user dengan email @example.com")

    deleted = 0
    while True:
        # Ambil ID batch
        ids = list(
            CustomUser.objects.filter(email__endswith='@example.com')
            .values_list('id', flat=True)[:BATCH_SIZE]
        )
        if not ids:
            break

        with transaction.atomic():
            CustomUser.objects.filter(id__in=ids).delete()

        deleted += len(ids)
        print(f"✅ Terhapus: {deleted} dari {total}")

    print("🎉 Semua user dummy berhasil dihapus.")

if __name__ == "__main__":
    delete_dummy_users()
