
import csv
import logging
from datetime import timedelta
from decimal import Decimal
from django.db.models import F
from django.db import transaction
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.mail import send_mail
from django.core.paginator import Paginator
from django.db.models import Avg, Prefetch
from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.urls import NoReverseMatch

from authentication.models import CustomUser, Universiti
from courses.models import (
    Assessment, AssessmentRead, AssessmentScore, AssessmentSession,
    AskOra, Choice, Comment, Course, CourseProgress, CourseStatusHistory,
    Enrollment, GradeRange, Instructor, LTIExternalTool, Material,
    MaterialRead, Payment, PeerReview, Question, QuestionAnswer, 
    Score, Section, Submission, UserActivityLog, CommentReaction
)



logger = logging.getLogger(__name__)

@login_required
def toggle_reaction(request, comment_id, reaction_type):
    if not request.user.is_authenticated or request.method != 'POST':
        logger.warning(f"Invalid request: Auth={request.user.is_authenticated}, Method={request.method}")
        return HttpResponse(status=400)

    if reaction_type not in ['like', 'dislike']:
        logger.warning(f"Invalid reaction_type: {reaction_type}")
        return HttpResponse(status=400)

    comment = get_object_or_404(Comment, id=comment_id)
    material = comment.material
    reaction_type = CommentReaction.REACTION_LIKE if reaction_type == 'like' else CommentReaction.REACTION_DISLIKE

    try:
        with transaction.atomic():
            existing_reaction = CommentReaction.objects.filter(user=request.user, comment=comment).first()

            if existing_reaction:
                if existing_reaction.reaction_type == reaction_type:
                    # Batalkan reaksi
                    existing_reaction.delete()
                    if reaction_type == CommentReaction.REACTION_LIKE:
                        Comment.objects.filter(id=comment_id).update(likes=F('likes') - 1)
                    else:
                        Comment.objects.filter(id=comment_id).update(dislikes=F('dislikes') - 1)
                    logger.debug(f"User {request.user.username} removed {reaction_type} from comment {comment_id}")
                else:
                    # Ganti reaksi (misalnya, like ke dislike)
                    existing_reaction.delete()
                    CommentReaction.objects.create(user=request.user, comment=comment, reaction_type=reaction_type)
                    if reaction_type == CommentReaction.REACTION_LIKE:
                        Comment.objects.filter(id=comment_id).update(likes=F('likes') + 1, dislikes=F('dislikes') - 1)
                    else:
                        Comment.objects.filter(id=comment_id).update(dislikes=F('dislikes') + 1, likes=F('likes') - 1)
                    logger.debug(f"User {request.user.username} changed reaction to {reaction_type} on comment {comment_id}")
            else:
                # Tambahkan reaksi baru
                CommentReaction.objects.create(user=request.user, comment=comment, reaction_type=reaction_type)
                if reaction_type == CommentReaction.REACTION_LIKE:
                    Comment.objects.filter(id=comment_id).update(likes=F('likes') + 1)
                else:
                    Comment.objects.filter(id=comment_id).update(dislikes=F('dislikes') + 1)
                logger.debug(f"User {request.user.username} added {reaction_type} to comment {comment_id}")

    except Exception as e:
        logger.error(f"Error toggling reaction for comment {comment_id}: {str(e)}")
        return HttpResponse(status=500)

    is_htmx = getattr(request, 'htmx', False) or request.headers.get('HX-Request') == 'true'
    if is_htmx:
        context = {
            'comments': Comment.objects.filter(material=material).select_related('user', 'parent'),
            'material': material,
            'user_reactions': {r.comment_id: r.reaction_type for r in CommentReaction.objects.filter(user=request.user, comment__material=material)},
        }
        return render(request, 'learner/partials/comments.html', context)

    course = material.section.courses
    redirect_url = reverse('learner:load_content', kwargs={
        'username': request.user.username,
        'slug': course.slug,
        'content_type': 'material',
        'content_id': material.id
    })
    return HttpResponseRedirect(redirect_url)

