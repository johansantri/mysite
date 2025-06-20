import csv
import logging
from datetime import timedelta
from decimal import Decimal
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.mail import send_mail
from django.core.paginator import Paginator
from django.db.models import Avg, Count, Prefetch, F
from django.db import transaction
from django.http import HttpResponse, HttpResponseRedirect, JsonResponse
from django.shortcuts import get_object_or_404, render
from django.urls import reverse, NoReverseMatch
from django.utils import timezone
from django.template.defaultfilters import linebreaks
from django.middleware.csrf import get_token
from authentication.models import CustomUser, Universiti
from courses.models import (
    Assessment, AssessmentRead, AssessmentScore, AssessmentSession,
    AskOra, Choice, Comment, Course, CourseProgress, CourseStatusHistory,
    Enrollment, GradeRange, Instructor, LTIExternalTool, Material,
    MaterialRead, Payment, PeerReview, Question, QuestionAnswer,
    Score, Section, Submission, UserActivityLog, CommentReaction, AttemptedQuestion
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

def _get_navigation_urls(username, slug, combined_content, current_index):
    """
    Generate previous and next URLs for navigation.
    
    Args:
        username: Username of the current user.
        slug: Course slug.
        combined_content: List of combined content.
        current_index: Current content index.
    
    Returns:
        Tuple: (previous_url, next_url).
    """
    previous_url = None
    next_url = None
    try:
        if current_index > 0:
            previous_url = reverse('learner:load_content', kwargs={
                'username': username, 'slug': slug,
                'content_type': combined_content[current_index - 1][0],
                'content_id': combined_content[current_index - 1][1].id
            })
        if current_index < len(combined_content) - 1:
            next_url = reverse('learner:load_content', kwargs={
                'username': username, 'slug': slug,
                'content_type': combined_content[current_index + 1][0],
                'content_id': combined_content[current_index + 1][1].id
            })
    except NoReverseMatch as e:
        logger.error(f"NoReverseMatch in _get_navigation_urls: {str(e)}")
    return previous_url, next_url

def _build_assessment_context(assessment, user):
    """
    Build context for assessment-related data (AskOra, submissions, peer reviews).
    
    Args:
        assessment: Assessment object.
        user: CustomUser object.
    
    Returns:
        Dict: Context dictionary with assessment-related data.
    """
    ask_oras = AskOra.objects.filter(assessment=assessment)
    user_submissions = Submission.objects.filter(askora__assessment=assessment, user=user)
    submitted_askora_ids = set(user_submissions.values_list('askora_id', flat=True))
    now = timezone.now()
    
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
        'peer_review_stats': None,
        'submissions': Submission.objects.filter(
            askora__assessment=assessment
        ).exclude(
            user=user
        ).exclude(
            id__in=PeerReview.objects.filter(reviewer=user).values('submission__id')
        ),
        'is_quiz': assessment.questions.exists(),
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
    """
    Toggle like/dislike reaction on a comment.
    
    Args:
        request: HTTP request object.
        comment_id: ID of the comment.
        reaction_type: Type of reaction ('like' or 'dislike').
    
    Returns:
        HttpResponse: Updated comments partial or redirect.
    """
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
                    logger.debug(f"User {request.user.username} removed {reaction_type} from comment {comment_id}")
                else:
                    existing_reaction.delete()
                    CommentReaction.objects.create(user=request.user, comment=comment, reaction_type=reaction_value)
                    if reaction_value == CommentReaction.REACTION_LIKE:
                        Comment.objects.filter(id=comment_id).update(likes=F('likes') + 1, dislikes=F('dislikes') - 1)
                    else:
                        Comment.objects.filter(id=comment_id).update(dislikes=F('dislikes') + 1, likes=F('likes') - 1)
                    logger.debug(f"User {request.user.username} changed reaction to {reaction_type} on comment {comment_id}")
            else:
                CommentReaction.objects.create(user=request.user, comment=comment, reaction_type=reaction_value)
                if reaction_value == CommentReaction.REACTION_LIKE:
                    Comment.objects.filter(id=comment_id).update(likes=F('likes') + 1)
                else:
                    Comment.objects.filter(id=comment_id).update(dislikes=F('dislikes') + 1)
                logger.debug(f"User {request.user.username} added {reaction_type} to comment {comment_id}")

        is_htmx = request.headers.get('HX-Request') == 'true'
        if is_htmx:
            context = {
                'comments': Comment.objects.filter(material=material).select_related('user', 'parent'),
                'material': material,
                'user_reactions': {
                    r.comment_id: r.reaction_type for r in CommentReaction.objects.filter(
                        user=request.user, comment__material=material
                    )
                },
            }
            return render(request, 'learner/partials/comments.html', context)

        redirect_url = reverse('learner:load_content', kwargs={
            'username': request.user.username,
            'slug': material.section.course.slug,
            'content_type': 'material',
            'content_id': material.id
        })
        return HttpResponseRedirect(redirect_url)

    except Exception as e:
        logger.error(f"Error toggling reaction for comment {comment_id}: {str(e)}", exc_info=True)
        is_htmx = request.headers.get('HX-Request') == 'true'
        if is_htmx:
            return render(request, 'learner/partials/error.html', {
                'error_message': 'Terjadi kesalahan saat memproses reaksi.'
            }, status=500)
        return HttpResponse(status=500)

@login_required
def my_course(request, username, slug):
    """
    Display the user's course page with materials and assessments.
    
    Args:
        request: HTTP request object.
        username: Username of the user.
        slug: Course slug.
    
    Returns:
        HttpResponse: Rendered course page.
    """
    if request.user.username != username:
        logger.warning(f"Unauthorized access attempt by {request.user.username} for {username}")
        return HttpResponse(status=403)

    course = get_object_or_404(Course, slug=slug)
    if not Enrollment.objects.filter(user=request.user, course=course).exists():
        logger.warning(f"User {request.user.username} not enrolled in course {slug}")
        return HttpResponse(status=403)

    sections = Section.objects.filter(course=course).prefetch_related(
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
        'show_timer': False,
    }

    assessment_id = request.GET.get('assessment_id')
    current_index = 0
    if assessment_id:
        assessment = get_object_or_404(Assessment, id=assessment_id)
        context['assessment'] = assessment
        context['current_content'] = ('assessment', assessment, next((s for s in sections if assessment in s.assessments.all()), None))
        current_index = next((i for i, c in enumerate(combined_content) if c[0] == 'assessment' and c[1].id == assessment.id), 0)

        if course.payment_model == 'pay_for_exam':
            payment = Payment.objects.filter(
                user=request.user, course=course, status='completed', payment_model='pay_for_exam'
            ).first()
            if not payment:
                context['assessment_locked'] = True
                context['payment_required_url'] = reverse('payments:process_payment', kwargs={
                    'course_id': course.id, 'payment_type': 'exam'
                })
                logger.info(f"Payment required for assessment {assessment_id} in course {course.id} for user {request.user.username}")
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
                context.update(_build_assessment_context(context['assessment'], request.user))

    context['previous_url'], context['next_url'] = _get_navigation_urls(username, slug, combined_content, current_index)
    user_progress, _ = CourseProgress.objects.get_or_create(user=request.user, course=course)
    if context['current_content'] and (current_index + 1) > user_progress.progress_percentage / 100 * total_content:
        user_progress.progress_percentage = (current_index + 1) / total_content * 100
        user_progress.save()
    context['course_progress'] = user_progress.progress_percentage
    context['can_review'] = bool(context['submissions'])

    logger.info(f"my_course: Rendering for user {username}, course {slug}, assessment_id={assessment_id}")
    response = render(request, 'learner/my_course.html', context)
    response['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    return response

@login_required
def load_content(request, username, slug, content_type, content_id):
    """
    Load specific course content (material or assessment).
    
    Args:
        request: HTTP request object.
        username: Username of the user.
        slug: Course slug.
        content_type: Type of content ('material' or 'assessment').
        content_id: ID of the content.
    
    Returns:
        HttpResponse: Rendered content partial or full page.
    """
    if request.user.username != username:
        logger.warning(f"Unauthorized access attempt by {request.user.username} for {username}")
        return HttpResponse(status=403)

    course = get_object_or_404(Course, slug=slug)
    if not Enrollment.objects.filter(user=request.user, course=course).exists():
        logger.warning(f"User {request.user.username} not enrolled in course {slug}")
        return HttpResponse(status=403)

    sections = Section.objects.filter(courses=course).prefetch_related(  # Changed 'course' to 'courses'
        Prefetch('materials', queryset=Material.objects.all()),
        Prefetch('assessments', queryset=Assessment.objects.all())
    ).order_by('order')
    combined_content = _build_combined_content(sections)
    current_index = next((i for i, c in enumerate(combined_content) if c[0] == content_type and c[1].id == int(content_id)), 0)
    current_content = combined_content[current_index] if combined_content else None

    context = {
        'course': course,
        'course_name': course.course_name,
        'username': username,
        'slug': slug,
        'sections': sections,
        'current_content': current_content,
        'material': None,
        'assessment': None,
        'comments': None,
        'assessment_locked': False,
        'payment_required_url': None,
        'is_started': False,
        'is_expired': False,
        'remaining_time': 0,
        'answered_questions': {},
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
        'show_timer': False,
    }

    if content_type == 'material':
        context['material'] = get_object_or_404(Material, id=content_id)
        context['comments'] = Comment.objects.filter(
            material=context['material'], parent=None
        ).order_by('-created_at')
        MaterialRead.objects.get_or_create(user=request.user, material=context['material'])
    elif content_type == 'assessment':
        context['assessment'] = get_object_or_404(Assessment, id=content_id)
        context.update(_build_assessment_context(context['assessment'], request.user))
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
                AssessmentRead.objects.get_or_create(user=request.user, assessment=context['assessment'])
        else:
            AssessmentRead.objects.get_or_create(user=request.user, assessment=context['assessment'])
        if context['is_quiz']:
            session = AssessmentSession.objects.filter(user=request.user, assessment=context['assessment']).first()
            if session:
                context['is_started'] = True
                if session.end_time:
                    context['remaining_time'] = max(0, int((session.end_time - timezone.now()).total_seconds()))
                    context['is_expired'] = context['remaining_time'] <= 0
                    context['show_timer'] = context['remaining_time'] > 0
                context['answered_questions'] = {
                    a.question.id: a for a in QuestionAnswer.objects.filter(
                        user=request.user, question__assessment=context['assessment']
                    ).select_related('question', 'choice')
                }

    context['previous_url'], context['next_url'] = _get_navigation_urls(username, slug, combined_content, current_index)
    user_progress, _ = CourseProgress.objects.get_or_create(user=request.user, course=course)
    total_content = len(combined_content)
    if current_index + 1 > user_progress.progress_percentage / 100 * total_content:
        user_progress.progress_percentage = ((current_index + 1) / total_content) * 100
        user_progress.save()
    context['course_progress'] = user_progress.progress_percentage
    context['can_review'] = bool(context['submissions'])

    is_htmx = request.headers.get('HX-Request') == 'true'
    template = 'learner/partials/content.html' if is_htmx else 'learner/my_course.html'
    logger.info(f"load_content: Rendering {template} for user {username}, {content_type} {content_id}")
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
    context['previous_url'], context['next_url'] = _get_navigation_urls(request.user.username, course.slug, combined_content, current_index)

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
    
    Args:
        request: HTTP request object.
        assessment_id: ID of the assessment.
    
    Returns:
        HttpResponse: Rendered assessment partial or redirect.
    """
    if request.method != 'POST':
        logger.warning(f"Invalid request method: {request.method} for submit_assessment_new")
        return render(request, 'learner/partials/error.html', {
            'error_message': 'Permintaan tidak valid.'
        }, status=400) if request.headers.get('HX-Request') == 'true' else HttpResponse(status=400)

    assessment = get_object_or_404(Assessment.objects.select_related('section__courses'), id=assessment_id)  # Fixed: 'section__course' to 'section__courses'
    course = assessment.section.courses  # Fixed: 'course' to 'courses'
    session = AssessmentSession.objects.filter(user=request.user, assessment=assessment).first()

    if not session:
        logger.error(f"No session found for user {request.user.username}, assessment {assessment_id}")  # Changed to 'error' for severity
        return render(request, 'learner/partials/error.html', {
            'error_message': 'Sesi penilaian tidak ditemukan.'
        }, status=400) if request.headers.get('HX-Request') == 'true' else HttpResponse(status=400)

    session.end_time = timezone.now()
    session.save()
    logger.debug(f"Assessment submitted for user {request.user.username}, assessment {assessment_id}")

    context = {
        'course': course,
        'course_name': course.course_name,
        'username': request.user.username,
        'slug': course.slug,
        'sections': Section.objects.filter(courses=course).prefetch_related('materials', 'assessments').order_by('order'),  # Fixed: 'course' to 'courses'
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

    context.update(_build_assessment_context(assessment, request.user))
    context['can_review'] = bool(context['submissions'])

    combined_content = _build_combined_content(context['sections'])
    current_index = next((i for i, c in enumerate(combined_content) if c[0] == 'assessment' and c[1].id == assessment_id), 0)
    context['previous_url'], context['next_url'] = _get_navigation_urls(request.user.username, course.slug, combined_content, current_index)

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
    context['previous_url'], context['next_url'] = _get_navigation_urls(request.user.username, course.slug, combined_content, current_index)

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
    course = material.section.course
    parent_comment = get_object_or_404(Comment, id=parent_id, material=material) if parent_id else None

    if is_suspicious(request):
        logger.warning(f"Suspicious activity detected by {request.user.username}")
        messages.warning(request, "Aktivitas mencurigakan terdeteksi.")
        return HttpResponseRedirect(reverse('learner:load_content', kwargs={
            'username': request.user.username, 'slug': course.slug,
            'content_type': 'material', 'content_id': material_id
        }))

    if is_spam(request, request.user, comment_text):
        logger.warning(f"Spam comment detected by {request.user.username}: {comment_text}")
        messages.warning(request, "Komentar Anda terdeteksi sebagai spam!")
        return HttpResponseRedirect(reverse('learner:load_content', kwargs={
            'username': request.user.username, 'slug': course.slug,
            'content_type': 'material', 'content_id': material_id
        }))

    comment = Comment(user=request.user, material=material, content=comment_text, parent=parent_comment)
    if comment.contains_blacklisted_keywords():
        logger.warning(f"Comment by {request.user.username} contains blacklisted keywords: {comment_text}")
        messages.warning(request, "Komentar mengandung kata-kata yang tidak diizinkan.")
        return HttpResponseRedirect(reverse('learner:load_content', kwargs={
            'username': request.user.username, 'slug': course.slug,
            'content_type': 'material', 'content_id': material_id
        }))

    comment.save()
    logger.debug(f"Comment added by {request.user.username} for material {material_id}, parent_id={parent_id}")

    is_htmx = request.headers.get('HX-Request') == 'true'
    if is_htmx:
        context = {
            'comments': Comment.objects.filter(material=material).select_related('user', 'parent'),
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
        'username': request.user.username, 'slug': course.slug,
        'content_type': 'material', 'content_id': material_id
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
    Submit an answer for an AskOra question.
    
    Args:
        request: HTTP request object.
        ask_ora_id: ID of the AskOra question.
    
    Returns:
        HttpResponse: Rendered success or error message.
    """
    ask_ora = get_object_or_404(AskOra, id=ask_ora_id)
    assessment = ask_ora.assessment

    if not ask_ora.is_responsive():
        logger.warning(f"Submission deadline expired for ask_ora {ask_ora_id}")
        return HttpResponse(
            '<div class="alert alert-danger">Batas waktu pengiriman telah berakhir.</div>',
            status=400
        )

    if Submission.objects.filter(askora=ask_ora, user=request.user).exists():
        logger.warning(f"Duplicate submission attempt for ask_ora {ask_ora_id} by {request.user.username}")
        return HttpResponse(
            '<div class="alert alert-warning">Anda sudah mengirimkan jawaban untuk pertanyaan ini.</div>',
            status=400
        )

    if request.method != 'POST':
        logger.warning(f"Invalid request method: {request.method} for submit_answer_askora_new")
        return HttpResponse(
            '<div class="alert alert-danger">Metode request tidak valid.</div>',
            status=400
        )

    answer_text = request.POST.get('answer_text')
    answer_file = request.FILES.get('answer_file')
    if not answer_text:
        logger.warning(f"Missing answer_text for ask_ora {ask_ora_id} by {request.user.username}")
        return HttpResponse(
            '<div class="alert alert-danger">Jawaban teks diperlukan.</div>',
            status=400
        )

    submission = Submission.objects.create(
        askora=ask_ora,
        user=request.user,
        answer_text=answer_text,
        answer_file=answer_file
    )
    logger.debug(f"Submission created for ask_ora {ask_ora_id} by {request.user.username}")

    can_review = Submission.objects.filter(
        askora__assessment=assessment
    ).exclude(user=request.user).exists()

    response_html = f"""
        <div class="alert alert-success">
            <div class="d-flex align-items-center">
                <i class="bi bi-check-circle-fill fs-3 me-3"></i>
                <div>
                    <h5 class="mb-1">Jawaban Berhasil Dikirim!</h5>
                    <p class="mb-0">Terima kasih telah mengirimkan jawaban Anda.</p>
                </div>
            </div>
        </div>
        <div class="card border-success mb-4">
            <div class="card-header bg-success text-white">
                <i class="bi bi-info-circle"></i> Langkah Selanjutnya
            </div>
            <div class="card-body">
                {(
                    f'<p>✅ <strong>Sekarang Anda bisa meninjau jawaban teman-teman Anda.</strong></p>'
                    f'<a href="#peer-review-section" class="btn btn-success">Lihat Jawaban Teman</a>'
                    if can_review else
                    '<p>⏳ Nilai akan muncul setelah jawaban Anda direview oleh teman-teman dan instruktur.</p>'
                )}
                <hr>
                <p class="small text-muted mb-0"><i class="bi bi-clock-history"></i> Jawaban dikirim pada {timezone.now().strftime("%d %B %Y %H:%M")}</p>
            </div>
        </div>
        <div class="card mb-4">
            <div class="card-header">
                <h5>Jawaban Anda</h5>
            </div>
            <div class="card-body">
                <p><strong>Pertanyaan:</strong> {ask_ora.title}</p>
                <div class="bg-light p-3 rounded mb-3">
                    {linebreaks(submission.answer_text)}
                </div>
                {(
                    f'<p><a href="{submission.answer_file.url}" class="btn btn-sm btn-primary"><i class="bi bi-download"></i> Unduh File Lampiran</a></p>'
                    if submission.answer_file else ''
                )}
            </div>
        </div>
    """

    if can_review:
        submissions_to_review = Submission.objects.filter(
            askora__assessment=assessment
        ).exclude(user=request.user).select_related('user', 'askora')
        response_html += f"""
            <div id="peer-review-section" class="mt-4">
                <div class="d-flex justify-content-between align-items-center mb-3">
                    <h4><i class="bi bi-people-fill"></i> Tinjau Jawaban Teman</h4>
                    <span class="badge bg-primary">{submissions_to_review.count()} jawaban</span>
                </div>
                <div class="alert alert-info">
                    <h5><i class="bi bi-lightbulb"></i> Panduan Review:</h5>
                    <ol class="mb-0">
                        <li>Baca jawaban dengan seksama</li>
                        <li>Berikan skor 1-5 (1 = sangat buruk, 5 = sangat baik)</li>
                        <li>Beri komentar yang membangun (opsional)</li>
                        <li>Review Anda akan mempengaruhi nilai teman</li>
                    </ol>
                </div>
        """
        for sub in submissions_to_review:
            response_html += f"""
                <div class="card mb-3">
                    <div class="card-body">
                        <div class="d-flex justify-content-between">
                            <h5>{sub.askora.title}</h5>
                            <small class="text-muted">Oleh: {sub.user.get_full_name or sub.user.username}</small>
                        </div>
                        <div class="bg-light p-3 rounded my-3">
                            {linebreaks(sub.answer_text)}
                        </div>
                        {(
                            f'<p><a href="{sub.answer_file.url}" class="btn btn-sm btn-outline-secondary mb-3"><i class="bi bi-download"></i> Unduh File</a></p>'
                            if sub.answer_file else ''
                        )}
                        <form method="post" 
                              hx-post="{reverse('learner:submit_peer_review_new', args=[sub.id])}"
                              hx-target="#content-area"
                              hx-swap="innerHTML">
                            <input type="hidden" name="csrfmiddlewaretoken" value="{get_token(request)}">
                            <div class="mb-3">
                                <label class="form-label"><i class="bi bi-star-fill"></i> Berikan Nilai (1-5)</label>
                                <select name="score" class="form-select" required>
                                    <option value="">Pilih nilai...</option>
                                    <option value="1">1 - Sangat Buruk</option>
                                    <option value="2">2 - Buruk</option>
                                    <option value="3">3 - Cukup</option>
                                    <option value="4">4 - Baik</option>
                                    <option value="5">5 - Sangat Baik</option>
                                </select>
                            </div>
                            <div class="mb-3">
                                <label class="form-label"><i class="bi bi-chat-left-text"></i> Komentar (opsional)</label>
                                <textarea name="comment" class="form-control" rows="3" placeholder="Berikan masukan yang membangun..."></textarea>
                            </div>
                            <button type="submit" class="btn btn-primary">
                                <i class="bi bi-send"></i> Kirim Review
                            </button>
                        </form>
                    </div>
                </div>
            """
        response_html += "</div>"

    response_html += """
        <script>
            if (document.getElementById('peer-review-section')) {
                document.getElementById('peer-review-section').scrollIntoView({ behavior: 'smooth' });
            }
        </script>
    """
    return HttpResponse(response_html)

@login_required
def submit_peer_review_new(request, submission_id):
    """
    Submit a peer review for a submission.
    
    Args:
        request: HTTP request object.
        submission_id: ID of the submission to review.
    
    Returns:
        HttpResponse: Rendered success or error message.
    """
    submission = get_object_or_404(Submission, id=submission_id)
    if PeerReview.objects.filter(submission=submission, reviewer=request.user).exists():
        logger.warning(f"Duplicate review attempt for submission {submission_id} by {request.user.username}")
        return HttpResponse(
            '<div class="alert alert-warning">Anda sudah memberikan review untuk jawaban ini.</div>',
            status=400
        )

    if request.method != 'POST':
        logger.warning(f"Invalid request method: {request.method} for submit_peer_review_new")
        return HttpResponse(
            '<div class="alert alert-danger">Metode request tidak valid.</div>',
            status=400
        )

    try:
        score = int(request.POST.get('score'))
        if not 1 <= score <= 5:
            raise ValueError("Nilai harus antara 1-5")
        comment = request.POST.get('comment', '').strip()

        PeerReview.objects.create(
            submission=submission,
            reviewer=request.user,
            score=score,
            comment=comment if comment else None
        )

        assessment_score, _ = AssessmentScore.objects.get_or_create(submission=submission)
        assessment_score.calculate_final_score()
        logger.debug(f"Peer review submitted for submission {submission_id} by {request.user.username}")

        return HttpResponse(f"""
            <div class="alert alert-success">
                <div class="d-flex align-items-center">
                    <i class="bi bi-check-circle-fill fs-3 me-3"></i>
                    <div>
                        <h5 class="mb-1">Review Berhasil Dikirim!</h5>
                        <p class="mb-0">Terima kasih telah memberikan penilaian.</p>
                    </div>
                </div>
            </div>
            <script>
                htmx.ajax('GET', '{reverse("learner:load_content", kwargs={
                    "username": request.user.username,
                    "slug": submission.askora.assessment.section.course.slug,
                    "content_type": "assessment",
                    "content_id": submission.askora.assessment.id
                })}', {{
                    target: "#content-area",
                    swap: "innerHTML",
                    headers: {{"HX-Trigger": "contentLoaded"}}
                }});
            </script>
        """)

    except (ValueError, TypeError):
        logger.warning(f"Invalid score for submission {submission_id} by {request.user.username}")
        return HttpResponse(
            '<div class="alert alert-danger">Nilai harus berupa angka antara 1-5.</div>',
            status=400
        )

def learner_detail(request, username):
    """
    Display a learner's public profile with completed courses and instructor info.
    
    Args:
        request: HTTP request object.
        username: Username of the learner.
    
    Returns:
        HttpResponse: Rendered learner profile page.
    """
    learner = get_object_or_404(CustomUser, username=username)
    enrollments = Enrollment.objects.filter(user=learner).select_related('course')
    instructor = Instructor.objects.filter(user=learner).first()
    completed_courses_data = []

    for enrollment in enrollments:
        course = enrollment.course
        materials = Material.objects.filter(section__course=course).distinct()
        total_materials = materials.count()
        materials_read = MaterialRead.objects.filter(user=learner, material__in=materials).count()
        materials_read_percentage = (materials_read / total_materials * 100) if total_materials > 0 else 0

        assessments = Assessment.objects.filter(section__course=course).distinct()
        total_assessments = assessments.count()
        assessments_completed = AssessmentRead.objects.filter(user=learner, assessment__in=assessments).count()
        assessments_completed_percentage = (assessments_completed / total_assessments * 100) if total_assessments > 0 else 0

        progress = (materials_read_percentage + assessments_completed_percentage) / 2 if (total_materials + total_assessments) > 0 else 0
        course_progress, _ = CourseProgress.objects.get_or_create(user=learner, course=course)
        course_progress.progress_percentage = progress
        course_progress.save()

        grade_range = GradeRange.objects.filter(course=course, name='Pass').first()
        passing_threshold = grade_range.min_grade if grade_range else Decimal('52.00')

        total_score = Decimal('0')
        total_max_score = Decimal('0')
        for assessment in assessments:
            score_value = Decimal('0')
            total_questions = assessment.questions.count()
            if total_questions > 0:
                correct_answers = QuestionAnswer.objects.filter(
                    user=learner, question__assessment=assessment, choice__is_correct=True
                ).count()
                score_value = (Decimal(correct_answers) / Decimal(total_questions)) * assessment.weight if total_questions > 0 else Decimal('0')
            else:
                submission = Submission.objects.filter(askora__assessment=assessment, user=learner).order_by('-submitted_at').first()
                if submission:
                    assessment_score = AssessmentScore.objects.filter(submission=submission).first()
                    if assessment_score:
                        score_value = assessment_score.final_score

            total_score += min(score_value, assessment.weight)
            total_max_score += assessment.weight

        overall_percentage = (total_score / total_max_score * 100) if total_max_score > 0 else 0
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