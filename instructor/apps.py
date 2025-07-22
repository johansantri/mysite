from django.apps import AppConfig


class InstructorConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'instructor'
    def ready(self):
        import instructor.signals  # sesuaikan path-nya