@login_required
def my_course(request, username, slug):
    if request.user.username != username:
        logger.warning(f"Unauthorized access attempt by {request.user.username} for {username}")
        return HttpResponse(status=403)

    course = get_object_or_404(Course, slug=slug)
    if not Enrollment.objects.filter(user=request.user, course=course).exists():
        logger.warning(f"User {request.user.username} not enrolled in course {slug}")
        return HttpResponse(status=403)

    sections = Section.objects.filter(courses=course).prefetch_related('materials', 'assessments').order_by('order')
    combined_content = []
    for section in sections:
        for m in section.materials.all():
            combined_content.append(('material', m, section))
        for a in section.assessments.all():
            combined_content.append(('assessment', a, section))

    total_content = len(combined_content)
    current_content = None
    material = None
    assessment = None
    comments = None
    assessment_locked = False
    payment_required_url = None
    is_started = False
    is_expired = False
    time_left = 0
    answered_questions = {}

    # Cek parameter assessment_id
    assessment_id = request.GET.get('assessment_id')
    if assessment_id:
        assessment = get_object_or_404(Assessment, id=assessment_id)
        current_content = ('assessment', assessment, next((s for s in sections if assessment in s.assessments.all()), None))
        if course.payment_model == 'pay_for_exam':
            payment = Payment.objects.filter(
                user=request.user, course=course, status='completed', payment_model='pay_for_exam'
            ).first()
            if not payment:
                assessment_locked = True
                payment_required_url = reverse('payments:process_payment', kwargs={'course_id': course.id, 'payment_type': 'exam'})
                logger.info(f"Payment required for assessment {assessment_id} in course {course.id} for user {request.user.username}")
            else:
                if not AssessmentRead.objects.filter(user=request.user, assessment=assessment).exists():
                    AssessmentRead.objects.create(user=request.user, assessment=assessment)
        else:
            if not AssessmentRead.objects.filter(user=request.user, assessment=assessment).exists():
                AssessmentRead.objects.create(user=request.user, assessment=assessment)
        session = AssessmentSession.objects.filter(user=request.user, assessment=assessment).first()
        if session:
            is_started = True
            if session.end_time:
                time_left = max(0, (session.end_time - timezone.now()).total_seconds())
                is_expired = time_left <= 0
            else:
                time_left = 0
            answered_questions = {
                answer.question.id: answer
                for answer in QuestionAnswer.objects.filter(user=request.user, question__assessment=assessment).select_related('question', 'choice')
            }
        else:
            if assessment.duration_in_minutes == 0:
                is_started = True
                time_left = 0
    else:
        current_content = combined_content[0] if combined_content else None
        if current_content:
            if current_content[0] == 'material':
                material = current_content[1]
                comments = Comment.objects.filter(material=material, parent=None).order_by('-created_at')
                if not MaterialRead.objects.filter(user=request.user, material=material).exists():
                    MaterialRead.objects.create(user=request.user, material=material)
            elif current_content[0] == 'assessment':
                assessment = current_content[1]

    current_index = -1
    if current_content:
        for i, content in enumerate(combined_content):
            if content[0] == current_content[0] and content[1].id == current_content[1].id:
                current_index = i
                break

    previous_url = reverse('learner:load_content', kwargs={
        'username': username, 'slug': slug,
        'content_type': combined_content[current_index - 1][0],
        'content_id': combined_content[current_index - 1][1].id
    }) if current_index > 0 else None
    next_url = reverse('learner:load_content', kwargs={
        'username': username, 'slug': slug,
        'content_type': combined_content[current_index + 1][0],
        'content_id': combined_content[current_index + 1][1].id
    }) if current_index < len(combined_content) - 1 else None

    user_progress, created = CourseProgress.objects.get_or_create(user=request.user, course=course)
    if current_content and (current_index + 1) > user_progress.progress_percentage / 100 * total_content:
        user_progress.progress_percentage = (current_index + 1) / total_content * 100
        user_progress.save()

    context = {
        'course': course,
        'course_name': course.course_name,
        'username': username,
        'slug': slug,
        'sections': sections,
        'current_content': current_content,
        'material': material,
        'assessment': assessment,
        'comments': comments,
        'assessment_locked': assessment_locked,
        'payment_required_url': payment_required_url,
        'is_started': is_started,
        'is_expired': is_expired,
        'remaining_time': int(time_left),
        'answered_questions': answered_questions,
        'course_progress': user_progress.progress_percentage,
        'previous_url': previous_url,
        'next_url': next_url,
    }

    logger.info(f"my_course: Rendering for user {username}, course {slug}, assessment_id={assessment_id}")
    return render(request, 'learner/my_course.html', context)
