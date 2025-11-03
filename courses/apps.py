from django.apps import AppConfig
from django.db.models.signals import post_migrate


class CoursesConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'courses'

    def ready(self):
        from .models import PricingType

        def create_default_pricing_types(sender, **kwargs):
            defaults = [
                ('free', 'Free', 'Gratis untuk semua pengguna'),
                ('buy_first', 'Buy First', 'Bayar di awal sebelum akses kursus'),
                ('buy_take_exam', 'Buy Take Exam', 'Bayar hanya untuk mengikuti ujian'),
                ('pay_only_certificate', 'Pay Only Certificate', 'Bayar hanya untuk sertifikat'),
            ]
            for code, name, desc in defaults:
                PricingType.objects.get_or_create(
                    code=code,
                    defaults={'name': name, 'description': desc}
                )

        # Daftarkan ke event post_migrate agar otomatis setelah migrate
        post_migrate.connect(create_default_pricing_types, sender=self)
