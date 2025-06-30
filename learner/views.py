import csv
import logging
import uuid
import base64
import hmac
import hashlib
import urllib.parse
from urllib.parse import urlparse, urlunparse,quote, urlencode
from datetime import datetime
import time
import pytz
from datetime import timedelta
from decimal import Decimal
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.mail import send_mail
from django.core.paginator import Paginator
from django.db.models import Avg, Count, Prefetch, F
from django.db import transaction
from django.http import HttpResponse, HttpResponseRedirect, JsonResponse,HttpResponseBadRequest,HttpResponseForbidden
from django.shortcuts import get_object_or_404, render,redirect
from django.urls import reverse, NoReverseMatch
from django.utils import timezone
from django.template.defaultfilters import linebreaks

from django.middleware.csrf import get_token
from authentication.models import CustomUser, Universiti
from django.template.loader import render_to_string
from courses.models import (
    Assessment, AssessmentRead, AssessmentScore, AssessmentSession,
    AskOra, Choice, Comment, Course, CourseProgress, CourseStatusHistory,
    Enrollment, GradeRange, Instructor, LTIExternalTool, Material,
    MaterialRead, Payment, PeerReview, Question, QuestionAnswer,
    Score, Section, Submission, UserActivityLog, CommentReaction, AttemptedQuestion,
    LTIPlatform,
)

logger = logging.getLogger(__name__)







def _build_combined_content(sections):
    """
    Build a list of combined content (materials and assessments) from sections.
    
    Args:
        sections: QuerySet of Section objects.
    
    Returns:
        List of tuples: (content_type, content_object, section).
    """
    combined_content = []
    for section in sections:
        for material in section.materials.all():
            combined_content.append(('material', material, section))
        for assessment in section.assessments.all():
            combined_content.append(('assessment', assessment, section))
    return combined_content



def _build_assessment_context(assessment, user):
    """
    Build context for assessment-related data.
    Includes AskOra, submissions, peer reviews, quiz flags.
    """
    # Periksa apakah asesmen memiliki alat LTI terkait
    lti_tool = assessment.lti_tools.first()  # Ambil alat LTI pertama (jika ada)
    if lti_tool:
        return {
            'ask_oras': [],
            'user_submissions': [],
            'askora_submit_status': {},
            'askora_can_submit': {},
            'can_review': False,
            'submissions': [],
            'has_other_submissions': False,
            'is_quiz': False,
            'peer_review_stats': None,
            'is_lti': True,
            'lti_tool': lti_tool,  # Sertakan objek LTIExternalTool untuk digunakan di template
        }

    # --- Lanjutan untuk assessment biasa (non-LTI) ---
    ask_oras = AskOra.objects.filter(assessment=assessment)
    user_submissions = Submission.objects.filter(askora__assessment=assessment, user=user)
    submitted_askora_ids = set(user_submissions.values_list('askora_id', flat=True))
    now = timezone.now()

    submissions = Submission.objects.filter(
        askora__assessment=assessment
    ).exclude(user=user).exclude(
        id__in=PeerReview.objects.filter(reviewer=user).values('submission__id')
    )

    has_other_submissions = Submission.objects.filter(
        askora__assessment=assessment
    ).exclude(user=user).exists()

    context = {
        'ask_oras': ask_oras,
        'user_submissions': user_submissions,
        'askora_submit_status': {askora.id: (askora.id in submitted_askora_ids) for askora in ask_oras},
        'askora_can_submit': {
            askora.id: (
                askora.id not in submitted_askora_ids and
                askora.is_responsive and
                (askora.response_deadline is None or askora.response_deadline > now)
            ) for askora in ask_oras
        },
        'can_review': submissions.exists(),
        'submissions': submissions,
        'has_other_submissions': has_other_submissions,
        'is_quiz': assessment.questions.exists(),
        'peer_review_stats': None,
        'is_lti': False,
    }

    if user_submissions.exists():
        total_participants = Submission.objects.filter(
            askora__assessment=assessment
        ).values('user').distinct().count()
        user_reviews = PeerReview.objects.filter(
            submission__in=user_submissions
        ).aggregate(
            total_reviews=Count('id'),
            distinct_reviewers=Count('reviewer', distinct=True)
        )
        context['peer_review_stats'] = {
            'total_reviews': user_reviews['total_reviews'] or 0,
            'distinct_reviewers': user_reviews['distinct_reviewers'] or 0,
            'total_participants': total_participants - 1,
            'completed': user_reviews['distinct_reviewers'] >= (total_participants - 1)
        }
        if user_reviews['total_reviews'] > 0:
            avg_score = PeerReview.objects.filter(
                submission__in=user_submissions
            ).aggregate(avg_score=Avg('score'))['avg_score']
            context['peer_review_stats']['avg_score'] = round(avg_score, 2) if avg_score else None

    return context

@login_required
def toggle_reaction(request, comment_id, reaction_type):
    if request.method != 'POST':
        logger.warning(f"Invalid request method: {request.method} for toggle_reaction")
        return HttpResponse(status=400)

    if reaction_type not in ['like', 'dislike']:
        logger.warning(f"Invalid reaction_type: {reaction_type}")
        return HttpResponse(status=400)

    comment = get_object_or_404(Comment, id=comment_id)
    material = comment.material
    reaction_value = CommentReaction.REACTION_LIKE if reaction_type == 'like' else CommentReaction.REACTION_DISLIKE

    try:
        with transaction.atomic():
            existing_reaction = CommentReaction.objects.filter(user=request.user, comment=comment).first()
            if existing_reaction:
                if existing_reaction.reaction_type == reaction_value:
                    existing_reaction.delete()
                    if reaction_value == CommentReaction.REACTION_LIKE:
                        Comment.objects.filter(id=comment_id).update(likes=F('likes') - 1)
                    else:
                        Comment.objects.filter(id=comment_id).update(dislikes=F('dislikes') - 1)
                else:
                    existing_reaction.delete()
                    CommentReaction.objects.create(user=request.user, comment=comment, reaction_type=reaction_value)
                    if reaction_value == CommentReaction.REACTION_LIKE:
                        Comment.objects.filter(id=comment_id).update(likes=F('likes') + 1, dislikes=F('dislikes') - 1)
                    else:
                        Comment.objects.filter(id=comment_id).update(dislikes=F('dislikes') + 1, likes=F('likes') - 1)
            else:
                CommentReaction.objects.create(user=request.user, comment=comment, reaction_type=reaction_value)
                if reaction_value == CommentReaction.REACTION_LIKE:
                    Comment.objects.filter(id=comment_id).update(likes=F('likes') + 1)
                else:
                    Comment.objects.filter(id=comment_id).update(dislikes=F('dislikes') + 1)

        is_htmx = request.headers.get('HX-Request') == 'true'
        if is_htmx:
            comment.refresh_from_db()
            user_reactions = {
                r.comment_id: r.reaction_type
                for r in CommentReaction.objects.filter(user=request.user, comment__material=material)
            }
            level = int(request.GET.get('level', 0))
            html = render_to_string(
                'learner/partials/comment.html',
                {
                    'comment': comment,
                    'material': material,
                    'user_reactions': user_reactions,
                    'level': level,
                },
                request=request
            )
            return HttpResponse(html)

        redirect_url = reverse('learner:load_content', kwargs={
            'username': request.user.username,
            'slug': material.section.course.slug,
            'content_type': 'material',
            'content_id': material.id
        })
        return HttpResponseRedirect(redirect_url)

    except Exception as e:
        logger.error(f"Error toggling reaction for comment {comment_id}: {str(e)}", exc_info=True)
        if request.headers.get('HX-Request') == 'true':
            return HttpResponse("Terjadi kesalahan saat memproses reaksi.", status=500)
        return HttpResponse(status=500)