@login_required
def load_content(request, username, slug, content_type, content_id):
    if request.user.username != username:
        logger.warning(f"Unauthorized access attempt by {request.user.username} for {username}")
        return HttpResponse(status=403)

    course = get_object_or_404(Course, slug=slug)
    if not Enrollment.objects.filter(user=request.user, course=course).exists():
        logger.warning(f"User {request.user.username} not enrolled in course {slug}")
        return HttpResponse(status=403)

    sections = Section.objects.filter(courses=course).prefetch_related('materials', 'assessments').order_by('order')
    current_content = None
    material = None
    assessment = None
    comments = None
    assessment_locked = False
    payment_required_url = None
    is_started = False
    is_expired = False
    remaining_time = 0
    answered_questions = {}

    combined_content = []
    for section in sections:
        for m in section.materials.all():
            combined_content.append(('material', m, section))
        for a in section.assessments.all():
            combined_content.append(('assessment', a, section))

    total_content = len(combined_content)
    current_index = next((i for i, c in enumerate(combined_content) if c[0] == content_type and c[1].id == int(content_id)), 0)
    previous_url = reverse('learner:load_content', kwargs={
        'username': username, 'slug': slug,
        'content_type': combined_content[current_index - 1][0],
        'content_id': combined_content[current_index - 1][1].id
    }) if current_index > 0 else None
    next_url = reverse('learner:load_content', kwargs={
        'username': username, 'slug': slug,
        'content_type': combined_content[current_index + 1][0],
        'content_id': combined_content[current_index + 1][1].id
    }) if current_index < len(combined_content) - 1 else None

    if content_type == 'material':
        material = get_object_or_404(Material, id=content_id)
        current_content = ('material', material, next((s for s in sections if material in s.materials.all()), None))
        comments = Comment.objects.filter(material=material, parent=None).order_by('-created_at')
        if not MaterialRead.objects.filter(user=request.user, material=material).exists():
            MaterialRead.objects.create(user=request.user, material=material)
    elif content_type == 'assessment':
        assessment = get_object_or_404(Assessment, id=content_id)
        current_content = ('assessment', assessment, next((s for s in sections if assessment in s.assessments.all()), None))
        if course.payment_model == 'pay_for_exam':
            payment = Payment.objects.filter(
                user=request.user, course=course, status='completed', payment_model='pay_for_exam'
            ).first()
            if not payment:
                assessment_locked = True
                payment_required_url = reverse('payments:process_payment', kwargs={'course_id': course.id, 'payment_type': 'exam'})
                logger.info(f"Payment required for assessment {content_id} in course {course.id} for user {request.user.username}")
            else:
                if not AssessmentRead.objects.filter(user=request.user, assessment=assessment).exists():
                    AssessmentRead.objects.create(user=request.user, assessment=assessment)
        else:
            if not AssessmentRead.objects.filter(user=request.user, assessment=assessment).exists():
                AssessmentRead.objects.create(user=request.user, assessment=assessment)
        session = AssessmentSession.objects.filter(user=request.user, assessment=assessment).first()
        if session:
            is_started = True
            if session.end_time:
                remaining_time = max(0, (session.end_time - timezone.now()).total_seconds())
                is_expired = remaining_time <= 0
            else:
                remaining_time = 0  # No timer for duration_in_minutes == 0
            logger.debug(f"load_content: Assessment session user={request.user.username}, assessment={content_id}, start_time={session.start_time}, end_time={session.end_time}, remaining_time={remaining_time} sec, is_expired={is_expired}")
            answered_questions = {
                answer.question.id: answer
                for answer in QuestionAnswer.objects.filter(user=request.user, question__assessment=assessment).select_related('question', 'choice')
            }
        else:
            if assessment.duration_in_minutes == 0:
                is_started = True
                remaining_time = 0
            else:
                is_started = False

    # Update progres
    user_progress, created = CourseProgress.objects.get_or_create(user=request.user, course=course)
    if current_content and (current_index + 1) > user_progress.progress_percentage / 100 * total_content:
        user_progress.progress_percentage = (current_index + 1) / total_content * 100
        user_progress.save()

    context = {
        'course': course,
        'course_name': course.course_name,
        'username': username,
        'slug': slug,
        'sections': sections,
        'current_content': current_content,
        'material': material,
        'assessment': assessment,
        'comments': comments,
        'assessment_locked': assessment_locked,
        'payment_required_url': payment_required_url,
        'is_started': is_started,
        'is_expired': is_expired,
        'remaining_time': int(remaining_time),
        'answered_questions': answered_questions,
        'course_progress': user_progress.progress_percentage,
        'previous_url': previous_url,
        'next_url': next_url,
    }

    is_htmx = request.headers.get('HX-Request') == 'true'
    logger.info(f"load_content: Rendering for {request.path}, Content_type={content_type}, Content_id={content_id}, Comments={comments.count() if comments else 0}, is_htmx={is_htmx}, is_started={is_started}, remaining_time={remaining_time}")
    if is_htmx:
        return render(request, 'learner/partials/content.html', context)
    return render(request, 'learner/my_course.html', context)


