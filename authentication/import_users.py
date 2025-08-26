import csv
from datetime import datetime
from django.core.exceptions import ObjectDoesNotExist
from django.db import transaction
from authentication.models import CustomUser, Universiti

def import_users(csv_path):
    with open(csv_path, newline='', encoding='utf-8') as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            gender_map = {'male': 'M', 'female': 'F'}
            gender = gender_map.get(row.get('gender', '').lower(), None)
            if gender is None:
                gender = 'M'  # default gender jika kosong atau invalid

            edu_choices = {
                "Basic": "Basic",
                "Secondary": "Secondary",
                "Higher": "Higher",
                "Diploma": "Diploma",
                "Bachelor's": "Bachelor's",
                "Master": "Master",
                "Doctorate": "Doctorate",
            }
            education = edu_choices.get(row.get('education', ''), '')

            country_codes = [code for code, name in CustomUser.choice_country]
            country = row.get('country', '').lower()
            if country not in country_codes:
                country = 'id'

            birth_date = None
            birth_str = row.get('birth', '')
            if birth_str:
                try:
                    birth_date = datetime.strptime(birth_str, '%Y-%m-%d').date()
                except Exception:
                    print(f"Format tanggal salah di row: {row}")

            university = None
            uni_id = row.get('university_id', None)
            if uni_id:
                try:
                    university = Universiti.objects.get(id=uni_id)
                except ObjectDoesNotExist:
                    print(f"Universiti dengan id {uni_id} tidak ditemukan.")

            email = row.get('email')
            username = row.get('username')

            # Cek username bentrok dengan user lain selain email ini
            username_conflict = CustomUser.objects.filter(username=username).exclude(email=email).exists()
            if username_conflict:
                print(f"Username '{username}' sudah dipakai user lain, lewati user dengan email {email}")
                continue  # skip user ini agar tidak error

            with transaction.atomic():
                user, created = CustomUser.objects.update_or_create(
                    email=email,
                    defaults={
                        'username': username,
                        'phone': row.get('phone', ''),
                        'gender': gender,
                        'country': country,
                        'birth': birth_date,
                        'address': row.get('address', ''),
                        'hobby': row.get('hobby', ''),
                        'education': education,
                        'university': university,
                        'tiktok': row.get('tiktok', ''),
                        'youtube': row.get('youtube', ''),
                        'facebook': row.get('facebook', ''),
                        'instagram': row.get('instagram', ''),
                        'linkedin': row.get('linkedin', ''),
                        'twitter': row.get('twitter', ''),
                        'is_member': row.get('is_member', '').lower() == 'true',
                        'is_subscription': row.get('is_subscription', '').lower() == 'true',
                        'is_instructor': row.get('is_instructor', '').lower() == 'true',
                        'is_partner': row.get('is_partner', '').lower() == 'true',
                        'is_audit': row.get('is_audit', '').lower() == 'true',
                        'is_learner': row.get('is_learner', '').lower() != 'false',
                        'is_note': row.get('is_note', '').lower() == 'true',
                    }
                )
                if created:
                    print(f"User {user.email} dibuat.")
                else:
                    print(f"User {user.email} diupdate.")