logger = logging.getLogger(__name__)


def _get_navigation_urls(username, id, slug, combined_content, current_index):
    """
    Menghasilkan URL sebelumnya dan berikutnya untuk navigasi konten.
    
    Args:
        username: Nama pengguna.
        id: ID kursus.
        slug: Slug kursus.
        combined_content: Daftar konten gabungan (material/assessment).
        current_index: Indeks konten saat ini.
    
    Returns:
        Tuple: (previous_url, next_url).
    """
    previous_url = None
    next_url = None
    try:
        if current_index > 0:
            prev_content = combined_content[current_index - 1]
            previous_url = reverse('learner:load_content', kwargs={
                'username': username,
                'id': id,  # Sertakan id
                'slug': slug,
                'content_type': prev_content[0],
                'content_id': prev_content[1].id
            })
        if current_index < len(combined_content) - 1:
            next_content = combined_content[current_index + 1]
            next_url = reverse('learner:load_content', kwargs={
                'username': username,
                'id': id,  # Sertakan id
                'slug': slug,
                'content_type': next_content[0],
                'content_id': next_content[1].id
            })
    except NoReverseMatch as e:
        logger.error(f"NoReverseMatch di _get_navigation_urls: {str(e)}")
        previous_url = None
        next_url = None
    return previous_url, next_url