@login_required
def start_assessment_courses(request, assessment_id):
    #logger.debug(f"start_assessment: Request={request.method}, {Path=request.path}, Headers={request.headers}")
    
    if not request.user.is_authenticated or not request.method == 'POST':
        logger.error(f"Invalid start_assessment: Auth={request.user.is_authenticated}, Method={request.method}, Path={request.path}")
        return HttpResponse(status=400)

    assessment = get_object_or_404(Assessment, id=assessment_id)
    course = assessment.section.courses  # Pastikan mengambil course yang benar
    if not Enrollment.objects.filter(user=request.user, course=course).exists():
        logger.warning(f"User {request.user.username} not enrolled in course {course.slug}, assessment_id={assessment_id}")
        return HttpResponse(status=403)

    # Create or reset session
    session, created = AssessmentSession.objects.get_or_create(
        user=request.user,
        assessment=assessment,
        defaults={
            'start_time': timezone.now(),
            'end_time': timezone.now() + timedelta(minutes=assessment.duration_in_minutes) if assessment.duration_in_minutes > 0 else None
        }
    )
    if not created and session.end_time():
        session.start_time = timezone.now()
        session.end_time = timezone.now() + timedelta(minutes=assessment.duration_in_minutes) if assessment.duration_in_minutes > 0 else None
        session.save()
        logger.debug(f"Reset session for user {request.user.username}, assessment {assessment_id}, start_time={session.start_time}, end_time={session.end_time}")
    elif created:
        logger.debug(f"New session for user {request.user.username}, assessment {assessment_id}, start_time={session.start_time}, end_time={session.end_time}")
    else:
        logger.debug(f"Using existing session: for user {request.user.username}, assessment_id={assessment_id}, start_time={session.start_time}, end_time={session.end_time}")

    # Calculate time_left
    is_started = True
    is_expired = False
    time_left = 0
    if assessment.duration_in_minutes > 0 and session.end_time:
        time_left = max(0, (session.end_time - timezone.now()).total_seconds())
        is_expired = time_left <= 0
    else:
        time_left = 0

    logger.info(f"start_assessment: assessment_id={assessment_id}, duration={assessment.duration_in_minutes} min, start_time={session.start_time}, end_time={session.end_time}, time_left={time_left}, is_expired={is_expired}, timezone={timezone.get_current_timezone_name()}")

    sections = Section.objects.filter(courses=course).prefetch_related('materials', 'assessments').all().order_by('id')
    combined_content = []
    for section in sections:
        for m in section.materials.all():
            combined_content.append(('material', m, section))
        for a in section.assessments.all():
            combined_content.append(('assessment', a, section))

    current_index = next((i for i, c in enumerate(combined_content) if c[0] == 'assessment' and c[1].id == assessment_id), 0)
    previous_url = reverse('learner:load_content', kwargs={
        'username': request.user.username,
        'slug': course.slug,
        'content_type': combined_content[current_index - 1][0],
        'content_id': combined_content[current_index - 1][1].id
    }) if current_index > 0 else None
    next_url = reverse('learner:load_content', kwargs={
        'username': request.user.username,
        'slug': course.slug,
        'content_type': combined_content[current_index + 1][0],
        'content_id': combined_content[current_index + 1][1].id
    }) if current_index < len(combined_content) - 1 else None

    context = {
        'course': course,
        'course_name': course.course_name,
        'username': request.user.username,
        'slug': course.slug,
        'sections': sections,
        'current_content': ('assessment', assessment, section),
        'material': None,
        'assessment': assessment,
        'comments': None,
        'assessment_locked': False,
        'payment_required_url': None,
        'is_started': is_started,
        'is_expired': is_expired,
        'remaining_time': int(time_left),
        'answered_questions': {
            answer.question.id: answer
            for answer in QuestionAnswer.objects.filter(user=request.user, question__assessment=assessment).select_related('question', 'choice')
        },
        'course_progress': course.get_progress(request.user) if hasattr(course, 'get_progress') else 0,
        'previous_url': previous_url,
        'next_url': next_url,
    }

    is_htmx = request.headers.get('HX-Request') == 'true'
    if not is_htmx:
        logger.warning(f"Non-HTMX request detected for start_assessment: {request.path}, Headers: {request.headers}")
        # Redirect ke URL load_content yang benar
        redirect_url = reverse('learner:load_content', kwargs={
            'username': request.user.username,
            'slug': course.slug,
            'content_type': 'assessment',
            'content_id': assessment.id
        })
        logger.info(f"Redirecting non-HTMX request to: {redirect_url}")
        return HttpResponseRedirect(redirect_url)

    logger.info(f"start_assessment: Rendering HTMX for user {request.user.username}, assessment {assessment_id}, is_htmx={is_htmx}, time_left={time_left}")
    return render(request, 'learner/partials/content.html', context)


