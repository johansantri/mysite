from django.core.management.base import BaseCommand
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization
from lti_consumer.models import PlatformKey
import uuid

class Command(BaseCommand):
    help = "Generate Platform RSA keypair (1 LMS : 1 key)"

    def handle(self, *args, **options):
        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        private_pem = key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        ).decode("utf-8")
        public_pem = key.public_key().public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        ).decode("utf-8")

        kid = uuid.uuid4().hex
        PlatformKey.objects.update_or_create(
            kid=kid,
            defaults={
                "private_key_pem": private_pem,
                "public_key_pem": public_pem,
                "active": True,
            },
        )
        self.stdout.write(self.style.SUCCESS(f"Created PlatformKey kid={kid}"))
