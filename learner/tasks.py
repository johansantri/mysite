# your_app/tasks.py
from celery import shared_task
from django.utils import timezone
from datetime import timedelta
from courses.models import CourseSessionLog  # Ganti dengan path model Anda
import logging

logger = logging.getLogger(__name__)

@shared_task
def close_idle_sessions():
    threshold = timezone.now() - timedelta(minutes=30)
    idle_sessions = CourseSessionLog.objects.filter(
        ended_at__isnull=True,
        started_at__lt=threshold
    )
    closed_count = 0
    for session in idle_sessions:
        session.ended_at = timezone.now()
        session.save()  # Ini akan menghitung duration_seconds
        logger.info(f"Auto-closed idle session for user {session.user.id}, course {session.course.id}, duration: {session.duration_seconds} seconds")
        closed_count += 1
    logger.info(f"Closed {closed_count} idle sessions")