@login_required
def submit_assessment(request, assessment_id):
    if not request.user.is_authenticated or request.method != 'POST':
        logger.warning(f"Invalid submit_assessment: Auth={request.user.is_authenticated}, Method={request.method}")
        return HttpResponse(status=400)

    assessment = get_object_or_404(Assessment, id=assessment_id)
    course = assessment.section.courses
    session = AssessmentSession.objects.filter(user=request.user, assessment=assessment).first()

    if not session:
        logger.warning(f"No session found for user {request.user.username}, assessment {assessment_id}")
        return HttpResponse(status=400)

    # Tandai sesi selesai
    session.end_time = timezone.now()
    session.save()
    logger.debug(f"Assessment submitted for user {request.user.username}, assessment {assessment_id}, end_time={session.end_time}")

    sections = Section.objects.filter(courses=course).prefetch_related('materials', 'assessments').order_by('order')
    combined_content = []
    for section in sections:
        for m in section.materials.all():
            combined_content.append(('material', m, section))
        for a in section.assessments.all():
            combined_content.append(('assessment', a, section))

    current_index = next((i for i, c in enumerate(combined_content) if c[0] == 'assessment' and c[1].id == assessment_id), 0)
    previous_url = reverse('learner:load_content', kwargs={
        'username': request.user.username, 'slug': course.slug,
        'content_type': combined_content[current_index - 1][0],
        'content_id': combined_content[current_index - 1][1].id
    }) if current_index > 0 else None
    next_url = reverse('learner:load_content', kwargs={
        'username': request.user.username, 'slug': course.slug,
        'content_type': combined_content[current_index + 1][0],
        'content_id': combined_content[current_index + 1][1].id
    }) if current_index < len(combined_content) - 1 else None

    context = {
        'course': course,
        'course_name': course.course_name,
        'username': request.user.username,
        'slug': course.slug,
        'sections': sections,
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
            answer.question.id: answer
            for answer in QuestionAnswer.objects.filter(user=request.user, assessment=assessment).select_related('question', 'choice')
        },
        'course_progress': course.get_progress(request.user) if hasattr(course, 'get_progress') else 0,
        'previous_url': previous_url,
        'next_url': next_url,
    }

    is_htmx = request.headers.get('HX-Request') == 'true'
    logger.info(f"submit_assessment: Rendering for user {request.user.username}, assessment {assessment_id}, is_htmx={is_htmx}")
    return render(request, 'learner/partials/content.html', context)


