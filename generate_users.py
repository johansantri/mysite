import os
import django

# Tetapkan settings project Django kamu
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mysite.settings')
django.setup()
from authentication.models import CustomUser, Universiti
from django.db import transaction
from faker import Faker
import random
from tqdm import tqdm
import uuid
import os
import django

# Setup Django jika dijalankan sebagai standalone script
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mysite.settings')
django.setup()

fake = Faker()
batch_size = 10000
total_users = 1000000

universitas_ids = list(Universiti.objects.values_list('id', flat=True))
users_to_create = []

for i in tqdm(range(total_users), desc="Creating users"):
    username = f"{fake.user_name()}_{uuid.uuid4().hex[:6]}"
    email = f"{username}@example.com"

    user = CustomUser(
        username=username,
        email=email,
        phone=fake.phone_number(),
        gender=random.choice(['male', 'female']),
        country=random.choice([code for code, _ in CustomUser.choice_country]),
        birth=fake.date_of_birth(minimum_age=18, maximum_age=60),
        address=fake.address(),
        hobby=fake.word(),
        education=random.choice(list(CustomUser.edu.keys())),
        university_id=random.choice(universitas_ids) if universitas_ids else None,
        is_learner=True,
        is_instructor=False,
        is_partner=False,
    )
    users_to_create.append(user)

    if len(users_to_create) >= batch_size:
        with transaction.atomic():
            CustomUser.objects.bulk_create(users_to_create, ignore_conflicts=True)
        users_to_create = []

# Insert sisa data
if users_to_create:
    with transaction.atomic():
        CustomUser.objects.bulk_create(users_to_create, ignore_conflicts=True)

print("✅ Done inserting 1 juta users!")