@login_required
def my_course(request, username, id, slug):
    if request.user.username != username:
        logger.warning(f"Upaya akses tidak sah oleh {request.user.username} untuk {username}")
        return HttpResponse(status=403)

    course = get_object_or_404(Course, id=id, slug=slug)
    if not Enrollment.objects.filter(user=request.user, course=course).exists():
        logger.warning(f"Pengguna {request.user.username} tidak terdaftar di kursus {slug}")
        return HttpResponse(status=403)

    sections = Section.objects.filter(courses=course).prefetch_related(
        Prefetch('materials', queryset=Material.objects.all()),
        Prefetch('assessments', queryset=Assessment.objects.all())
    ).order_by('order')
    combined_content = _build_combined_content(sections)
    total_content = len(combined_content)

    context = {
        'course': course,
        'course_name': course.course_name,
        'username': username,
        'slug': slug,
        'sections': sections,
        'current_content': None,
        'material': None,
        'assessment': None,
        'comments': None,
        'assessment_locked': False,
        'payment_required_url': None,
        'is_started': False,
        'is_expired': False,
        'remaining_time': 0,
        'answered_questions': {},
        'course_progress': 0,
        'previous_url': None,
        'next_url': None,
        'ask_oras': [],
        'user_submissions': Submission.objects.none(),
        'askora_submit_status': {},
        'askora_can_submit': {},
        'peer_review_stats': None,
        'submissions': [],
        'can_submit': False,
        'can_review': False,
        'is_quiz': False,
        'is_lti': False,
        'show_timer': False,
        'lti_tool': None,
    }

    assessment_id = request.GET.get('assessment_id')
    current_index = 0
    if assessment_id:
        assessment = get_object_or_404(Assessment, id=assessment_id)
        context['assessment'] = assessment
        context['current_content'] = ('assessment', assessment, next((s for s in sections if assessment in s.assessments.all()), None))
        current_index = next((i for i, c in enumerate(combined_content) if c[0] == 'assessment' and c[1].id == assessment.id), 0)

        # Tambahkan dukungan LTI Tool
        lti_tool = assessment.lti_tools.first() if assessment.lti_tools.exists() else None
        context['lti_tool'] = lti_tool
        context['is_lti'] = bool(lti_tool)

        if course.payment_model == 'pay_for_exam':
            payment = Payment.objects.filter(
                user=request.user, course=course, status='completed', payment_model='pay_for_exam'
            ).first()
            if not payment:
                context['assessment_locked'] = True
                context['payment_required_url'] = reverse('payments:process_payment', kwargs={
                    'course_id': course.id,
                    'payment_type': 'exam'
                })
                logger.info(f"Pembayaran diperlukan untuk penilaian {assessment_id} di kursus {course.id} untuk pengguna {request.user.username}")
            else:
                AssessmentRead.objects.get_or_create(user=request.user, assessment=assessment)
        else:
            AssessmentRead.objects.get_or_create(user=request.user, assessment=assessment)

        session = AssessmentSession.objects.filter(user=request.user, assessment=assessment).first()
        if session:
            context['is_started'] = True
            if session.end_time:
                context['remaining_time'] = max(0, int((session.end_time - timezone.now()).total_seconds()))
                context['is_expired'] = context['remaining_time'] <= 0
                context['show_timer'] = context['remaining_time'] > 0
            context['answered_questions'] = {
                answer.question.id: answer for answer in QuestionAnswer.objects.filter(
                    user=request.user, question__assessment=assessment
                ).select_related('question', 'choice')
            }
        else:
            if assessment.duration_in_minutes == 0:
                context['is_started'] = True

        context.update(_build_assessment_context(assessment, request.user))
    else:
        context['current_content'] = combined_content[0] if combined_content else None
        if context['current_content']:
            current_index = 0
            if context['current_content'][0] == 'material':
                context['material'] = context['current_content'][1]
                context['comments'] = Comment.objects.filter(
                    material=context['material'], parent=None
                ).order_by('-created_at')
                MaterialRead.objects.get_or_create(user=request.user, material=context['material'])
            elif context['current_content'][0] == 'assessment':
                context['assessment'] = context['current_content'][1]
                assessment = context['assessment']
                lti_tool = assessment.lti_tools.first() if assessment.lti_tools.exists() else None
                context['lti_tool'] = lti_tool
                context['is_lti'] = bool(lti_tool)
                context.update(_build_assessment_context(assessment, request.user))

    context['previous_url'], context['next_url'] = _get_navigation_urls(username, id, slug, combined_content, current_index)
    user_progress, _ = CourseProgress.objects.get_or_create(user=request.user, course=course)
    if context['current_content'] and (current_index + 1) > user_progress.progress_percentage / 100 * total_content:
        user_progress.progress_percentage = (current_index + 1) / total_content * 100
        user_progress.save()
    context['course_progress'] = user_progress.progress_percentage
    context['can_review'] = bool(context['submissions'])

    logger.info(f"my_course: Rendering untuk pengguna {username}, kursus {slug}, assessment_id={assessment_id}")
    response = render(request, 'learner/my_course.html', context)
    response['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    return response



@login_required
def load_content(request, username, id, slug, content_type, content_id):
    if request.user.username != username:
        logger.warning(f"Upaya akses tidak sah oleh {request.user.username} untuk {username}")
        return HttpResponse(status=403)

    course = get_object_or_404(Course, id=id, slug=slug)
    if not Enrollment.objects.filter(user=request.user, course=course).exists():
        logger.warning(f"Pengguna {request.user.username} tidak terdaftar di kursus {slug}")
        return HttpResponse(status=403)

    sections = Section.objects.filter(courses=course).prefetch_related(
        Prefetch('materials', queryset=Material.objects.all()),
        Prefetch('assessments', queryset=Assessment.objects.all())
    ).order_by('order')

    context = {
        'course': course,
        'course_name': course.course_name,
        'username': username,
        'slug': slug,
        'sections': sections,
        'current_content': None,
        'material': None,
        'assessment': None,
        'comments': None,
        'assessment_locked': False,
        'payment_required_url': None,
        'is_started': False,
        'is_expired': False,
        'remaining_time': 0,
        'answered_questions': {},
        'course_progress': CourseProgress.objects.get_or_create(user=request.user, course=course)[0].progress_percentage,
        'previous_url': None,
        'next_url': None,
        'ask_oras': [],
        'user_submissions': Submission.objects.none(),
        'askora_submit_status': {},
        'askora_can_submit': {},
        'peer_review_stats': None,
        'submissions': [],
        'can_submit': False,
        'can_review': False,
        'is_quiz': False,
        'is_lti': False,
        'show_timer': False,
        'lti_tool': None,
    }

    combined_content = _build_combined_content(sections)
    current_index = 0

    if content_type == 'material':
        material = get_object_or_404(Material, id=content_id)
        context['material'] = material
        context['current_content'] = ('material', material, next((s for s in sections if material in s.materials.all()), None))
        context['comments'] = Comment.objects.filter(material=material, parent=None).select_related('user', 'parent').prefetch_related('children').order_by('-created_at')
        MaterialRead.objects.get_or_create(user=request.user, material=material)
        current_index = next((i for i, c in enumerate(combined_content) if c[0] == 'material' and c[1].id == material.id), 0)

    elif content_type == 'assessment':
        assessment = get_object_or_404(Assessment.objects.select_related('section__courses'), id=content_id)
        context['assessment'] = assessment
        context['current_content'] = ('assessment', assessment, next((s for s in sections if assessment in s.assessments.all()), None))
        current_index = next((i for i, c in enumerate(combined_content) if c[0] == 'assessment' and c[1].id == assessment.id), 0)

        # Tambahkan dukungan LTI Tool
        lti_tool = assessment.lti_tools.first() if assessment.lti_tools.exists() else None
        context['lti_tool'] = lti_tool
        context['is_lti'] = bool(lti_tool)

        if course.payment_model == 'pay_for_exam':
            payment = Payment.objects.filter(
                user=request.user, course=course, status='completed', payment_model='pay_for_exam'
            ).first()
            if not payment:
                context['assessment_locked'] = True
                context['payment_required_url'] = reverse('payments:process_payment', kwargs={
                    'course_id': course.id,
                    'payment_type': 'exam'
                })
                logger.info(f"Pembayaran diperlukan untuk penilaian {content_id} di kursus {course.id} untuk pengguna {request.user.username}")
            else:
                AssessmentRead.objects.get_or_create(user=request.user, assessment=assessment)
        else:
            AssessmentRead.objects.get_or_create(user=request.user, assessment=assessment)

        session = AssessmentSession.objects.filter(user=request.user, assessment=assessment).first()
        if session:
            context['is_started'] = True
            if session.end_time:
                context['remaining_time'] = max(0, int((session.end_time - timezone.now()).total_seconds()))
                context['is_expired'] = context['remaining_time'] <= 0
                context['show_timer'] = context['remaining_time'] > 0
            context['answered_questions'] = {
                answer.question.id: answer for answer in QuestionAnswer.objects.filter(
                    user=request.user, question__assessment=assessment
                ).select_related('question', 'choice')
            }
        context.update(_build_assessment_context(assessment, request.user))

    context['previous_url'], context['next_url'] = _get_navigation_urls(username, id, slug, combined_content, current_index)
    template = 'learner/partials/content.html' if request.headers.get('HX-Request') == 'true' else 'learner/my_course.html'

    logger.info(f"load_content: Rendering {template} untuk pengguna {username}, {content_type} {content_id}")
    response = render(request, template, context)
    response['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    return response



@login_required
def start_assessment_courses(request, assessment_id):
    """
    Start an assessment session for the user.
    
    Args:
        request: HTTP request object.
        assessment_id: ID of the assessment.
    
    Returns:
        HttpResponse: Rendered assessment partial or redirect.
    """
    if request.method != 'POST':
        logger.error(f"Invalid request method: {request.method} for start_assessment")
        return render(request, 'learner/partials/error.html', {
            'error_message': 'Permintaan tidak valid.'
        }, status=400) if request.headers.get('HX-Request') == 'true' else HttpResponse(status=400)

    assessment = get_object_or_404(Assessment.objects.select_related('section__courses'), id=assessment_id)  # Changed 'section__course' to 'section__courses'
    course = assessment.section.courses
    if not Enrollment.objects.filter(user=request.user, course=course).exists():
        logger.warning(f"User {request.user.username} not enrolled in course {course.slug}")
        return render(request, 'learner/partials/error.html', {
            'error_message': 'Anda tidak terdaftar di kursus ini.'
        }, status=403) if request.headers.get('HX-Request') == 'true' else HttpResponse(status=403)

    session, created = AssessmentSession.objects.get_or_create(
        user=request.user, assessment=assessment,
        defaults={
            'start_time': timezone.now(),
            'end_time': timezone.now() + timedelta(minutes=assessment.duration_in_minutes) if assessment.duration_in_minutes > 0 else None
        }
    )
    if not created and session.end_time and session.end_time > timezone.now():
        logger.debug(f"Using existing session for user {request.user.username}, assessment {assessment_id}")
    else:
        session.start_time = timezone.now()
        session.end_time = timezone.now() + timedelta(minutes=assessment.duration_in_minutes) if assessment.duration_in_minutes > 0 else None
        session.save()
        logger.debug(f"{'New' if created else 'Reset'} session for user {request.user.username}, assessment {assessment_id}")

    context = {
        'course': course,
        'course_name': course.course_name,
        'username': request.user.username,
        'slug': course.slug,
        'sections': Section.objects.filter(courses=course).prefetch_related('materials', 'assessments').order_by('order'),
        'current_content': ('assessment', assessment, assessment.section),
        'material': None,
        'assessment': assessment,
        'comments': None,
        'assessment_locked': False,
        'payment_required_url': None,
        'is_started': True,
        'is_expired': False,
        'remaining_time': max(0, int((session.end_time - timezone.now()).total_seconds())) if session.end_time else 0,
        'answered_questions': {
            answer.question.id: answer for answer in QuestionAnswer.objects.filter(
                user=request.user, question__assessment=assessment
            ).select_related('question', 'choice')
        },
        'course_progress': CourseProgress.objects.get_or_create(user=request.user, course=course)[0].progress_percentage,
        'previous_url': None,
        'next_url': None,
    }

    context.update(_build_assessment_context(assessment, request.user))
    context['show_timer'] = context['remaining_time'] > 0
    context['is_expired'] = context['remaining_time'] <= 0
    context['can_review'] = bool(context['submissions'])

    combined_content = _build_combined_content(context['sections'])
    current_index = next((i for i, c in enumerate(combined_content) if c[0] == 'assessment' and c[1].id == assessment_id), 0)
    context['previous_url'], context['next_url'] = _get_navigation_urls(request.user.username, course.id,course.slug, combined_content, current_index)

    if course.payment_model == 'pay_for_exam':
        has_paid = Payment.objects.filter(
            user=request.user, course=course, status='completed', payment_model='pay_for_exam'
        ).exists()
        if not has_paid:
            context['assessment_locked'] = True
            context['payment_required_url'] = reverse('payments:process_payment', kwargs={
                'course_id': course.id, 'payment_type': 'exam'
            })
        else:
            AssessmentRead.objects.get_or_create(user=request.user, assessment=assessment)
    else:
        AssessmentRead.objects.get_or_create(user=request.user, assessment=assessment)

    is_htmx = request.headers.get('HX-Request') == 'true'
    if not is_htmx:
        redirect_url = reverse('learner:load_content', kwargs={
            'username': request.user.username, 'slug': course.slug,
            'content_type': 'assessment', 'content_id': assessment.id
        })
        logger.info(f"Redirecting non-HTMX request to: {redirect_url}")
        return HttpResponseRedirect(redirect_url)

    logger.info(f"start_assessment: Rendering HTMX for user {request.user.username}, assessment {assessment_id}, time_left={context['remaining_time']}")
    response = render(request, 'learner/partials/content.html', context)
    response['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    return response
@login_required
def submit_assessment_new(request, assessment_id):
    """
    Submit an assessment and end the session.
    """
    if request.method != 'POST':
        logger.warning(f"Invalid request method: {request.method} for submit_assessment_new")
        return render(request, 'learner/partials/error.html', {
            'error_message': 'Permintaan tidak valid.'
        }, status=400) if request.headers.get('HX-Request') == 'true' else HttpResponse(status=400)

    assessment = get_object_or_404(Assessment.objects.select_related('section__courses'), id=assessment_id)
    course = assessment.section.courses
    session = AssessmentSession.objects.filter(user=request.user, assessment=assessment).first()

    if not session:
        logger.error(f"No session found for user {request.user.username}, assessment {assessment_id}")
        return render(request, 'learner/partials/error.html', {
            'error_message': 'Sesi penilaian tidak ditemukan.'
        }, status=400) if request.headers.get('HX-Request') == 'true' else HttpResponse(status=400)

    # ⬇️ SIMPAN JAWABAN PILIHAN GANDA
    answers = {
        key.split('_')[1]: value
        for key, value in request.POST.items()
        if key.startswith('answers_')
    }

    for question_id, choice_id in answers.items():
        try:
            question = Question.objects.get(id=question_id, assessment=assessment)
            choice = Choice.objects.get(id=choice_id, question=question)

            QuestionAnswer.objects.update_or_create(
                user=request.user,
                question=question,
                defaults={'choice': choice}
            )
        except (Question.DoesNotExist, Choice.DoesNotExist) as e:
            logger.warning(f"Invalid answer data for question {question_id}: {e}")
            continue

    # ⬇️ SIMPAN AKHIR SESI
    session.end_time = timezone.now()
    session.save()

    logger.debug(f"Assessment submitted for user {request.user.username}, assessment {assessment_id}")
    
    # ⬇️ BANGUN KONTEN
    context = {
        'course': course,
        'course_name': course.course_name,
        'username': request.user.username,
        'slug': course.slug,
        'sections': Section.objects.filter(courses=course).prefetch_related('materials', 'assessments').order_by('order'),
        'current_content': ('assessment', assessment, assessment.section),
        'material': None,
        'assessment': assessment,
        'comments': None,
        'assessment_locked': False,
        'payment_required_url': None,
        'is_started': True,
        'is_expired': True,
        'remaining_time': 0,
        'answered_questions': {
            answer.question.id: answer for answer in QuestionAnswer.objects.filter(
                user=request.user, question__assessment=assessment
            ).select_related('question', 'choice')
        },
        'course_progress': CourseProgress.objects.get_or_create(user=request.user, course=course)[0].progress_percentage,
        'previous_url': None,
        'next_url': None,
    }

    # Tambahan jika Anda punya helper
    context.update(_build_assessment_context(assessment, request.user))
    context['can_review'] = bool(context['submissions'])

    combined_content = _build_combined_content(context['sections'])
    current_index = next((i for i, c in enumerate(combined_content) if c[0] == 'assessment' and c[1].id == assessment_id), 0)
    context['previous_url'], context['next_url'] = _get_navigation_urls(request.user.username, course.id, course.slug, combined_content, current_index)

    is_htmx = request.headers.get('HX-Request') == 'true'
    if not is_htmx:
        redirect_url = reverse('learner:load_content', kwargs={
            'username': request.user.username,
            'slug': course.slug,
            'content_type': 'assessment',
            'content_id': assessment.id
        })
        logger.info(f"Redirecting non-HTMX request to: {redirect_url}")
        return HttpResponseRedirect(redirect_url)

    logger.info(f"submit_assessment_new: Rendering HTMX for user {request.user.username}, assessment {assessment_id}")
    response = render(request, 'learner/partials/content.html', context)
    response['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    return response


@login_required
def submit_answer(request):
    """
    Submit an answer for a quiz question.
    
    Args:
        request: HTTP request object.
    
    Returns:
        HttpResponse: Rendered assessment partial.
    """
    if request.method != 'POST':
        logger.warning(f"Invalid request method: {request.method} for submit_answer")
        return render(request, 'learner/partials/error.html', {
            'error_message': 'Permintaan tidak valid.'
        }, status=400) if request.headers.get('HX-Request') == 'true' else HttpResponse(status=400)

    question_id = request.POST.get('question_id')
    choice_id = request.POST.get('choice_id')
    if not question_id or not choice_id:
        logger.warning(f"Missing question_id or choice_id for user {request.user.username}")
        return render(request, 'learner/partials/error.html', {
            'error_message': 'Pilihan tidak valid.'
        }, status=400) if request.headers.get('HX-Request') == 'true' else HttpResponse(status=400)

    question = get_object_or_404(Question, id=question_id)
    choice = get_object_or_404(Choice, id=choice_id, question=question)
    assessment = question.assessment
    course = assessment.section.courses  # Changed 'course' to 'courses'

    if not Enrollment.objects.filter(user=request.user, course=course).exists():
        logger.warning(f"User {request.user.username} not enrolled in course {course.slug}")
        return render(request, 'learner/partials/error.html', {
            'error_message': 'Anda tidak terdaftar di kursus ini.'
        }, status=403) if request.headers.get('HX-Request') == 'true' else HttpResponse(status=403)

    session = AssessmentSession.objects.filter(user=request.user, assessment=assessment).first()
    if not session or (session.end_time and session.end_time < timezone.now()):
        logger.warning(f"No session or session expired for user {request.user.username}, assessment {assessment.id}")
        return render(request, 'learner/partials/error.html', {
            'error_message': 'Sesi penilaian tidak valid atau telah kedaluwarsa.'
        }, status=403) if request.headers.get('HX-Request') == 'true' else HttpResponse(status=403)

    QuestionAnswer.objects.update_or_create(
        user=request.user, question=question,
        defaults={'choice': choice}
    )
    logger.debug(f"Answer submitted for user {request.user.username}, question {question_id}, choice {choice_id}")

    context = {
        'course': course,
        'course_name': course.course_name,
        'username': request.user.username,
        'slug': course.slug,
        'sections': Section.objects.filter(courses=course).prefetch_related('materials', 'assessments').order_by('order'),
        'current_content': ('assessment', assessment, assessment.section),
        'material': None,
        'assessment': assessment,
        'comments': None,
        'assessment_locked': False,
        'payment_required_url': None,
        'is_started': True,
        'is_expired': session.end_time and session.end_time < timezone.now(),
        'remaining_time': max(0, int((session.end_time - timezone.now()).total_seconds())) if session.end_time else 0,
        'answered_questions': {
            answer.question.id: answer for answer in QuestionAnswer.objects.filter(
                user=request.user, question__assessment=assessment
            ).select_related('question', 'choice')
        },
        'course_progress': CourseProgress.objects.get_or_create(user=request.user, course=course)[0].progress_percentage,
        'previous_url': None,
        'next_url': None,
    }

    context.update(_build_assessment_context(assessment, request.user))
    context['show_timer'] = context['remaining_time'] > 0
    context['can_review'] = bool(context['submissions'])

    combined_content = _build_combined_content(context['sections'])
    current_index = next((i for i, c in enumerate(combined_content) if c[0] == 'assessment' and c[1].id == assessment.id), 0)
    context['previous_url'], context['next_url'] = _get_navigation_urls(request.user.username,course.id, course.slug, combined_content, current_index)

    is_htmx = request.headers.get('HX-Request') == 'true'
    logger.info(f"submit_answer: Rendering HTMX for user {request.user.username}, assessment {assessment.id}, question {question_id}")
    response = render(request, 'learner/partials/content.html', context)
    response['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    return response

def is_bot(request):
    """
    Check if the request originates from a bot based on User-Agent.
    
    Args:
        request: HTTP request object.
    
    Returns:
        bool: True if bot detected, False otherwise.
    """
    user_agent = request.META.get('HTTP_USER_AGENT', '').lower()
    return 'bot' in user_agent or 'crawler' in user_agent

def is_suspicious(request):
    """
    Check if the request is suspicious based on User-Agent or missing Referer.
    
    Args:
        request: HTTP request object.
    
    Returns:
        bool: True if suspicious, False otherwise.
    """
    user_agent = request.META.get('HTTP_USER_AGENT', '')
    referer = request.META.get('HTTP_REFERER', '')
    return 'bot' in user_agent.lower() or not referer

def is_spam(request, user, content):
    """
    Check if a comment is spam based on rate-limiting, bot detection, and blacklisted keywords.
    
    Args:
        request: HTTP request object.
        user: CustomUser object.
        content: Comment content.
    
    Returns:
        bool: True if spam detected, False otherwise.
    """
    if is_bot(request):
        logger.warning(f"Bot detected in comment attempt by {user.username}")
        return True

    time_limit = timedelta(seconds=30)
    last_comment = Comment.objects.filter(user=user).order_by('-created_at').first()
    if last_comment and timezone.now() - last_comment.created_at < time_limit:
        logger.warning(f"Rate limit exceeded for user {user.username}")
        return True

    comment_instance = Comment(user=user, content=content)
    if comment_instance.contains_blacklisted_keywords():
        logger.warning(f"Blacklisted keywords detected in comment by {user.username}: {content}")
        return True

    return False

@login_required
def add_comment(request):
    """
    Add a comment to a material, with spam and security checks.
    
    Args:
        request: HTTP request object.
    
    Returns:
        HttpResponse: Rendered comments partial or redirect.
    """
    if request.method != 'POST':
        logger.warning(f"Invalid request method: {request.method} for add_comment")
        messages.warning(request, "Permintaan tidak valid.")
        return HttpResponse(status=400)

    comment_text = request.POST.get('comment_text')
    material_id = request.POST.get('material_id')
    parent_id = request.POST.get('parent_id')

    if not comment_text or not material_id:
        logger.warning(f"Missing fields: comment_text={bool(comment_text)}, material_id={material_id}")
        messages.warning(request, "Komentar dan ID materi diperlukan.")
        return HttpResponse(status=400)

    material = get_object_or_404(Material, id=material_id)
    course = material.section.courses  # Fixed: 'course' to 'courses'
    parent_comment = get_object_or_404(Comment, id=parent_id, material=material) if parent_id else None

    if is_suspicious(request):
        logger.warning(f"Suspicious activity detected by {request.user.username}")
        messages.warning(request, "Aktivitas mencurigakan terdeteksi.")
        return HttpResponseRedirect(reverse('learner:load_content', kwargs={
            'username': request.user.username,
            'slug': course.slug,
            'content_type': 'material',
            'content_id': material_id
        }))

    if is_spam(request, request.user, comment_text):
        logger.warning(f"Spam comment detected by {request.user.username}: {comment_text}")
        messages.warning(request, "Komentar Anda terdeteksi sebagai spam!")
        return HttpResponseRedirect(reverse('learner:load_content', kwargs={
            'username': request.user.username,
            'slug': course.slug,
            'content_type': 'material',
            'content_id': material_id
        }))

    comment = Comment(user=request.user, material=material, content=comment_text, parent=parent_comment)
    if comment.contains_blacklisted_keywords():
        logger.warning(f"Comment by {request.user.username} contains blacklisted keywords: {comment_text}")
        messages.warning(request, "Komentar mengandung kata-kata yang tidak diizinkan.")
        return HttpResponseRedirect(reverse('learner:load_content', kwargs={
            'username': request.user.username,
            'slug': course.slug,
            'content_type': 'material',
            'content_id': material_id
        }))

    comment.save()
    logger.debug(f"Comment added by {request.user.username} for material {material_id}, parent_id={parent_id}")

    is_htmx = request.headers.get('HX-Request') == 'true'
    if is_htmx:
        context = {
            'comments': Comment.objects.filter(material=material, parent=None).select_related('user', 'parent').prefetch_related('children'),  # Modified to ensure replies are fetched
            'material': material,
            'user_reactions': {
                r.comment_id: r.reaction_type for r in CommentReaction.objects.filter(
                    user=request.user, comment__material=material
                )
            },
        }
        messages.success(request, "Komentar berhasil diposting!")
        return render(request, 'learner/partials/comments.html', context)

    messages.success(request, "Komentar berhasil diposting!")
    return HttpResponseRedirect(reverse('learner:load_content', kwargs={
        'username': request.user.username,
        'slug': course.slug,
        'content_type': 'material',
        'content_id': material_id
    }))



@login_required
def get_progress(request, username, slug):
    """
    Get the progress bar for a course.
    
    Args:
        request: HTTP request object.
        username: Username of the user.
        slug: Course slug.
    
    Returns:
        HttpResponse: Rendered progress partial.
    """
    if request.user.username != username:
        logger.warning(f"Unauthorized access attempt by {request.user.username} for {username}")
        return HttpResponse(status=403)

    course = get_object_or_404(Course, slug=slug)
    user_progress, _ = CourseProgress.objects.get_or_create(user=request.user, course=course)
    return render(request, 'learner/partials/progress.html', {'course_progress': user_progress.progress_percentage})


@login_required
def submit_answer_askora_new(request, ask_ora_id):
    """
    Submit an answer for an AskOra question, rendering content partial.
    
    Args:
        request: HTTP request object.
        ask_ora_id: ID of the AskOra question.
    
    Returns:
        HttpResponse: Rendered assessment partial.
    """
    if request.method != 'POST':
        logger.warning(f"Invalid request method: {request.method} for submit_answer_askora_new")
        return render(request, 'learner/partials/error.html', {
            'error_message': 'Metode request tidak valid.'
        }, status=400) if request.headers.get('HX-Request') == 'true' else HttpResponse(status=400)

    ask_ora = get_object_or_404(AskOra, id=ask_ora_id)
    assessment = ask_ora.assessment
    course = assessment.section.courses  # Assuming this is correct from previous fix

    if not ask_ora.is_responsive():
        logger.warning(f"Submission deadline expired for ask_ora {ask_ora_id}")
        messages.warning(request, "Batas waktu pengiriman telah berakhir.")
        return render(request, 'learner/partials/error.html', {
            'error_message': 'Batas waktu pengiriman telah berakhir.'
        }, status=400) if request.headers.get('HX-Request') == 'true' else HttpResponse(status=400)

    if Submission.objects.filter(askora=ask_ora, user=request.user).exists():
        logger.warning(f"Duplicate submission attempt for ask_ora {ask_ora_id} by {request.user.username}")
        messages.warning(request, "Anda sudah mengirimkan jawaban untuk pertanyaan ini.")
        return render(request, 'learner/partials/error.html', {
            'error_message': 'Anda sudah mengirimkan jawaban untuk pertanyaan ini.'
        }, status=400) if request.headers.get('HX-Request') == 'true' else HttpResponse(status=400)

    answer_text = request.POST.get('answer_text')
    answer_file = request.FILES.get('answer_file')
    if not answer_text:
        logger.warning(f"Missing answer_text for ask_ora {ask_ora_id} by {request.user.username}")
        messages.warning(request, "Jawaban teks diperlukan.")
        return render(request, 'learner/partials/error.html', {
            'error_message': 'Jawaban teks diperlukan.'
        }, status=400) if request.headers.get('HX-Request') == 'true' else HttpResponse(status=400)

    # Buat submission
    submission = Submission.objects.create(
        askora=ask_ora,
        user=request.user,
        answer_text=answer_text,
        answer_file=answer_file
    )
    logger.debug(f"Submission created for ask_ora {ask_ora_id} by {request.user.username}")

    # Bangun konteks untuk template
    context = {
        'course': course,
        'course_name': course.course_name,  # Sesuaikan dengan atribut model Course
        'username': request.user.username,
        'slug': course.slug,
        'sections': Section.objects.filter(courses=course).prefetch_related('materials', 'assessments').order_by('order'),
        'current_content': ('assessment', assessment, assessment.section),
        'material': None,
        'assessment': assessment,
        'comments': None,
        'assessment_locked': False,  # Sesuaikan dengan logika Anda
        'payment_required_url': None,
        'is_started': True,  # Sesuaikan dengan logika sesi
        'is_expired': False,  # Sesuaikan dengan logika sesi
        'remaining_time': 0,  # Sesuaikan jika ada timer
        'ask_oras': assessment.ask_oras.all(),  # Fixed: Use ask_oras instead of askora_set
        'user_submissions': Submission.objects.filter(askora__assessment=assessment, user=request.user),
        'can_review': Submission.objects.filter(askora__assessment=assessment).exclude(user=request.user).exists(),
        'submissions': Submission.objects.filter(askora__assessment=assessment).exclude(user=request.user),
        'is_quiz': False,
        'askora_can_submit': {
            ao.id: ao.is_responsive() and not Submission.objects.filter(askora=ao, user=request.user).exists()
            for ao in assessment.ask_oras.all()  # Fixed: Consistent use of ask_oras
        },
        'course_progress': CourseProgress.objects.get_or_create(user=request.user, course=course)[0].progress_percentage,
        'previous_url': None,
        'next_url': None,
    }

    # Tambahkan konteks tambahan untuk peer review stats
    context.update({
        'peer_review_stats': {
            'distinct_reviewers': 0,  # Ganti dengan logika sebenarnya
            'total_participants': 0,  # Ganti dengan logika sebenarnya
            'completed': False,  # Ganti dengan logika sebenarnya
            'avg_score': None,  # Ganti dengan logika sebenarnya
        },
        'course_scores': [],  # Sesuaikan jika ada skor kuis
    })

    # Hitung URL navigasi
    combined_content = []
    for section in context['sections']:
        for material in section.materials.all():
            combined_content.append(('material', material))
        for assessment in section.assessments.all():
            combined_content.append(('assessment', assessment))
    current_index = next((i for i, c in enumerate(combined_content) if c[0] == 'assessment' and c[1].id == assessment.id), 0)
    if current_index > 0:
        prev = combined_content[current_index - 1]
        context['previous_url'] = reverse('learner:load_content', kwargs={
            'username': request.user.username,
            'id':course.id,
            'slug': course.slug,
            'content_type': prev[0],
            'content_id': prev[1].id
        })
    if current_index < len(combined_content) - 1:
        next_item = combined_content[current_index + 1]
        context['next_url'] = reverse('learner:load_content', kwargs={
            'username': request.user.username,
            'id': course.id,
            'slug': course.slug,
            'content_type': next_item[0],
            'content_id': next_item[1].id
        })

    # Tambahkan pesan sukses
    messages.success(request, "Jawaban berhasil dikirim!")
    
    # Render template parsial
    is_htmx = request.headers.get('HX-Request') == 'true'
    logger.info(f"submit_answer_askora_new: Rendering HTMX for user {request.user.username}, assessment {assessment.id}, ask_ora {ask_ora_id}")
    response = render(request, 'learner/partials/content.html', context)
    response['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    return response



@login_required
def submit_peer_review_new(request, submission_id):
    """
    Menyimpan peer review untuk submisi tertentu dan merender ulang halaman assessment.
    
    Args:
        request: Objek HTTP request.
        submission_id: ID submisi yang akan direview.
    
    Returns:
        HttpResponse: Render ulang template content.html atau pesan error.
    """
    submission = get_object_or_404(Submission, id=submission_id)
    assessment = submission.askora.assessment
    course = assessment.section.courses  # Menggunakan courses, bukan course

    if request.method != 'POST':
        logger.warning(f"Metode tidak valid untuk submit_peer_review_new oleh {request.user.username}")
        return HttpResponse('<div class="alert alert-danger">Metode request tidak valid.</div>', status=400)

    logger.debug(f"POST data untuk review submission {submission_id}: {request.POST}")

    if PeerReview.objects.filter(reviewer=request.user).count() >= 5:
        logger.warning(f"Pengguna {request.user.username} telah mencapai batas maksimum 5 review")
        messages.warning(request, "Anda telah memberikan jumlah review maksimal yang diperbolehkan.")
        return render_content(request, assessment, course)

    if PeerReview.objects.filter(submission=submission, reviewer=request.user).exists():
        logger.warning(f"Pengguna {request.user.username} mencoba mereview ulang submission {submission_id}")
        messages.warning(request, "Anda sudah mereview submisi ini.")
        return render_content(request, assessment, course)

    try:
        score_raw = request.POST.get('score')
        logger.debug(f"Nilai review untuk submission {submission_id}: {score_raw}")
        score = int(score_raw)

        if not 1 <= score <= 5:
            raise ValueError("Nilai harus antara 1 hingga 5")

        comment = request.POST.get('comment', '').strip()

        # Buat objek PeerReview
        peer_review = PeerReview.objects.create(
            submission=submission,
            reviewer=request.user,
            score=score,
            comment=comment or None
        )
        logger.info(f"Peer review berhasil dibuat untuk submission {submission_id} oleh {request.user.username}")

        # Hitung skor final
        assessment_score, _ = AssessmentScore.objects.get_or_create(submission=submission)
        assessment_score.calculate_final_score()
        logger.debug(f"Skor final dihitung untuk submission {submission_id}")

        # Tambahkan pesan sukses
        messages.success(request, "Review berhasil dikirim!")

        # Render ulang halaman assessment
        return render_content(request, assessment, course)

    except Exception as e:
        logger.exception(f"Gagal menyimpan review untuk submission {submission_id} oleh {request.user.username}: {str(e)}")
        messages.error(request, f"Error: {str(e)}")
        return render_content(request, assessment, course)

def render_content(request, assessment, course):
    """
    Helper function untuk merender ulang template content.html dengan konteks lengkap.
    
    Args:
        request: Objek HTTP request.
        assessment: Objek Assessment.
        course: Objek Course.
    
    Returns:
        HttpResponse: Render template content.html.
    """
    sections = Section.objects.filter(courses=course).prefetch_related(
        Prefetch('materials', queryset=Material.objects.all()),
        Prefetch('assessments', queryset=Assessment.objects.all())
    ).order_by('order')

    # Bangun combined_content untuk navigasi
    combined_content = []
    for section in sections:
        for material in section.materials.all():
            combined_content.append(('material', material))
        for assessment_item in section.assessments.all():
            combined_content.append(('assessment', assessment_item))
    current_index = next((i for i, c in enumerate(combined_content) if c[0] == 'assessment' and c[1].id == assessment.id), 0)

    # Filter submisi yang belum direview
    submissions = Submission.objects.filter(
        askora__assessment=assessment
    ).exclude(user=request.user).exclude(
        id__in=PeerReview.objects.filter(reviewer=request.user).values('submission__id')
    )
    
    # Periksa apakah ada submisi dari pengguna lain
    has_other_submissions = Submission.objects.filter(
        askora__assessment=assessment
    ).exclude(user=request.user).exists()

    # Bangun konteks
    context = {
        'course': course,
        'course_name': course.course_name,
        'username': request.user.username,
        'id': course.id,
        'slug': course.slug,
        'sections': sections,
        'current_content': ('assessment', assessment, assessment.section),
        'material': None,
        'assessment': assessment,
        'comments': None,
        'assessment_locked': False,
        'payment_required_url': None,
        'is_started': False,
        'is_expired': False,
        'remaining_time': 0,
        'answered_questions': {},
        'course_progress': CourseProgress.objects.get_or_create(user=request.user, course=course)[0].progress_percentage,
        'previous_url': None,
        'next_url': None,
        'ask_oras': assessment.ask_oras.all(),
        'user_submissions': Submission.objects.filter(askora__assessment=assessment, user=request.user),
        'askora_submit_status': {
            ao.id: Submission.objects.filter(askora=ao, user=request.user).exists()
            for ao in assessment.ask_oras.all()
        },
        'askora_can_submit': {
            ao.id: (
                not Submission.objects.filter(askora=ao, user=request.user).exists() and
                ao.is_responsive and
                (ao.response_deadline is None or ao.response_deadline > timezone.now())
            ) for ao in assessment.ask_oras.all()
        },
        'can_review': submissions.exists(),
        'submissions': submissions,
        'has_other_submissions': has_other_submissions,  # Tambahan: True jika ada submisi dari pengguna lain
        'is_quiz': assessment.questions.exists(),
        'peer_review_stats': None,
        'show_timer': False,
    }

    # Hitung peer_review_stats jika pengguna punya submisi
    user_submissions = context['user_submissions']
    if user_submissions.exists():
        total_participants = Submission.objects.filter(
            askora__assessment=assessment
        ).values('user').distinct().count()
        user_reviews = PeerReview.objects.filter(
            submission__in=user_submissions
        ).aggregate(
            total_reviews=Count('id'),
            distinct_reviewers=Count('reviewer', distinct=True)
        )
        context['peer_review_stats'] = {
            'total_reviews': user_reviews['total_reviews'] or 0,
            'distinct_reviewers': user_reviews['distinct_reviewers'] or 0,
            'total_participants': total_participants - 1,
            'completed': user_reviews['distinct_reviewers'] >= (total_participants - 1)
        }
        if user_reviews['total_reviews'] > 0:
            avg_score = PeerReview.objects.filter(
                submission__in=user_submissions
            ).aggregate(avg_score=Avg('score'))['avg_score']
            context['peer_review_stats']['avg_score'] = round(avg_score, 2) if avg_score else None

    # Hitung URL navigasi
    if current_index > 0:
        prev = combined_content[current_index - 1]
        context['previous_url'] = reverse('learner:load_content', kwargs={
            'username': request.user.username,
            'id': course.id,
            'slug': course.slug,
            'content_type': prev[0],
            'content_id': prev[1].id
        })
    if current_index < len(combined_content) - 1:
        next_item = combined_content[current_index + 1]
        context['next_url'] = reverse('learner:load_content', kwargs={
            'username': request.user.username,
            'id': course.id,
            'slug': course.slug,
            'content_type': next_item[0],
            'content_id': next_item[1].id
        })

    logger.info(f"submit_peer_review_new: Rendering learner/partials/content.html untuk user {request.user.username}, assessment {assessment.id}")
    response = render(request, 'learner/partials/content.html', context)
    response['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    return response

def learner_detail(request, username):
    """
    Menampilkan profil learner secara publik, termasuk kursus yang diselesaikan (lulus),
    informasi instructor jika ada, dan progres belajar.
    """
    learner = get_object_or_404(CustomUser, username=username)

    # Ambil semua enrollment dan prefetch relasi yang diperlukan
    enrollments = Enrollment.objects.filter(user=learner).select_related('course')

    # Jika learner juga instructor, ambil profil instructor-nya
    instructor = Instructor.objects.filter(user=learner).first()

    completed_courses_data = []

    for enrollment in enrollments:
        course = enrollment.course

        # Hitung progress materi
        materials = Material.objects.filter(section__courses=course).distinct()
        total_materials = materials.count()
        materials_read = MaterialRead.objects.filter(user=learner, material__in=materials).count()
        materials_read_percentage = (materials_read / total_materials * 100) if total_materials > 0 else 0

        # Hitung progress assessment
        assessments = Assessment.objects.filter(section__courses=course).distinct()
        total_assessments = assessments.count()
        assessments_completed = AssessmentRead.objects.filter(user=learner, assessment__in=assessments).count()
        assessments_completed_percentage = (assessments_completed / total_assessments * 100) if total_assessments > 0 else 0

        # Gabungkan progress keseluruhan
        progress = (materials_read_percentage + assessments_completed_percentage) / 2 if (total_materials + total_assessments) > 0 else 0

        # Simpan atau update ke model CourseProgress
        course_progress, _ = CourseProgress.objects.get_or_create(user=learner, course=course)
        course_progress.progress_percentage = progress
        course_progress.save()

        # Ambil ambang batas kelulusan
        grade_range = GradeRange.objects.filter(course=course, name='Pass').first()
        passing_threshold = grade_range.min_grade if grade_range else Decimal('52.00')

        # Hitung nilai akhir
        total_score = Decimal('0')
        total_max_score = Decimal('0')

        for assessment in assessments:
            score_value = Decimal('0')
            total_questions = assessment.questions.count()

            if total_questions > 0:
                correct_answers = QuestionAnswer.objects.filter(
                    user=learner, question__assessment=assessment, choice__is_correct=True
                ).count()
                score_value = (Decimal(correct_answers) / Decimal(total_questions)) * assessment.weight
            else:
                submission = Submission.objects.filter(askora__assessment=assessment, user=learner).order_by('-submitted_at').first()
                if submission:
                    assessment_score = AssessmentScore.objects.filter(submission=submission).first()
                    if assessment_score:
                        score_value = assessment_score.final_score

            total_score += min(score_value, assessment.weight)
            total_max_score += assessment.weight

        overall_percentage = (total_score / total_max_score * 100) if total_max_score > 0 else 0

        # Penentu apakah kursus dianggap selesai/lulus
        is_completed = progress == 100 and overall_percentage >= passing_threshold

        if is_completed:
            completed_courses_data.append({
                'enrollment': enrollment,
                'progress': progress,
                'overall_percentage': overall_percentage,
                'threshold': passing_threshold,
                'total_score': total_score,
            })

    context = {
        'learner': learner,
        'completed_courses': completed_courses_data,
        'instructor': instructor,
    }

    return render(request, 'learner/learner.html', context)