@login_required
def submit_answer(request):
    if not request.user.is_authenticated or request.method != 'POST':
        logger.warning(f"Invalid submit_answer: Auth={request.user.is_authenticated}, Method={request.method}")
        return HttpResponse(status=400)
    logger.debug(f"submit_answer POST data: {request.POST}")

    question_id = request.POST.get('question_id')
    choice_id = request.POST.get('choice_id')

    if not question_id or not choice_id:
        logger.warning(f"Missing question_id or choice_id in submit_answer for user {request.user.username}")
        return HttpResponse(status=400)

    question = get_object_or_404(Question, id=question_id)
    choice = get_object_or_404(Choice, id=choice_id)
    assessment = question.assessment
    course = assessment.section.courses

    if not Enrollment.objects.filter(user=request.user, course=course).exists():
        logger.warning(f"User {request.user.username} not enrolled in course {course.slug}")
        return HttpResponse(status=403)

    # Simpan jawaban
    QuestionAnswer.objects.update_or_create(
        user=request.user,
        question=question,
        defaults={'choice': choice}
    )
    logger.debug(f"Answer submitted for user {request.user.username}, question {question_id}, choice {choice_id}")

    # Muat ulang konten assessment
    session = AssessmentSession.objects.filter(user=request.user, assessment=assessment).first()
    is_started = False
    is_expired = False
    remaining_time = 0
    if session:
        is_started = True
        if session.end_time:
            remaining_time = max(0, (session.end_time - timezone.now()).total_seconds())
            is_expired = remaining_time <= 0
        else:
            remaining_time = 0

    sections = Section.objects.filter(courses=course).prefetch_related('materials', 'assessments').order_by('order')
    combined_content = []
    for section in sections:
        for m in section.materials.all():
            combined_content.append(('material', m, section))
        for a in section.assessments.all():
            combined_content.append(('assessment', a, section))

    current_index = next((i for i, c in enumerate(combined_content) if c[0] == 'assessment' and c[1].id == assessment.id), 0)
    previous_url = reverse('learner:load_content', kwargs={
        'username': request.user.username, 'slug': course.slug,
        'content_type': combined_content[current_index - 1][0],
        'content_id': combined_content[current_index - 1][1].id
    }) if current_index > 0 else None
    next_url = reverse('learner:load_content', kwargs={
        'username': request.user.username, 'slug': course.slug,
        'content_type': combined_content[current_index + 1][0],
        'content_id': combined_content[current_index + 1][1].id
    }) if current_index < len(combined_content) - 1 else None

    context = {
        'course': course,
        'course_name': course.course_name,
        'username': request.user.username,
        'slug': course.slug,
        'sections': sections,
        'current_content': ('assessment', assessment, assessment.section),
        'material': None,
        'assessment': assessment,
        'comments': None,
        'assessment_locked': False,
        'payment_required_url': None,
        'is_started': is_started,
        'is_expired': is_expired,
        'remaining_time': int(remaining_time),
        'answered_questions': {
            answer.question.id: answer
            for answer in QuestionAnswer.objects.filter(user=request.user, question__assessment=assessment).select_related('question', 'choice')
        },
        'course_progress': course.get_progress(request.user) if hasattr(course, 'get_progress') else 0,
        'previous_url': previous_url,
        'next_url': next_url,
        
    }

    is_htmx = request.headers.get('HX-Request') == 'true'
    logger.info(f"submit_answer: Rendering for user {request.user.username}, assessment {assessment.id}, question {question_id}, is_htmx={is_htmx}")
    return render(request, 'learner/partials/content.html', context)

#add coment matrial course
def is_bot(request):
    """
    Mengecek apakah permintaan berasal dari bot.
    Dengan melihat user-agent dan header lainnya.
    """
    user_agent = request.META.get('HTTP_USER_AGENT', '').lower()
    if 'bot' in user_agent or 'crawler' in user_agent:
        return True  # Bot terdeteksi
    return False


def is_suspicious(request):
    """Check if the request is suspicious based on User-Agent or missing Referer."""
    user_agent = request.META.get('HTTP_USER_AGENT', '')
    referer = request.META.get('HTTP_REFERER', '')
    
    # Bot detection (simple heuristic)
    if 'bot' in user_agent.lower() or not referer:
        return True
    return False


def is_spam(request, user, content):
    """
    Memeriksa apakah komentar terdeteksi sebagai spam berdasarkan
    rate-limiting, bot detection dan blacklist keywords.
    """
    # 1. Cek Bot Detection
    if is_bot(request):
        return True  # Bot terdeteksi, komentar dianggap spam
    
    # 2. Cek Rate Limiting (Spam)
    time_limit = timedelta(seconds=30)  # Menentukan batas waktu antara komentar
    last_comment = Comment.objects.filter(user=user).order_by('-created_at').first()
    if last_comment and timezone.now() - last_comment.created_at < time_limit:
        return True  # Terlalu cepat mengirim komentar, dianggap spam
    
    # 3. Cek Kata Kunci yang Diblokir menggunakan metode model
    comment_instance = Comment(user=user, content=content)
    if comment_instance.contains_blacklisted_keywords():
        return True  # Mengandung kata terlarang, dianggap spam
    
    return False


@login_required
def add_comment(request):
    if not request.user.is_authenticated or request.method != 'POST':
        logger.warning(f"Invalid request: Auth={request.user.is_authenticated}, Method={request.method}")
        return HttpResponse(status=400)

    comment_text = request.POST.get('comment_text')
    material_id = request.POST.get('material_id')
    parent_id = request.POST.get('parent_id')
    if not comment_text or not material_id:
        logger.warning(f"Missing required fields: comment_text={bool(comment_text)}, material_id={material_id}")
        return HttpResponse(status=400)

    material = get_object_or_404(Material, id=material_id)
    if not material.section or not material.section.courses:
        logger.warning(f"Invalid material: section={material.section}, courses={material.section.courses if material.section else None}")
        messages.warning(request, "Material tidak valid atau tidak terkait dengan kursus.")
        return HttpResponse(status=400)

    course = material.section.courses
    parent_comment = None
    if parent_id:
        parent_comment = get_object_or_404(Comment, id=parent_id, material=material)  # Validasi material
        if parent_comment.material != material:
            logger.warning(f"Invalid parent comment: parent_id={parent_id}, material_id={material_id}")
            messages.warning(request, "Komentar induk tidak valid.")
            return HttpResponse(status=400)

    # Pemeriksaan keamanan
    if is_suspicious(request):
        logger.warning(f"Suspicious activity detected by {request.user.username}")
        messages.warning(request, "Aktivitas mencurigakan terdeteksi. Komentar tidak diposting.")
        return HttpResponseRedirect(reverse('learner:load_content', kwargs={
            'username': request.user.username, 'slug': course.slug, 'content_type': 'material', 'content_id': material_id
        }))

    # Pemeriksaan spam
    if is_spam(request, request.user, comment_text):
        logger.warning(f"Spam comment detected by {request.user.username}: {comment_text}")
        messages.warning(request, "Komentar Anda terdeteksi sebagai spam!")
        return HttpResponseRedirect(reverse('learner:load_content', kwargs={
            'username': request.user.username, 'slug': course.slug, 'content_type': 'material', 'content_id': material_id
        }))

    # Pemeriksaan blacklisted keywords
    comment = Comment(user=request.user, material=material, content=comment_text, parent=parent_comment)
    if comment.contains_blacklisted_keywords():
        logger.warning(f"Comment by {request.user.username} contains blacklisted keywords: {comment_text}")
        messages.warning(request, "Komentar mengandung kata-kata yang tidak diizinkan.")
        return HttpResponseRedirect(reverse('learner:load_content', kwargs={
            'username': request.user.username, 'slug': course.slug, 'content_type': 'material', 'content_id': material_id
        }))

    # Simpan komentar
    comment.save()
    logger.debug(f"Comment added by {request.user.username} for material {material_id}, parent_id={parent_id}")

    # Untuk HTMX, kembalikan partial comments.html
    is_htmx = getattr(request, 'htmx', False) or request.headers.get('HX-Request') == 'true'
    if is_htmx:
        context = {
            'comments': Comment.objects.filter(material=material).select_related('user', 'parent'),
            'material': material,
        }
        messages.success(request, "Komentar berhasil diposting!")
        return render(request, 'learner/partials/comments.html', context)

    # Untuk non-HTMX, redirect dengan pesan
    messages.success(request, "Komentar berhasil diposting!")
    redirect_url = reverse('learner:load_content', kwargs={
        'username': request.user.username,
        'slug': course.slug,
        'content_type': 'material',
        'content_id': material_id
    })
    return HttpResponseRedirect(redirect_url)


def get_progress(request, username, slug):
    if not request.user.is_authenticated or request.user.username != username:
        return HttpResponse(status=403)
    course = get_object_or_404(Course, slug=slug)
    user_progress, _ = CourseProgress.objects.get_or_create(user=request.user, course=course)
    return render(request, 'learner/partials/progress.html', {'course_progress': user_progress.progress_percentage})


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
