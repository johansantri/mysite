# Standard library
import os
import re
import csv
import time
import json
import uuid
import hmac
import html
import base64
import random
import string
import logging
import hashlib
import urllib
from io import BytesIO
from datetime import datetime, timedelta, timezone
from decimal import Decimal, ROUND_DOWN
from urllib.parse import quote, urlparse, parse_qs, urlencode


# Third-party packages
import pytz
import qrcode
import bleach
import requests
from PIL import Image
from jose import jwt
from jose import jwk as jose_jwk
from jose.utils import base64url_decode
from jwt import get_unverified_header, decode as jwt_decode, algorithms
from jwt.algorithms import RSAAlgorithm
from oauthlib.oauth1 import Client, Client as OAuth1Client
from oauthlib.common import to_unicode
from requests_oauthlib import OAuth1, OAuth1Session
from weasyprint import HTML
from django_ckeditor_5.widgets import CKEditor5Widget

# Django core
from django import forms
from django.conf import settings
from django.urls import reverse
from django.db import DatabaseError, IntegrityError
from django.db.models import (
    Q, F, Sum, Count, Avg,
    OuterRef, Subquery, IntegerField, Prefetch
)
from django.core.cache import cache
from django.core.files.base import ContentFile
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.core.exceptions import ObjectDoesNotExist, PermissionDenied, ValidationError
from django.middleware.csrf import get_token
from django.template.loader import render_to_string
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from django.utils.timezone import now
from django.utils.text import slugify
from django.http import (
    JsonResponse, Http404, HttpResponse, HttpResponseForbidden,
    HttpResponseNotFound, HttpResponseBadRequest, HttpResponseRedirect
)
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.views.decorators.cache import cache_page
from django.views.decorators.csrf import csrf_exempt, csrf_protect
from django.views.decorators.http import require_POST
from django_ratelimit.decorators import ratelimit

# Internal imports - forms
from .forms import (
    MicroCredentialCommentForm, MicroCredentialReviewForm, LTIExternalToolForm,
    CoursePriceForm, CourseRatingForm, SosPostForm, MicroCredentialForm, AskOraForm,
    CourseForm, CourseRerunForm, PartnerForm, PartnerFormUpdate, CourseInstructorForm,
    SectionForm, GradeRangeForm, ProfilForm, InstructorForm, InstructorAddCoruseForm,
    TeamMemberForm, MatrialForm, QuestionForm, ChoiceFormSet, AssessmentForm
)

# Internal imports - utils
from .utils import user_has_passed_course, check_for_blacklisted_keywords, is_suspicious

# Internal imports - models
from .models import (
    LTIPlatform, PlatformKey, LastAccessCourse, UserActivityLog, MicroClaim, CourseViewIP,
    CourseViewLog, UserMicroCredential, MicroCredentialComment, MicroCredentialReview,
    UserMicroProgress, SearchHistory, Certificate, LTIExternalTool, Course, CourseRating,
    Like, SosPost, Hashtag, UserProfile, MicroCredentialEnrollment, MicroCredential,
    AskOra, PeerReview, AssessmentScore, Submission, CourseStatus, AssessmentSession,
    CourseComment, Comment, Choice, Score, CoursePrice, AssessmentRead, QuestionAnswer,
    Enrollment, PricingType, Partner, CourseProgress, MaterialRead, GradeRange, Category,
    Section, Instructor, TeamMember, Material, Question, Assessment
)

# Project-level apps
from authentication.models import CustomUser, Universiti
from blog.models import BlogPost
from licensing.models import License
from payments.models import Payment


logger = logging.getLogger(__name__)
User = CustomUser

# === NONCE ===
def generate_nonce(request):
    nonce = uuid.uuid4().hex
    request.session['lti_nonce'] = nonce
    request.session['lti_nonce_timestamp'] = datetime.now(timezone.utc).timestamp()
    logger.debug("[NONCE] Generated nonce: %s, timestamp: %s", nonce, request.session['lti_nonce_timestamp'])
    return nonce

def validate_nonce(request, nonce):
    stored = request.session.get('lti_nonce')
    ts = request.session.get('lti_nonce_timestamp')
    logger.debug("[NONCE] Validating nonce: %s, stored: %s, timestamp: %s", nonce, stored, ts)
    if stored != nonce or not ts:
        logger.error("[NONCE] Invalid nonce: stored=%s, received=%s, timestamp=%s", stored, nonce, ts)
        return False
    now = datetime.now(timezone.utc).timestamp()
    valid = (now - ts) <= 300
    logger.debug("[NONCE] Nonce validation result: %s", valid)
    return valid


# === 1. LMS → TOOL ===
@login_required
def lti_login_initiation(request, tool_id):
    try:
        tool = get_object_or_404(LTIExternalTool, id=tool_id)
        platform = tool.platform
        launch_url = request.build_absolute_uri(reverse("courses:lti_launch"))
        params = {
            "iss": settings.LTI_ISSUER,
            "login_hint": str(request.user.id),
            "target_link_uri": launch_url,
            "redirect_uri": launch_url,
            "client_id": platform.client_id,
            "lti_message_hint": str(tool.id),
        }
        logger.debug("[LTI INIT] Tool ID: %s, Platform: %s, Login URL: %s", tool_id, platform.name, platform.login_url)
        logger.debug("[LTI INIT] Parameters: %s", params)
        # Perbaiki encoding manual
        encoded_params = "&".join(f"{quote(k)}={quote(str(v))}" for k, v in params.items())
        logger.debug("[LTI INIT] Encoded parameters: %s", encoded_params)
        login_url = f"{platform.login_url}?{encoded_params}"
        logger.info("[LTI INIT] Redirecting to: %s", login_url)
        return redirect(login_url)
    except Exception as e:
        logger.exception("[LTI INIT] Error in lti_login_initiation: %s", str(e))
        return HttpResponseBadRequest(f"Error initiating LTI login: {str(e)}")


# === 2. TOOL → LMS ===
@csrf_exempt
def lti_tool_login_handler(request):
    try:
        logger.debug("[LTI LOGIN HANDLER] Query Params: %s", request.GET.dict())
        iss = request.GET.get("iss")
        login_hint = request.GET.get("login_hint")
        target_link_uri = request.GET.get("target_link_uri")
        client_id = request.GET.get("client_id")
        received_redirect_uri = request.GET.get("redirect_uri")
        lti_message_hint = request.GET.get("lti_message_hint")

        # Jika iss atau target_link_uri hilang, coba ambil dari LTIPlatform
        if not iss or not target_link_uri or not client_id:
            platform = LTIPlatform.objects.filter(client_id=client_id).first()
            if not platform:
                logger.error("[LTI LOGIN HANDLER] No platform found for client_id: %s", client_id)
                return HttpResponseBadRequest(f"No platform found for client_id: {client_id}")
            iss = iss or platform.issuer
            target_link_uri = target_link_uri or request.build_absolute_uri(reverse("courses:lti_launch"))
        
        # Paksa redirect_uri ke nilai yang benar
        correct_redirect_uri = request.build_absolute_uri(reverse("courses:lti_launch"))
        if received_redirect_uri and received_redirect_uri != correct_redirect_uri:
            logger.warning("[LTI LOGIN HANDLER] Incorrect redirect_uri received: %s, using correct redirect_uri: %s",
                           received_redirect_uri, correct_redirect_uri)
        
        if not all([iss, login_hint, target_link_uri, client_id]):
            logger.error("[LTI LOGIN HANDLER] Missing required parameters: iss=%s, login_hint=%s, target_link_uri=%s, client_id=%s",
                         iss, login_hint, target_link_uri, client_id)
            return HttpResponseBadRequest(f"Missing required parameters. Got: iss={iss}, login_hint={login_hint}, target_link_uri={target_link_uri}, client_id={client_id}")
        
        nonce = generate_nonce(request)
        state = uuid.uuid4().hex
        auth_params = {
            "scope": "openid",
            "response_type": "id_token",
            "client_id": client_id,
            "redirect_uri": correct_redirect_uri,
            "login_hint": login_hint,
            "state": state,
            "response_mode": "form_post",
            "nonce": nonce,
            "prompt": "none",
            "lti_message_hint": lti_message_hint,
        }
        logger.debug("[LTI LOGIN HANDLER] Auth parameters: %s", auth_params)
        # Perbaiki encoding manual
        encoded_auth_params = "&".join(f"{quote(k)}={quote(str(v))}" for k, v in auth_params.items())
        authorize_url = f"{iss}/authorize?{encoded_auth_params}"
        logger.debug("[LTI LOGIN HANDLER] Redirecting to: %s", authorize_url)
        return redirect(authorize_url)
    except Exception as e:
        logger.exception("[LTI LOGIN HANDLER] Error in lti_tool_login_handler: %s", str(e))
        return HttpResponseBadRequest(f"Error in LTI login handler: {str(e)}")
# === 3. Launch Endpoint ===
@csrf_exempt
def lti_launch(request):
    try:
        logger.debug("[LTI LAUNCH] Received request: method=%s, POST=%s", request.method, request.POST)
        if request.method != "POST":
            logger.error("[LTI LAUNCH] Invalid method: %s", request.method)
            return HttpResponseBadRequest("Invalid method")

        id_token = request.POST.get("id_token")
        if not id_token:
            logger.error("[LTI LAUNCH] Missing id_token")
            return HttpResponseBadRequest("Missing id_token")

        logger.debug("[LTI LAUNCH] Received id_token: %s", id_token)
        header = jwt.get_unverified_header(id_token)
        kid = header.get("kid")
        logger.debug("[LTI LAUNCH] JWT header: %s, kid: %s", header, kid)

        claims = jwt.decode(id_token, options={"verify_signature": False})
        logger.debug("[LTI LAUNCH] Unverified claims: %s", claims)
        iss = claims.get("iss")
        aud = claims.get("aud")
        nonce = claims.get("nonce")
        sub = claims.get("sub")
        name = claims.get("name")
        email = claims.get("email") or f"lti-{sub}@tool.com"

        if not validate_nonce(request, nonce):
            logger.error("[LTI LAUNCH] Invalid or expired nonce: %s", nonce)
            return HttpResponseBadRequest("Invalid or expired nonce")

        jwks_url = f"{iss}/.well-known/jwks.json"
        logger.debug("[LTI LAUNCH] Fetching JWKS from: %s", jwks_url)
        res = requests.get(jwks_url)
        if res.status_code != 200:
            logger.error("[LTI LAUNCH] Failed to fetch JWKS: status=%s, response=%s", res.status_code, res.text)
            return HttpResponseBadRequest("Failed to fetch JWKS")

        jwks = res.json().get("keys", [])
        public_key = None
        for key in jwks:
            if key.get("kid") == kid:
                public_key = RSAAlgorithm.from_jwk(json.dumps(key))
                logger.debug("[LTI LAUNCH] Found matching public key for kid: %s", kid)
                break

        if not public_key:
            logger.error("[LTI LAUNCH] No matching key for kid: %s", kid)
            return HttpResponseBadRequest("No matching key")

        payload = jwt.decode(
            id_token,
            public_key,
            algorithms=["RS256"],
            audience=aud,
            issuer=iss
        )
        logger.debug("[LTI LAUNCH] Verified payload: %s", payload)

        user, created = User.objects.get_or_create(
            username=email,
            defaults={"email": email, "full_name": name or "LTI User", "is_active": True}
        )
        logger.debug("[LTI LAUNCH] User: %s, created: %s", user.username, created)
        login(request, user)
        logger.info("[LTI LAUNCH] Redirecting to learner dashboard")
        return redirect("learner:dashboard")
    except Exception as e:
        logger.exception("[LTI LAUNCH] Error in lti_launch: %s", str(e))
        return HttpResponseBadRequest(f"LTI launch failed: {str(e)}")
# === 4. Token Endpoint (optional) ===
@csrf_exempt
def lti_token_endpoint(request):
    try:
        logger.debug("[LTI TOKEN] Received request: method=%s, POST=%s, headers=%s", 
                     request.method, request.POST, request.headers)
        if request.method != "POST":
            logger.error("[LTI TOKEN] Invalid method: %s", request.method)
            return HttpResponseBadRequest("Invalid method")

        auth = request.headers.get("Authorization", "")
        if not auth.startswith("Basic "):
            logger.error("[LTI TOKEN] Missing or invalid Authorization header: %s", auth)
            return HttpResponseForbidden("Missing Authorization header")

        try:
            decoded = base64.b64decode(auth.split(" ")[1]).decode()
            client_id, _ = decoded.split(":")
            logger.debug("[LTI TOKEN] Decoded client_id: %s", client_id)
        except Exception as e:
            logger.error("[LTI TOKEN] Invalid credentials: %s", str(e))
            return HttpResponseForbidden("Invalid credentials")

        platform = LTIPlatform.objects.filter(client_id=client_id).first()
        key = PlatformKey.objects.filter(partner__name=platform.name).first()

        if not key or not key.private_key:
            logger.error("[LTI TOKEN] No private key for platform: %s", client_id)
            return JsonResponse({"error": "No private key"}, status=500)

        now = datetime.now(timezone.utc)
        token = {
            "iss": settings.LTI_ISSUER,
            "sub": client_id,
            "aud": client_id,
            "iat": int(now.timestamp()),
            "exp": int((now + timedelta(minutes=5)).timestamp()),
            "scope": request.POST.get("scope", ""),
        }
        logger.debug("[LTI TOKEN] Generating token: %s", token)
        jwt_token = jwt.encode(token, key.private_key, algorithm="RS256")
        logger.debug("[LTI TOKEN] Generated JWT token: %s", jwt_token)
        return JsonResponse({
            "access_token": jwt_token,
            "token_type": "bearer",
            "expires_in": 300,
            "scope": token["scope"],
        })
    except Exception as e:
        logger.exception("[LTI TOKEN] Error in lti_token_endpoint: %s", str(e))
        return JsonResponse({"error": f"Token endpoint failed: {str(e)}"}, status=500)

# === 5. JWKS ===
def jwks_public(request):
    try:
        key = PlatformKey.objects.first()
        if not key:
            logger.error("[JWKS] No platform key configured")
            raise Http404("No platform key")
        logger.debug("[JWKS] Returning public JWK: %s", key.public_jwk)
        return JsonResponse({"keys": [key.public_jwk]})
    except Exception as e:
        logger.exception("[JWKS] Error in jwks_public: %s", str(e))
        return JsonResponse({"error": f"JWKS endpoint failed: {str(e)}"}, status=500)

def openid_configuration(request):
    try:
        base = request.build_absolute_uri("/")[:-1]
        config = {
            "issuer": base,
            "authorization_endpoint": base + reverse("courses:lti_login"),
            "token_endpoint": base + reverse("courses:lti_token"),
            "jwks_uri": base + reverse("courses:jwks-public"),
            "response_types_supported": ["id_token"],
            "subject_types_supported": ["public"],
            "id_token_signing_alg_values_supported": ["RS256"],
        }
        logger.debug("[OPENID CONFIG] Returning configuration: %s", config)
        return JsonResponse(config)
    except Exception as e:
        logger.exception("[OPENID CONFIG] Error in openid_configuration: %s", str(e))
        return JsonResponse({"error": f"OpenID configuration failed: {str(e)}"}, status=500)




@login_required
def microcredential_report_view(request, microcredential_id):
    if not request.user.is_staff:
        raise PermissionDenied("You do not have permission to access this report.")

    micro = get_object_or_404(MicroCredential, id=microcredential_id)
    enrollments = MicroCredentialEnrollment.objects.filter(microcredential=micro)
    total_participants = enrollments.count()
    required_courses = micro.required_courses.all()

    participants_data = []
    for enrollment in enrollments:
        user = enrollment.user
        user_micro = UserMicroCredential.objects.filter(user=user, microcredential=micro).first()
        micro_claim = MicroClaim.objects.filter(user=user, microcredential=micro).first()
        completed = user_micro.completed if user_micro else False
        certificate_id = user_micro.certificate_id if user_micro else "N/A"
        issued_at = micro_claim.issued_at if micro_claim else None 

        country = user.country if user.country else "N/A"
        gender = user.gender if user.gender else "N/A"
        university = user.university.name if user.university else "N/A"
        full_name = f"{user.first_name} {user.last_name}".strip() or user.username

        course_progress = []
        total_user_score = Decimal(0)
        total_max_score = Decimal(0)
        all_courses_completed = True

        for course in required_courses:
            assessments = Assessment.objects.filter(section__courses=course)
            course_score = Decimal(0)
            course_max_score = Decimal(0)
            course_completed = True

            for assessment in assessments:
                score_value = Decimal(0)
                total_questions = assessment.questions.count()
                if total_questions > 0:
                    total_correct_answers = 0
                    answers_exist = False
                    for question in assessment.questions.all():
                        answers = QuestionAnswer.objects.filter(question=question, user=user)
                        if answers.exists():
                            answers_exist = True
                        total_correct_answers += answers.filter(choice__is_correct=True).count()
                    if not answers_exist:
                        course_completed = False
                    if total_questions > 0:
                        score_value = (Decimal(total_correct_answers) / Decimal(total_questions)) * Decimal(assessment.weight)
                else:
                    askora_submissions = Submission.objects.filter(askora__assessment=assessment, user=user)
                    if not askora_submissions.exists():
                        course_completed = False
                    else:
                        latest_submission = askora_submissions.order_by('-submitted_at').first()
                        assessment_score = AssessmentScore.objects.filter(submission=latest_submission).first()
                        if assessment_score:
                            score_value = Decimal(assessment_score.final_score)

                score_value = min(score_value, Decimal(assessment.weight))
                course_score += score_value
                course_max_score += assessment.weight

            course_score = course_score.quantize(Decimal('1'), rounding=ROUND_DOWN)
            course_max_score = course_max_score.quantize(Decimal('1'), rounding=ROUND_DOWN)
            min_score = Decimal(micro.get_min_score(course) or 0).quantize(Decimal('1'), rounding=ROUND_DOWN)
            course_passed = course_completed and course_score >= min_score

            course_progress.append({
                'course_name': course.course_name,
                'user_score': course_score,
                'max_score': course_max_score,
                'min_score': min_score,
                'completed': course_completed,
                'passed': course_passed,
            })

            total_user_score += course_score
            total_max_score += course_max_score
            if not course_passed:
                all_courses_completed = False

        total_user_score = total_user_score.quantize(Decimal('1'), rounding=ROUND_DOWN)
        total_max_score = total_max_score.quantize(Decimal('1'), rounding=ROUND_DOWN)
        microcredential_passed = all_courses_completed and total_user_score >= Decimal(micro.min_total_score)

        # CEK APAKAH SUDAH KLAIM SERTIFIKAT
        micro_claim = MicroClaim.objects.filter(user=user, microcredential=micro).first()
        has_claimed = bool(micro_claim)
        certificate_claim_id = micro_claim.certificate_id if micro_claim else "N/A"
        claim_verified = micro_claim.verified if micro_claim else False
        claimed_at = micro_claim.claim_date if micro_claim else None

        participants_data.append({
            'full_name': full_name,
            'email': user.email,
            'country': country,
            'gender': gender,
            'university': university,
            'total_user_score': total_user_score,
            'total_max_score': total_max_score,
            'min_total_score': micro.min_total_score,
            'microcredential_passed': microcredential_passed,
            'completed': completed,
            'certificate_id': certificate_claim_id,
            'issued_at': issued_at,
            'claimed': has_claimed,
            'verified': claim_verified,
            'claimed_at': claimed_at,
            'course_progress': course_progress,
        })

    # PAGINATION
    per_page = 25
    paginator = Paginator(participants_data, per_page)
    page = request.GET.get('page')

    try:
        participants_page = paginator.page(page)
    except PageNotAnInteger:
        participants_page = paginator.page(1)
    except EmptyPage:
        participants_page = paginator.page(paginator.num_pages)

    context = {
        'report': {
            'microcredential_title': micro.title,
            'microcredential_id': micro.id,
            'total_participants': total_participants,
            'min_total_score': micro.min_total_score,
            'participants': participants_page,
        },
        'current_date': timezone.now().date(),
    }

    return render(request, 'micro/microcredential_report.html', context)


@login_required
def add_microcredential_review(request, microcredential_id):
    microcredential = get_object_or_404(MicroCredential, id=microcredential_id)

    # Validasi apakah user terdaftar dalam microcredential
    is_enrolled = MicroCredentialEnrollment.objects.filter(user=request.user, microcredential=microcredential).exists()
    if not is_enrolled:
        messages.error(request, "You must be enrolled in this MicroCredential to leave a review.")
        return redirect('courses:micro_detail', slug=microcredential.slug)

    # Hitung kelulusan seluruh kursus
    required_courses = microcredential.required_courses.all()
    total_user_score = Decimal(0)
    total_max_score = Decimal(0)
    all_courses_completed = True

    for course in required_courses:
        assessments = Assessment.objects.filter(section__courses=course)
        course_score = Decimal(0)
        course_completed = True

        for assessment in assessments:
            score_value = Decimal(0)
            total_questions = assessment.questions.count()

            if total_questions > 0:  # Multiple Choice
                total_correct_answers = 0
                answers_exist = False
                for question in assessment.questions.all():
                    answers = QuestionAnswer.objects.filter(question=question, user=request.user)
                    if answers.exists():
                        answers_exist = True
                    total_correct_answers += answers.filter(choice__is_correct=True).count()
                if not answers_exist:
                    course_completed = False
                if total_questions > 0:
                    score_value = (Decimal(total_correct_answers) / Decimal(total_questions)) * Decimal(assessment.weight)
            else:  # AskOra
                submissions = Submission.objects.filter(askora__assessment=assessment, user=request.user)
                if not submissions.exists():
                    course_completed = False
                else:
                    latest = submissions.order_by('-submitted_at').first()
                    score_obj = AssessmentScore.objects.filter(submission=latest).first()
                    if score_obj:
                        score_value = Decimal(score_obj.final_score)

            score_value = min(score_value, Decimal(assessment.weight))
            course_score += score_value

        min_score = Decimal(microcredential.get_min_score(course))
        course_passed = course_completed and course_score >= min_score
        if not course_passed:
            all_courses_completed = False

        total_user_score += course_score
        total_max_score += sum(a.weight for a in assessments)

    microcredential_passed = all_courses_completed and total_user_score >= Decimal(microcredential.min_total_score)

    if not microcredential_passed:
        messages.error(request, "You must complete and pass all required courses to leave a review.")
        return redirect('courses:micro_detail', slug=microcredential.slug)

    # Form submission
    if request.method == 'POST':
        form = MicroCredentialReviewForm(request.POST)
        if form.is_valid():
            review, created = MicroCredentialReview.objects.get_or_create(
                user=request.user,
                microcredential=microcredential
            )
            review.rating = form.cleaned_data['rating']
            review.review_text = form.cleaned_data['review_text']
            review.save()
            if created:
                messages.success(request, "Your review has been submitted.")
            else:
                messages.success(request, "Your review has been updated.")
            return redirect('courses:micro_detail', id=microcredential.id, slug=microcredential.slug)
    else:
        existing_review = MicroCredentialReview.objects.filter(user=request.user, microcredential=microcredential).first()
        if existing_review:
            messages.info(request, "You're editing your previous review.")
            form = MicroCredentialReviewForm(instance=existing_review)
        else:
            form = MicroCredentialReviewForm()

    return render(request, 'micro/add_review.html', {
        'form': form,
        'microcredential': microcredential
    })


def self_course(request, username, id, slug):
    if not request.user.is_authenticated:
        return redirect("/login/?next=%s" % request.path)

    # Ambil course berdasarkan id dan slug
    course = get_object_or_404(Course, id=id, slug=slug)

    # Pastikan user yang mengakses adalah user yang benar
    if request.user.username != username:
        return redirect('authentication:course_list')

    # Cek apakah user adalah instruktur dari course ini
    is_instructor = course.instructor == request.user

   
    
    course_name = course.course_name

    # Ambil section, material, assessment, dan askora
    sections = Section.objects.filter(courses=course).prefetch_related(
        Prefetch('materials', queryset=Material.objects.all()),
        Prefetch('assessments', queryset=Assessment.objects.all().prefetch_related(
            Prefetch('questions', queryset=Question.objects.all().prefetch_related(
                Prefetch('choices', queryset=Choice.objects.all())
            )),
            Prefetch('ask_oras', queryset=AskOra.objects.all())
        ))
    )

    # Buat daftar konten gabungan dengan informasi section
    combined_content = []
    for section in sections:
        for material in section.materials.all():
            combined_content.append(('material', material, section))
        for assessment in section.assessments.all():
            combined_content.append(('assessment', assessment, section))

    total_content = len(combined_content)

    # Ambil ID konten saat ini dari parameter URL
    material_id = request.GET.get('material_id')
    assessment_id = request.GET.get('assessment_id')

    # Tentukan current_content
    current_content = None
    if not material_id and not assessment_id:
        current_content = combined_content[0] if combined_content else None
    elif material_id:
        material = get_object_or_404(Material, id=material_id)
        current_content = ('material', material, next((s for s in sections if material in s.materials.all()), None))
    elif assessment_id:
        assessment = get_object_or_404(Assessment, id=assessment_id)
        current_content = ('assessment', assessment, next((s for s in sections if assessment in s.assessments.all()), None))

    # Handle comments and pagination based on current_content
    comments = None
    page_comments = []
    if current_content:
        if current_content[0] == 'material':
            material = current_content[1]
            comments = Comment.objects.filter(material=material, parent=None).order_by('-created_at')
        elif current_content[0] == 'assessment':
            section = current_content[2]
            comments = Comment.objects.filter(material__section=section, parent=None).order_by('-created_at')

        if comments:
            paginator = Paginator(comments, 5)
            page_number = request.GET.get('page')
            page_comments = paginator.get_page(page_number)

    # Cek status assessment untuk peserta
    is_started = False
    is_expired = False
    remaining_time = 0

    # Jika user adalah instruktur, abaikan cek session assessment
    if not is_instructor:
        session = AssessmentSession.objects.filter(user=request.user, assessment=assessment).first()
        if session:
            is_started = True
            remaining_time = int((session.end_time - timezone.now()).total_seconds())
            if remaining_time <= 0:
                is_expired = True
                remaining_time = 0
        else:
            if assessment.duration_in_minutes == 0:
                is_started = True
                remaining_time = 0
            else:
                is_started = False

    # Tentukan indeks konten saat ini
    current_index = -1
    if current_content:
        for i, content in enumerate(combined_content):
            if (content[0] == current_content[0] and 
                content[1].id == current_content[1].id and 
                content[2].id == current_content[2].id):
                current_index = i
                break
        if current_index == -1:
            print("Warning: Current content not found in combined_content, defaulting to first content")
            current_index = 0
            current_content = combined_content[0] if combined_content else None

    # Tentukan konten sebelumnya dan berikutnya
    previous_content = combined_content[current_index - 1] if current_index > 0 else None
    next_content = combined_content[current_index + 1] if current_index < len(combined_content) - 1 and current_index != -1 else None
    is_last_content = next_content is None

    # Buat URL untuk navigasi
    previous_url = "#" if not previous_content else f"?{previous_content[0]}_id={previous_content[1].id}"
    next_url = "#" if not next_content else f"?{next_content[0]}_id={next_content[1].id}"

    # Skip progres dan sertifikat untuk instruktur
    if not is_instructor:
        # Save track records
        if current_content:
            if current_content[0] == 'material':
                material = current_content[1]
                if not MaterialRead.objects.filter(user=request.user, material=material).exists():
                    MaterialRead.objects.create(user=request.user, material=material)
            elif current_content[0] == 'assessment':
                assessment = current_content[1]
                if not AssessmentRead.objects.filter(user=request.user, assessment=assessment).exists():
                    AssessmentRead.objects.create(user=request.user, assessment=assessment)

        # Lacak kemajuan pengguna
        user_progress, created = CourseProgress.objects.get_or_create(user=request.user, course=course)
        if current_content and (current_index + 1) > user_progress.progress_percentage / 100 * total_content:
            user_progress.progress_percentage = (current_index + 1) / total_content * 100
            user_progress.save()

    # Ambil skor terakhir dari pengguna (untuk peserta)
    if not is_instructor:
        score = Score.objects.filter(user=request.user.username, course=course).order_by('-date').first()
        user_grade = 'Fail'
        if score:
            score_percentage = (score.score / score.total_questions) * 100
            user_grade = calculate_grade(score_percentage, course)

    # Proses assessment untuk instruktur dan peserta
    assessments = Assessment.objects.filter(section__courses=course)
    assessment_scores = []
    total_max_score = 0
    total_score = 0  # Inisialisasi total_score
    all_assessments_submitted = True

    grade_range = GradeRange.objects.filter(course=course).all()
    if grade_range:
        passing_threshold = grade_range.filter(name='Pass').first().min_grade
        max_grade = grade_range.filter(name='Pass').first().max_grade
    else:
        return render(request, 'error_template.html', {'message': 'Grade range not found for this course.'})

    # Proses skor untuk setiap assessment
    for assessment in assessments:
        score_value = Decimal(0)
        total_correct_answers = 0
        total_questions = assessment.questions.count()
        if total_questions > 0:
            answers_exist = False
            for question in assessment.questions.all():
                answers = QuestionAnswer.objects.filter(question=question, user=request.user)
                if answers.exists():
                    answers_exist = True
                total_correct_answers += answers.filter(choice__is_correct=True).count()
            if not answers_exist:
                all_assessments_submitted = False
            if total_questions > 0:
                score_value = (Decimal(total_correct_answers) / Decimal(total_questions)) * Decimal(assessment.weight)
        else:  # Assessment adalah AskOra
            askora_submissions = Submission.objects.filter(
                askora__assessment=assessment,
                user=request.user
            )
            if not askora_submissions.exists():
                all_assessments_submitted = False
            else:
                latest_submission = askora_submissions.order_by('-submitted_at').first()
                assessment_score = AssessmentScore.objects.filter(submission=latest_submission).first()
                if assessment_score:
                    score_value = Decimal(assessment_score.final_score)

        score_value = min(score_value, Decimal(assessment.weight))
        assessment_scores.append({
            'assessment': assessment,
            'score': score_value,
            'weight': assessment.weight
        })
        total_max_score += assessment.weight

    # Jangan lupa untuk merender halaman dengan context
    context = {
        'course': course,
        'course_name': course_name,
        'sections': sections,
        'current_content': current_content,
        'previous_url': previous_url,
        'next_url': next_url,
        'course_progress': user_progress.progress_percentage if not is_instructor else None,
        'user_grade': user_grade if not is_instructor else None,
        'assessment_results': assessment_scores,
        'total_score': total_score,
        'overall_percentage': (total_score / total_max_score) * 100 if total_max_score > 0 else 0,
        'total_weight': total_max_score,
        'status': 'Pass' if total_score >= passing_threshold else 'Fail',
        'is_last_content': is_last_content,
        'comments': page_comments,
        'material': current_content[1] if current_content and current_content[0] == 'material' else None,
        'assessment': current_content[1] if current_content and current_content[0] == 'assessment' else None,
    }

    return render(request, 'instructor/self_course.html', context)





logger = logging.getLogger(__name__)

@login_required
def launch_lti(request, idcourse, idsection, idlti, id_lti_tool):
    user = request.user
    logger.info(f"User {user.get_full_name()} (ID: {user.id}) attempting to launch LTI.")

    try:
        course = get_object_or_404(Course, id=idcourse)
        section = get_object_or_404(Section, id=idsection, courses=course)
        assessment = get_object_or_404(Assessment, id=idlti, section=section)
        lti_tool = get_object_or_404(LTIExternalTool, id=id_lti_tool, assessment=assessment)

        is_instructor = user.is_superuser or user == course.instructor.user or user == course.org_partner.user
        is_learner = course.enrollments.filter(user=user).exists()
        if not (is_instructor or is_learner):
            messages.error(request, "You do not have permission to access this LTI tool.")
            logger.error(f"User {user.id} denied access to LTI tool {lti_tool.id}.")
            return redirect('authentication:home')

        if not lti_tool.launch_url or not lti_tool.consumer_key or not lti_tool.shared_secret:
            messages.error(request, "Invalid LTI tool configuration.")
            logger.error(f"LTI tool {lti_tool.id} has missing or invalid configuration: "
                         f"launch_url={lti_tool.launch_url}, "
                         f"consumer_key={lti_tool.consumer_key}, "
                         f"shared_secret={'[REDACTED]' if lti_tool.shared_secret else 'None'}")
            return redirect('authentication:home')

        roles = "Instructor" if is_instructor else "Learner"
        launch_url = lti_tool.launch_url.strip()

        # Build LTI parameters (LTI 1.1 style)
        lti_params = {
            'lti_message_type': 'basic-lti-launch-request',
            'lti_version': 'LTI-1p0',
            'resource_link_id': f"{course.id}-{section.id}-{assessment.id}-{lti_tool.id}",
            'resource_link_title': assessment.name,
            'user_id': str(user.id),
            'roles': roles,
            'oauth_consumer_key': lti_tool.consumer_key,
            'oauth_signature_method': 'HMAC-SHA1',
            'oauth_timestamp': str(int(datetime.now(pytz.UTC).timestamp())),
            'oauth_nonce': str(uuid.uuid4()),
            'oauth_version': '1.0',
            'lis_person_name_full': user.get_full_name(),
            'lis_person_name_given': user.first_name,
            'lis_person_name_family': user.last_name,
            'lis_person_contact_email_primary': user.email,
            'lis_person_sourcedid': str(user.id),
            'context_id': str(course.id),
            'context_title': course.course_name,
            'context_label': course.course_name[:10],
            'launch_presentation_locale': 'id-ID',
            'launch_presentation_document_target': 'iframe',
        }

        # Tambahkan custom param jika ada
        if lti_tool.custom_params:
            lti_params.update({k: str(v) for k, v in lti_tool.custom_params.items()})
            logger.debug(f"Added custom params: {lti_tool.custom_params}")

        # Hitung signature
        params_to_sign = lti_params.copy()
        sorted_params = sorted(params_to_sign.items())
        encoded_params = urllib.parse.urlencode(sorted_params, quote_via=urllib.parse.quote)

        method = 'POST'
        base_string = f"{method}&{urllib.parse.quote(launch_url, safe='')}&{urllib.parse.quote(encoded_params, safe='')}"
        signing_key = f"{urllib.parse.quote(lti_tool.shared_secret, safe='')}&".encode('utf-8')

        logger.debug(f"Base string: {base_string}")
        logger.debug(f"Signing key: {signing_key.decode()}")

        hashed = hmac.new(signing_key, base_string.encode('utf-8'), hashlib.sha1)
        signature = base64.b64encode(hashed.digest()).decode('utf-8')
        lti_params['oauth_signature'] = signature

        logger.debug(f"Final signed LTI params: {lti_params}")

        return render(
            request,
            'courses/lti_launch.html',
            {
                'launch_url': launch_url,
                'lti_params': lti_params,
            }
        )

    except Exception as e:
        logger.exception(f"Error launching LTI tool {id_lti_tool}: {str(e)}")
        messages.error(request, "An error occurred while launching the LTI tool.")
        return redirect('authentication:home')









logger = logging.getLogger(__name__)

@login_required
def create_lti(request, idcourse, idsection, idlti):
    if request.user.is_superuser:
        course = get_object_or_404(Course, id=idcourse)
    elif request.user.is_partner:
        course = get_object_or_404(Course, id=idcourse, org_partner__user_id=request.user.id)
    elif request.user.is_instructor:
        course = get_object_or_404(Course, id=idcourse, instructor__user_id=request.user.id)
    else:
        messages.error(request, "Anda tidak memiliki izin untuk membuat alat LTI di kursus ini.")
        return redirect('courses:home')

    section = get_object_or_404(Section, id=idsection, courses=course)
    assessment = get_object_or_404(Assessment, id=idlti, section=section)

    if request.method == 'POST':
        form = LTIExternalToolForm(request.POST)
        if form.is_valid():
            lti_tool = form.save(commit=False)
            lti_tool.assessment = assessment
            
            # Generate random shared_secret if not provided
            lti_tool.shared_secret = ''.join(random.choices(string.ascii_letters + string.digits, k=32))  # 32-character random string
            
            lti_tool.save()
            messages.success(request, "Alat LTI berhasil ditambahkan!")
            return redirect('courses:view-question', idcourse=course.id, idsection=section.id, idassessment=assessment.id)
    else:
        form = LTIExternalToolForm()

    return render(request, 'courses/lti_tool_form.html', {
        'form': form,
        'course': course,
        'section': section,
        'assessment': assessment,
    })

@login_required
def edit_lti(request, idcourse, idsection, idlti, id_lti_tool):
    # Tentukan course berdasarkan peran pengguna
    if request.user.is_superuser:
        course = get_object_or_404(Course, id=idcourse)
    elif request.user.is_partner:
        course = get_object_or_404(Course, id=idcourse, org_partner__user_id=request.user.id)
    elif request.user.is_instructor:
        course = get_object_or_404(Course, id=idcourse, instructor__user_id=request.user.id)
    else:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': False, 'errors': 'Anda tidak memiliki izin untuk mengedit alat LTI di kursus ini.'}, status=403)
        messages.error(request, "Anda tidak memiliki izin untuk mengedit alat LTI di kursus ini.")
        return redirect('courses:home')

    # Pastikan section milik course
    section = get_object_or_404(Section, id=idsection, courses=course)

    # Pastikan assessment milik section
    assessment = get_object_or_404(Assessment, id=idlti, section=section)

    # Pastikan LTI tool milik assessment
    lti_tool = get_object_or_404(LTIExternalTool, id=id_lti_tool, assessment=assessment)

    # Menangani form
    if request.method == 'POST':
        form = LTIExternalToolForm(request.POST, instance=lti_tool)
        if form.is_valid():
            lti_tool = form.save(commit=False)
            lti_tool.assessment = assessment
            try:
                lti_tool.save()
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({
                        'success': True,
                        'message': 'Alat LTI berhasil diperbarui.',
                        'redirect_url': reverse('courses:view-question', kwargs={
                            'idcourse': course.id,
                            'idsection': section.id,
                            'idassessment': assessment.id
                        })
                    })
                messages.success(request, "Alat LTI berhasil diperbarui.")
                return redirect('courses:view-question', idcourse=course.id, idsection=section.id, idassessment=assessment.id)
            except ValueError as e:
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({'success': False, 'errors': str(e)}, status=400)
                messages.error(request, str(e))
        else:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'success': False, 'errors': form.errors}, status=400)
            messages.error(request, "Ada kesalahan dalam formulir. Silakan periksa kembali.")
    else:
        form = LTIExternalToolForm(instance=lti_tool)

    return render(request, 'courses/edit_lti_tool_form.html', {
        'course': course,
        'section': section,
        'assessment': assessment,
        'form': form,
    })


@login_required
def delete_lti(request, idcourse, idsection, idlti, id_lti_tool):
    # Tentukan course berdasarkan peran pengguna
    if request.user.is_superuser:
        course = get_object_or_404(Course, id=idcourse)
    elif request.user.is_partner:
        course = get_object_or_404(Course, id=idcourse, org_partner__user_id=request.user.id)
    elif request.user.is_instructor:
        course = get_object_or_404(Course, id=idcourse, instructor__user_id=request.user.id)
    else:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': False, 'errors': 'Anda tidak memiliki izin untuk menghapus alat LTI di kursus ini.'}, status=403)
        messages.error(request, "Anda tidak memiliki izin untuk menghapus alat LTI di kursus ini.")
        return redirect('courses:home')

    # Pastikan section milik course
    section = get_object_or_404(Section, id=idsection, courses=course)

    # Pastikan assessment milik section
    assessment = get_object_or_404(Assessment, id=idlti, section=section)

    # Pastikan LTI tool milik assessment
    lti_tool = get_object_or_404(LTIExternalTool, id=id_lti_tool, assessment=assessment)

    if request.method == 'POST':
        try:
            lti_tool.delete()
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': True,
                    'message': 'Alat LTI berhasil dihapus.',
                    'redirect_url': reverse('courses:view-question', kwargs={
                        'idcourse': course.id,
                        'idsection': section.id,
                        'idassessment': assessment.id
                    })
                })
            messages.success(request, "Alat LTI berhasil dihapus.")
            return redirect('courses:view-question', idcourse=course.id, idsection=section.id, idassessment=assessment.id)
        except Exception as e:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'success': False, 'errors': str(e)}, status=400)
            messages.error(request, f"Gagal menghapus alat LTI: {str(e)}")
            return redirect('courses:view-question', idcourse=course.id, idsection=section.id, idassessment=assessment.id)

    # Jika bukan POST, arahkan kembali ke halaman view-question
    return redirect('courses:view-question', idcourse=course.id, idsection=section.id, idassessment=assessment.id)

@csrf_exempt
@require_POST
def reorder_section(request):
    try:
        sections_data = json.loads(request.POST.get('sections', '[]'))
        subsections_data = json.loads(request.POST.get('subsections', '[]'))

        if not sections_data and not subsections_data:
            return JsonResponse({'status': 'error', 'message': 'No data provided for reordering'}, status=400)

        # Update sections
        for item in sections_data:
            section = Section.objects.get(id=item['id'])
            section.order = item['order']
            section.save()

        # Update subsections
        for item in subsections_data:
            subsection = Section.objects.get(id=item['id'])
            subsection.order = item['order']
            subsection.parent_id = item.get('parent_id') or None
            subsection.save()

        return JsonResponse({'status': 'success', 'message': 'Order updated successfully'})
    except Section.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'One or more sections/subsections not found'}, status=404)
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': f'Error: {str(e)}'}, status=500)
    
# views.py
@login_required
def course_list_enroll(request, id):
    

    # Mencari course berdasarkan ID
    course = get_object_or_404(Course, id=id)

    # Pemeriksaan keamanan: hanya admin atau pemilik course yang diizinkan
    if not (
        request.user.is_staff or 
        (course.instructor and course.instructor.user == request.user) or
        getattr(request.user, 'is_partner', False)
    ):


        
        messages.error(request, "Akses ditolak. Anda tidak memiliki izin untuk melihat data peserta kursus ini.")
        return redirect('authentication:home')

    # Mengambil daftar enrollments terkait kursus
    enrollments = course.enrollments.all()
    

    # Menyiapkan list untuk detail user dan statusnya
    enrollment_details = []

    # Pencarian berdasarkan email, first_name, atau last_name
    search_query = request.GET.get('search', '')
    if search_query:
        enrollments = enrollments.filter(
            Q(user__email__icontains=search_query) |
            Q(user__first_name__icontains=search_query) |
            Q(user__last_name__icontains=search_query)
        )

    # Ambil semua section dari course ini
    sections = course.sections.all()
    section_ids = sections.values_list('id', flat=True)

    # Ambil semua material dan assessment terkait section-section ini
    user_ids = enrollments.values_list('user_id', flat=True)
    
    # Ambil data MaterialRead untuk waktu terakhir akses material
    material_reads = MaterialRead.objects.filter(
        user_id__in=user_ids,
        material__section_id__in=section_ids
    ).order_by('-read_at')
    
    last_material_map = {}
    for mr in material_reads:
        key = (mr.user_id, mr.material_id)
        if key not in last_material_map:
            last_material_map[key] = mr.read_at

    # Ambil data AssessmentRead untuk waktu terakhir menyelesaikan assessment
    assessment_ids = []
    for section in sections:
        assessment_ids += list(section.assessments.values_list('id', flat=True))
    
    assessment_reads = AssessmentRead.objects.filter(
        user_id__in=user_ids,
        assessment_id__in=assessment_ids
    ).order_by('-completed_at')
    
    last_assessment_map = {}
    for ar in assessment_reads:
        key = (ar.user_id, ar.assessment_id)
        if key not in last_assessment_map:
            last_assessment_map[key] = ar.completed_at

    for enrollment in enrollments:
        user = enrollment.user

        # Ambil total skor dan status dari setiap kursus
        total_max_score = 0
        total_score = 0
        all_assessments_submitted = True

        # Ambil grade range untuk kursus tersebut
        grade_range = GradeRange.objects.filter(course=course).first()
        passing_threshold = grade_range.min_grade if grade_range else 0

        # Hitung skor dari asesmen
        assessments = Assessment.objects.filter(section__courses=course)
        if not assessments.exists():
            logger.warning('Tidak ada assessment untuk course %s, total_max_score = 0', course.course_name)

        for assessment in assessments:
            score_value = Decimal(0)
            total_correct_answers = 0
            total_questions = assessment.questions.count()

            if total_questions > 0:  # Multiple choice
                answers_exist = False
                for question in assessment.questions.all():
                    answers = QuestionAnswer.objects.filter(question=question, user=user)
                    if answers.exists():
                        answers_exist = True
                    total_correct_answers += answers.filter(choice__is_correct=True).count()
                if not answers_exist:
                    all_assessments_submitted = False
                if total_questions > 0:
                    score_value = (Decimal(total_correct_answers) / Decimal(total_questions)) * Decimal(assessment.weight)
            
            total_max_score += assessment.weight
            total_score += score_value

        # Hitung persentase skor
        overall_percentage = (total_score / total_max_score) * 100 if total_max_score > 0 else 0

        # Ambil progress dari CourseProgress
        course_progress = CourseProgress.objects.filter(user=user, course=course).first()
        progress_percentage = course_progress.progress_percentage if course_progress else 0

        # Tentukan status kelulusan
        status = "Fail"
        if progress_percentage == 100 and all_assessments_submitted and overall_percentage >= passing_threshold:
            status = "Pass"

        # Ambil waktu terakhir akses material dan assessment untuk user ini
        last_accessed_material = None
        last_completed_assessment = None
        
        for section in sections:
            for material in section.materials.all():
                time = last_material_map.get((user.id, material.id))
                if time and (not last_accessed_material or time > last_accessed_material):
                    last_accessed_material = time

            for assessment in section.assessments.all():
                time = last_assessment_map.get((user.id, assessment.id))
                if time and (not last_completed_assessment or time > last_completed_assessment):
                    last_completed_assessment = time

        # Tambahkan detail user ke daftar enrollment_details
        enrollment_details.append({
            'user': user,
            'email': user.email,
            'first_name': user.first_name,
            'last_name': user.last_name,
            'last_login': user.last_login,
            'gender': getattr(user, 'gender', 'N/A'),
            'birth': getattr(user, 'birth', 'N/A'),
            'address': getattr(user, 'address', 'N/A'),
            'country': getattr(user, 'country', 'N/A'),
            'phone': getattr(user, 'phone', 'N/A'),
            'education': getattr(user, 'education', 'N/A'),
            'university': getattr(user, 'university', 'N/A'),
            'total_score': total_score,
            'total_max_score': total_max_score,
            'status': status,
            'progress_percentage': progress_percentage,
            'overall_percentage': overall_percentage,
            'last_accessed_material': last_accessed_material,
            'last_completed_assessment': last_completed_assessment,
        })

    if not enrollments.exists():
        logger.info('Tidak ada enrollment untuk course %s', course.course_name)

    # Pagination untuk hasil peserta
    paginator = Paginator(enrollment_details, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    # Cek apakah ada permintaan untuk mengunduh CSV
    if request.GET.get('download') == 'csv':
        logger.info('Mengunduh CSV untuk course %s', course.course_name)
        return download_enrollment_data(course, enrollment_details)

    # Menampilkan data dalam template
    return render(request, 'courses/course_enroll_list.html', {
        'course': course,
        'enrollments': page_obj,
        'search_query': search_query,
    })


def download_enrollment_data(course, enrollment_details):
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="{course.course_name}_enrollments.csv"'

    writer = csv.writer(response)
    writer.writerow([
        'Name', 'Email', 'Last Login', 'Gender', 'Birth', 'Address', 'Country',
        'Phone', 'Education', 'University', 'Score', 'Status', 'Progress', 'Overall %',
        'Last Accessed Material', 'Last Completed Assessment'
    ])

    for enrollment in enrollment_details:
        full_name = f"{enrollment.get('first_name', '')} {enrollment.get('last_name', '')}".strip()

        # Handle last login
        last_login = enrollment.get('last_login')
        last_login_str = last_login.strftime('%Y-%m-%d %H:%M:%S') if last_login else ''

        # Handle birth
        birth = enrollment.get('birth')
        birth_str = birth if birth and birth != 'N/A' else ''

        writer.writerow([
            full_name,
            enrollment.get('email', ''),
            last_login_str,
            enrollment.get('gender', ''),
            birth_str,
            enrollment.get('address', ''),
            enrollment.get('country', ''),
            enrollment.get('phone', ''),
            enrollment.get('education', ''),
            enrollment.get('university', ''),
            f"{enrollment.get('total_score', 0)} / {enrollment.get('total_max_score', 0)}",
            enrollment.get('status', ''),
            f"{enrollment.get('progress_percentage', 0)}%",
            f"{enrollment.get('overall_percentage', 0):.2f}%",
            enrollment['last_accessed_material'].strftime('%Y-%m-%d %H:%M:%S') if enrollment.get('last_accessed_material') else '',
            enrollment['last_completed_assessment'].strftime('%Y-%m-%d %H:%M:%S') if enrollment.get('last_completed_assessment') else '',
        ])

    return response


@login_required
def submit_rating(request, id, slug):
    course = get_object_or_404(Course, id=id, slug=slug)

    # Cek apakah user sudah lulus
    if not user_has_passed_course(request.user, course):
        messages.error(request, "Kamu hanya bisa memberi rating setelah lulus dari course ini.")
        return redirect('courses:course_lms_detail', id=course.id, slug=course.slug)

    # Cek apakah user sudah memberi rating sebelumnya
    if CourseRating.objects.filter(user=request.user, course=course).exists():
        messages.info(request, "Kamu sudah memberikan rating untuk course ini.")
        return redirect('courses:course_lms_detail', id=course.id, slug=course.slug)

    if request.method == 'POST':
        form = CourseRatingForm(request.POST)

        # Deteksi aktivitas mencurigakan
        if is_suspicious(request):
            messages.warning(request, "Aktivitas mencurigakan terdeteksi. Rating tidak disimpan.")
            return redirect('courses:course_lms_detail', id=course.id, slug=course.slug)

        if form.is_valid():
            rating = form.save(commit=False)
            comment = form.cleaned_data.get('comment')

            # Validasi isi komentar
            blacklisted = check_for_blacklisted_keywords(comment)
            if blacklisted:
                messages.warning(request, f"Komentarmu mengandung kata yang dilarang: '{blacklisted}'")
                return redirect('courses:course_lms_detail', id=course.id, slug=course.slug)

            # Cek spam (opsional)
            if hasattr(rating, 'is_spam') and rating.is_spam():
                messages.warning(request, "Terlalu sering mengirim rating. Coba lagi nanti.")
                return redirect('courses:course_lms_detail', id=course.id, slug=course.slug)

            rating.user = request.user
            rating.course = course
            rating.save()

            messages.success(request, "Terima kasih! Rating kamu sudah disimpan.")
            return redirect('courses:course_lms_detail', id=course.id, slug=course.slug)
    else:
        form = CourseRatingForm()

    return render(request, 'home/submit_rating.html', {'form': form, 'course': course})

@ratelimit(key='ip', rate='100/h')
def category_course_list(request, slug):
    # Mengambil objek Category berdasarkan slug
    category = get_object_or_404(Category, slug=slug)

    # Mendapatkan status 'published'
    published_status = CourseStatus.objects.filter(status='published').first()
    if not published_status:
        return HttpResponseNotFound("Status 'published' tidak ditemukan")

    # Ambil courses yang terkait dengan kategori tersebut dan status 'published'
    courses = Course.objects.filter(
        category=category,
        status_course=published_status,
        end_enrol__gte=timezone.now()
    ).select_related(
        'category', 'instructor__user', 'org_partner'
    ).prefetch_related('enrollments')

    # Paginasi: menampilkan 10 kursus per halaman
    paginator = Paginator(courses, 10)
    page = request.GET.get('page')

    try:
        courses_paginated = paginator.page(page)
    except PageNotAnInteger:
        # Jika halaman yang diminta bukan angka, tampilkan halaman pertama
        courses_paginated = paginator.page(1)
    except EmptyPage:
        # Jika halaman lebih besar dari jumlah halaman, tampilkan halaman terakhir
        courses_paginated = paginator.page(paginator.num_pages)

    # Mengambil kategori yang terkait dengan kursus
    categories = Category.objects.filter(
        category_courses__status_course=published_status,
        category_courses__end_enrol__gte=timezone.now()
    ).annotate(course_count=Count('category_courses')).distinct()

    # Siapkan data untuk ditampilkan
    courses_data = []
    total_enrollments = 0

    for course in courses_paginated:
        review_qs = CourseRating.objects.filter(course=course)
        average_rating = round(review_qs.aggregate(avg=Avg('rating'))['avg'] or 0, 1)
        full_stars = int(average_rating)
        half_star = (average_rating % 1) >= 0.5
        empty_stars = 5 - full_stars - (1 if half_star else 0)

        num_enrollments = course.enrollments.count()
        total_enrollments += num_enrollments

        courses_data.append({
            'course_name': course.course_name,
            'course_id': course.id,
            'num_enrollments': num_enrollments,
            'course_slug': course.slug,
            'course_image': course.image.url if course.image else None,
            'instructor': course.instructor.user.get_full_name() if course.instructor else None,
            'instructor_username': course.instructor.user.username if course.instructor else None,
            'photo': course.instructor.user.photo.url if course.instructor and course.instructor.user.photo else None,
            'partner': course.org_partner.name if course.org_partner else None,
            'partner_kode': course.org_partner.name.kode if course.org_partner else None,
            'partner_photo': course.org_partner.logo.url if course.org_partner and course.org_partner.logo else None,
            'category': course.category.name if course.category else None,
            'language': course.get_language_display(),  # ← ini
            'average_rating': average_rating,
            'review_count': review_qs.count(),
            'full_star_range': range(full_stars),
            'half_star': half_star,
            'empty_star_range': range(empty_stars),
            'duration': course.hour,  # Assuming `duration` is in your model
        })

    context = {
        'category': category,
        'courses': courses_data,
        'page_obj': courses_paginated,
        'total_courses': courses.count(),
        'total_enrollments': total_enrollments,
        'total_pages': paginator.num_pages,
        'current_page': courses_paginated.number,
        'start_index': courses_paginated.start_index(),
        'end_index': courses_paginated.end_index(),
        'categories': list(categories.values('id', 'name', 'course_count')),
    }

    return render(request, 'courses/course_list.html', context)

@csrf_protect

def search_posts(request):
    if not request.user.is_authenticated:
        return redirect("/login/?next=%s" % request.path)
    
    user_agent = request.META.get('HTTP_USER_AGENT', '').lower()
    if 'bot' in user_agent or 'crawler' in user_agent:
        return HttpResponse(render_to_string('messages.html', {'message': "Akses diblokir. Terdeteksi bot!", 'type': 'error'}))

    user_profile, _ = UserProfile.objects.get_or_create(user=request.user)
    if user_profile.is_blocked():
        return render(request, 'blocked.html', {'until': user_profile.blocked_until})

    was_limited = getattr(request, 'limited', False)
    if was_limited:
        user_profile.blocked_until = timezone.now() + timedelta(days=1)
        user_profile.save()
        return HttpResponse(render_to_string('messages.html', {'message': "Diblokir 1 hari karena melanggar batas!", 'type': 'error'}))
    
    query = request.GET.get('q', '').strip()
    posts = SosPost.objects.filter(
        deleted=False,
        content__icontains=query
    ).select_related('user', 'parent').prefetch_related('replies').order_by('-created_at')[:10]
    
    for post in posts:
        post.liked = Like.objects.filter(user=request.user, post=post).exists()
        post.like_count = Like.objects.filter(post=post).count()
    
    html = ''
    for post in posts:
        if not post.parent:
            html += render_to_string('home/post_item.html', {'post': post}, request=request)
    
    return HttpResponse(html if html else '<p>No posts found for this search.</p>')

@csrf_protect
def posts_by_hashtag(request, hashtag):
    if not request.user.is_authenticated:
        return redirect("/login/?next=%s" % request.path)
    
    user_agent = request.META.get('HTTP_USER_AGENT', '').lower()
    if 'bot' in user_agent or 'crawler' in user_agent:
        return HttpResponse(render_to_string('messages.html', {'message': "Akses diblokir. Terdeteksi bot!", 'type': 'error'}))

    user_profile, _ = UserProfile.objects.get_or_create(user=request.user)
    if user_profile.is_blocked():
        return render(request, 'blocked.html', {'until': user_profile.blocked_until})

    was_limited = getattr(request, 'limited', False)
    if was_limited:
        user_profile.blocked_until = timezone.now() + timedelta(days=1)
        user_profile.save()
        return HttpResponse(render_to_string('messages.html', {'message': "Diblokir 1 hari karena melanggar batas!", 'type': 'error'}))
    
    posts = SosPost.objects.filter(
        deleted=False,
        hashtags__name=hashtag.lower()
    ).select_related('user', 'parent').prefetch_related('replies').order_by('-created_at')[:10]
    
    for post in posts:
        post.liked = Like.objects.filter(user=request.user, post=post).exists()
        post.like_count = Like.objects.filter(post=post).count()
    
    html = ''
    for post in posts:
        if not post.parent:  # Hanya post utama
            html += render_to_string('home/post_item.html', {'post': post}, request=request)
    
    return HttpResponse(html if html else '<p>No posts found for this hashtag.</p>')

def create_and_list_sos_posts(request):
    if not request.user.is_authenticated:
        return redirect("/login/?next=%s" % request.path)
    
    user_profile, _ = UserProfile.objects.get_or_create(user=request.user)
    if user_profile.is_blocked():
        return render(request, 'blocked.html', {'until': user_profile.blocked_until})

    # Ambil post awal (misalnya 10 pertama)
    posts = SosPost.objects.filter(deleted=False).select_related('user', 'parent').prefetch_related('replies').order_by('-created_at')[:10]
    
    for post in posts:
        post.liked = Like.objects.filter(user=request.user, post=post).exists()
        post.like_count = Like.objects.filter(post=post).count()

    today = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
    trending = Hashtag.objects.filter(posts__created_at__gte=today).annotate(count=Count('posts')).order_by('-count')[:5]
    
    form = SosPostForm()
    context = {
        'form': form,
        'posts': posts,
        'trending': trending,
        'default_photo': '/media/profile_pics/hasbusiness-icon.png'
    }
    return render(request, 'home/sosial.html', context)

def load_more_posts(request):
    if not request.user.is_authenticated:
        return redirect("/login/?next=%s" % request.path)
    
    user_agent = request.META.get('HTTP_USER_AGENT', '').lower()
    if 'bot' in user_agent or 'crawler' in user_agent:
        return HttpResponse(render_to_string('messages.html', {'message': "Akses diblokir. Terdeteksi bot!", 'type': 'error'}))

    user_profile, _ = UserProfile.objects.get_or_create(user=request.user)
    if user_profile.is_blocked():
        return render(request, 'blocked.html', {'until': user_profile.blocked_until})

    was_limited = getattr(request, 'limited', False)
    if was_limited:
        user_profile.blocked_until = timezone.now() + timedelta(days=1)
        user_profile.save()
        return HttpResponse(render_to_string('messages.html', {'message': "Diblokir 1 hari karena melanggar batas!", 'type': 'error'}))
    
    if request.method == 'GET':
        offset = int(request.GET.get('offset', 0))
        hashtag = request.GET.get('hashtag', None)
        query = request.GET.get('q', None)
        limit = 10
        
        qs = SosPost.objects.filter(deleted=False)
        if hashtag:
            qs = qs.filter(hashtags__name=hashtag.lower())
        if query:
            qs = qs.filter(content__icontains=query)
        
        posts = qs.select_related('user', 'parent').prefetch_related('replies').order_by('-created_at')[offset:offset + limit]
        
        html = ''
        for post in posts:
            if not post.parent:
                html += render_to_string('home/post_item.html', {'post': post}, request=request)
        
        return HttpResponse(html if html else '<p>No more posts to load.</p>')
    return HttpResponse(status=400)

@csrf_protect
@require_POST
def create_post(request):
    if not request.user.is_authenticated:
        return redirect("/login/?next=%s" % request.path)

    user_agent = request.META.get('HTTP_USER_AGENT', '').lower()
    if 'bot' in user_agent or 'crawler' in user_agent:
        return HttpResponse(render_to_string('messages.html', {'message': "Akses diblokir. Terdeteksi bot!", 'type': 'error'}))

    user_profile, _ = UserProfile.objects.get_or_create(user=request.user)
    if user_profile.is_blocked():
        return render(request, 'blocked.html', {'until': user_profile.blocked_until})

    was_limited = getattr(request, 'limited', False)
    if was_limited:
        user_profile.blocked_until = timezone.now() + timedelta(days=1)
        user_profile.save()
        return HttpResponse(render_to_string('messages.html', {'message': "Diblokir 1 hari karena melanggar batas!", 'type': 'error'}))

    if request.method == 'POST':
        form = SosPostForm(request.POST)
        if form.is_valid():
            new_post = form.save(commit=False)
            new_post.user = request.user
            new_post.save()
            liked = Like.objects.filter(user=request.user, post=new_post).exists()
            like_count = Like.objects.filter(post=new_post).count()
            html = render_to_string('home/post_item.html', {
                'post': new_post,
                'liked': liked,
                'like_count': like_count,
                'request': request,
                'default_photo': '/media/profile_pics/hasbusiness-icon.png'
            })
            return HttpResponse(html, headers={'HX-Trigger': 'clearForm'})
        else:
            return HttpResponse(render_to_string('messages.html', {'message': "Form tidak valid!", 'type': 'error'}))
    return HttpResponse(status=400)
@csrf_protect
@require_POST
def like_post(request, post_id):
    if not request.user.is_authenticated:
        return redirect("/login/?next=%s" % request.path)

    if request.method == 'POST':
        try:
            post = get_object_or_404(SosPost, id=post_id)
            like = Like.objects.filter(user=request.user, post=post).first()

            if like:
                like.delete()
                liked = False
            else:
                Like.objects.create(user=request.user, post=post)
                liked = True

            like_count = Like.objects.filter(post=post).count()

            html = render_to_string('home/like_button.html', {
                'post': post,
                'liked': liked,
                'like_count': like_count
            })
            return HttpResponse(html)

        except SosPost.DoesNotExist:
            return HttpResponse(render_to_string('messages.html', {'message': "Postingan tidak ditemukan!", 'type': 'error'}))
        except Exception:
            return HttpResponse(status=500)

    return HttpResponse(status=400)

@csrf_protect
@require_POST

def reply_post(request, post_id):
    try:
        if not request.user.is_authenticated:
            return redirect("/login/?next=%s" % request.path)
        
        user_agent = request.META.get('HTTP_USER_AGENT', '').lower()
        if 'bot' in user_agent or 'crawler' in user_agent:
            return HttpResponse(render_to_string('messages.html', {'message': "Akses diblokir. Terdeteksi bot!", 'type': 'error'}))

        user_profile, _ = UserProfile.objects.get_or_create(user=request.user)
        if user_profile.is_blocked():
            return render(request, 'blocked.html', {'until': user_profile.blocked_until})

        was_limited = getattr(request, 'limited', False)
        if was_limited:
            user_profile.blocked_until = timezone.now() + timedelta(days=1)
            user_profile.save()
            return HttpResponse(render_to_string('messages.html', {'message': "Diblokir 1 hari karena melanggar batas!", 'type': 'error'}))
        
        if request.method == 'POST':
            form = SosPostForm(request.POST)
            if form.is_valid():
                reply = form.save(commit=False)
                reply.user = request.user
                reply.parent = SosPost.objects.get(id=post_id)
                reply.save()
                reply.liked = Like.objects.filter(user=request.user, post=reply).exists()
                reply.like_count = Like.objects.filter(post=reply).count()
                html = render_to_string('home/post_item.html', {'post': reply})
                return HttpResponse(html, headers={'HX-Trigger': 'clearForm'})
            return HttpResponse(render_to_string('messages.html', {'message': "Form tidak valid!", 'type': 'error'}))
        return HttpResponse(status=400)
    except SosPost.DoesNotExist:
        return HttpResponse(render_to_string('messages.html', {'message': "Post tidak ditemukan!", 'type': 'error'}))
    except Exception:
        return HttpResponse(status=500)
    
def reply_form(request, post_id):
    try:
        post = SosPost.objects.get(id=post_id)
        html = render_to_string('home/reply_form.html', {'post_id': post_id})
        return HttpResponse(html)
    except SosPost.DoesNotExist:
        return HttpResponse(render_to_string('messages.html', {'message': "Post tidak ditemukan!", 'type': 'error'}))

def micro_detail(request, id, slug):
    # Ambil data MicroCredential
    microcredential = get_object_or_404(MicroCredential, id=id, slug=slug)

    # Mengecek apakah pengguna sudah terdaftar dalam microcredential
    is_enrolled = False
    if request.user.is_authenticated:
        is_enrolled = MicroCredentialEnrollment.objects.filter(user=request.user, microcredential=microcredential).exists()

    # Ambil semua review
    reviews = microcredential.reviews.select_related('user').all().order_by('-created_at')

    # Paginasi: menampilkan 10 review per halaman
    paginator_reviews = Paginator(reviews, 10)  # 10 review per halaman
    page_number_reviews = request.GET.get('page')  # ambil nomor halaman dari URL
    page_obj_reviews = paginator_reviews.get_page(page_number_reviews)

    # Hitung rating rata-rata dan jumlah review
    rating_summary = reviews.aggregate(
        average_rating=Avg('rating'),
        total_reviews=Count('id')
    )


    # Ambil semua review untuk microcredential ini
    reviews = microcredential.reviews.all().order_by('-created_at')

    # Hitung rating rata-rata dan jumlah review
    rating_summary = reviews.aggregate(
        average_rating=Avg('rating'),
        total_reviews=Count('id')
    )
    # Ambil komentar utama (parent) untuk microcredential ini
    comments = MicroCredentialComment.objects.filter(microcredential=microcredential, parent=None).order_by('-created_at')

    # Paginasi komentar utama
    paginator_comments = Paginator(comments, 10)  # 10 komentar per halaman
    page_number_comments = request.GET.get('page_comments')
    page_obj_comments = paginator_comments.get_page(page_number_comments)

    

    context = {
        'microcredential': microcredential,
        'page_obj_reviews': page_obj_reviews,  # Paginasi review
        'average_rating': rating_summary['average_rating'] or 0,
        'total_reviews': rating_summary['total_reviews'],
        'is_enrolled': is_enrolled,  # Menambahkan status enrollment ke context

        # Menambahkan komentar ke context
        'page_obj_comments': page_obj_comments,  # Paginasi komentar
       
    }

    return render(request, 'micro/micro_detail.html', context)


logger = logging.getLogger(__name__)

# Form untuk validasi input komentar
class CommentForm(forms.Form):
    content = forms.CharField(max_length=1000, min_length=1, strip=True)
    parent_id = forms.IntegerField(required=False)
    honeypot = forms.CharField(required=False, widget=forms.HiddenInput)  # Honeypot untuk bot detection

    def clean_content(self):
        content = self.cleaned_data['content']
        # Sanitasi HTML menggunakan bleach
        cleaned_content = bleach.clean(content, tags=['p', 'br', 'strong', 'em'], strip=True)
        if len(cleaned_content.strip()) == 0:
            raise ValidationError("Comment cannot be empty after sanitization.")
        return cleaned_content

    def clean_honeypot(self):
        honeypot = self.cleaned_data['honeypot']
        if honeypot:
            raise ValidationError("Suspicious activity detected.")
        return honeypot

# Fungsi untuk mendeteksi aktivitas mencurigakan (bot detection)
def is_suspicious(request):
    user_agent = request.META.get('HTTP_USER_AGENT', '').lower()
    # Contoh pemeriksaan sederhana: User-Agent kosong atau mencurigakan
    if not user_agent or 'bot' in user_agent or 'crawler' in user_agent:
        logger.warning("Suspicious request detected: Invalid User-Agent", extra={'user_agent': user_agent})
        return True
    # Periksa honeypot melalui form
    return False

# Fungsi untuk memeriksa kata kunci terlarang
def contains_blacklisted_keywords(content):
    blacklist = ['<script>', 'javascript:', 'onerror', 'onload', 'viagra', 'casino']  # Sesuaikan
    content_lower = content.lower()
    for keyword in blacklist:
        if keyword in content_lower:
            logger.warning("Blacklisted keyword detected: %s", keyword)
            return True
    return False

# Fungsi untuk memeriksa spam berdasarkan cooldown
def is_spam(user, cache_key_prefix="comment_spam"):
    from django.core.cache import cache
    cache_key = f"{cache_key_prefix}:{user.id}"
    last_comment_time = cache.get(cache_key)
    if last_comment_time:
        cooldown_seconds = 30  # Cooldown 30 detik
        if (timezone.now() - last_comment_time).total_seconds() < cooldown_seconds:
            logger.warning("Spam detected: User %s posting too frequently", user.id)
            return True
    cache.set(cache_key, timezone.now(), timeout=60)  # Cache selama 60 detik
    return False

# Kunci untuk rate-limiting
def get_ratelimit_key(group, request):
    user_agent = request.META.get('HTTP_USER_AGENT', 'unknown')
    return f"{request.META.get('REMOTE_ADDR')}:{user_agent}"

@ratelimit(key=get_ratelimit_key, rate='10/m', block=True)  # Batasi 10 permintaan per menit
@csrf_protect
@require_POST  # Hanya izinkan POST
def add_comment_microcredential(request, microcredential_id, slug):
    try:
        # Mengecek apakah pengguna sudah login
        if not request.user.is_authenticated:
            return redirect(f"/login/?next={request.path}")

        # Ambil data MicroCredential
        microcredential = get_object_or_404(MicroCredential, id=microcredential_id, slug=slug)

        # Validasi form
        form = CommentForm(request.POST)
        if not form.is_valid():
            logger.warning("Invalid comment form submission: %s", form.errors)
            messages.warning(request, "Invalid comment data.")
            return redirect('courses:micro_detail', id=microcredential.id, slug=microcredential.slug)

        # Deteksi bot melalui is_suspicious
        if is_suspicious(request):
            logger.warning("Suspicious activity detected for user %s", request.user.id)
            messages.warning(request, "Suspicious activity detected. Comment not posted.")
            return redirect('courses:micro_detail', id=microcredential.id, slug=microcredential.slug)

        content = form.cleaned_data['content']
        parent_id = form.cleaned_data['parent_id']
        parent_comment = None

        # Validasi parent_id jika ada
        if parent_id:
            try:
                parent_comment = MicroCredentialComment.objects.get(id=parent_id, microcredential=microcredential)
            except MicroCredentialComment.DoesNotExist:
                logger.warning("Invalid parent comment ID: %s", parent_id)
                messages.warning(request, "Invalid parent comment.")
                return redirect('courses:micro_detail', id=microcredential.id, slug=microcredential.slug)

        # Periksa kata kunci terlarang
        if contains_blacklisted_keywords(content):
            messages.warning(request, "Your comment contains blacklisted content.")
            return redirect('courses:micro_detail', id=microcredential.id, slug=microcredential.slug)

        # Periksa spam
        if is_spam(request.user):
            messages.warning(request, "You are posting too frequently. Please wait a moment before posting again.")
            return redirect('courses:micro_detail', id=microcredential.id, slug=microcredential.slug)

        # Buat dan simpan komentar
        comment = MicroCredentialComment(
            user=request.user,
            content=content,
            microcredential=microcredential,
            parent=parent_comment
        )
        comment.save()

        messages.success(request, 'Your comment has been posted.')
        return redirect('courses:micro_detail', id=microcredential.id, slug=microcredential.slug)

    except DatabaseError:
        logger.exception("Database error in add_comment_microcredential")
        messages.error(request, "A server error occurred. Please try again later.")
        return redirect('courses:micro_detail', id=microcredential.id, slug=microcredential.slug)
    except Exception as e:
        logger.exception("Unexpected error in add_comment_microcredential: %s", str(e))
        messages.error(request, "An unexpected error occurred.")
        return redirect('courses:micro_detail', id=microcredential.id, slug=microcredential.slug)
    

def reply_comment(request, comment_id):
    if not request.user.is_authenticated:
        return redirect("/login/?next=%s" % request.path)
    
    # Ambil komentar yang akan dibalas
    comment = get_object_or_404(MicroCredentialComment, id=comment_id)

    # Jika form di-submit
    if request.method == 'POST':
        content = request.POST.get('content')
        if content:
            # Buat balasan komentar
            reply_comment = MicroCredentialComment(
                user=request.user,
                content=content,
                microcredential=comment.microcredential,
                parent=comment  # Tautkan dengan komentar induk
            )
            reply_comment.save()
            messages.success(request, 'Your reply has been posted.')
            return redirect('courses:micro_detail', id=comment.microcredential.id, slug=comment.microcredential.slug)

    return redirect('courses:micro_detail', id=comment.microcredential.id, slug=comment.microcredential.slug)


def enroll_microcredential(request, slug):
    if not request.user.is_authenticated:
        return redirect("/login/?next=%s" % request.path)

    # Ambil microcredential berdasarkan slug
    microcredential = get_object_or_404(MicroCredential, slug=slug)

    # Cek apakah microcredential aktif dan dalam periode pendaftaran
    current_date = timezone.now().date()
    if microcredential.status != 'active':
        messages.error(request, "This MicroCredential is not currently active.")
        return redirect('courses:microcredential_detail', slug=slug)
    
    if microcredential.start_date and current_date < microcredential.start_date:
        messages.error(request, "Enrollment has not yet started for this MicroCredential.")
        return redirect('courses:microcredential_detail', slug=slug)
    
    if microcredential.end_date and current_date > microcredential.end_date:
        messages.error(request, "Enrollment has closed for this MicroCredential.")
        return redirect('courses:microcredential_detail', slug=slug)
    
    # Proses enrollment jika metode adalah POST
    if request.method == 'POST':
        enrollment, created = microcredential.enroll_user(request.user)
        if created:
            messages.success(request, f"You have successfully enrolled in {microcredential.title} and its required courses!")
        else:
            messages.info(request, f"You are already enrolled in {microcredential.title}.")
        return redirect('courses:microcredential_detail', slug=slug)

    # Tampilkan halaman konfirmasi enrollment
    context = {
        'microcredential': microcredential,
        'required_courses': microcredential.required_courses.all(),
        'current_date': current_date,
    }
    return render(request, 'learner/enroll_microcredential.html', context)


def microcredential_detail(request, slug):
    if not request.user.is_authenticated:
        return redirect("/login/?next=%s" % request.path)

    # Ambil microcredential berdasarkan slug
    microcredential = get_object_or_404(MicroCredential, slug=slug)

    # Cek apakah pengguna sudah terdaftar
    is_enrolled = microcredential.enrollments.filter(user=request.user).exists()

    # Ambil semua kursus yang diperlukan
    required_courses = microcredential.required_courses.all()

    # Hitung status kelulusan dan skor untuk setiap kursus
    course_progress = []
    total_user_score = Decimal(0)
    total_max_score = Decimal(0)
    all_courses_completed = True

    for course in required_courses:
        assessments = Assessment.objects.filter(section__courses=course)
        course_score = Decimal(0)
        course_max_score = Decimal(0)
        course_completed = True

        for assessment in assessments:
            score_value = Decimal(0)
            total_questions = assessment.questions.count()
            if total_questions > 0:  # Multiple choice
                total_correct_answers = 0
                answers_exist = False
                for question in assessment.questions.all():
                    answers = QuestionAnswer.objects.filter(question=question, user=request.user)
                    if answers.exists():
                        answers_exist = True
                    total_correct_answers += answers.filter(choice__is_correct=True).count()
                if not answers_exist:
                    course_completed = False
                if total_questions > 0:
                    score_value = (Decimal(total_correct_answers) / Decimal(total_questions)) * Decimal(assessment.weight)
            else:  # AskOra
                askora_submissions = Submission.objects.filter(
                    askora__assessment=assessment,
                    user=request.user
                )
                if not askora_submissions.exists():
                    course_completed = False
                else:
                    latest_submission = askora_submissions.order_by('-submitted_at').first()
                    assessment_score = AssessmentScore.objects.filter(submission=latest_submission).first()
                    if assessment_score:
                        score_value = Decimal(assessment_score.final_score)

            score_value = min(score_value, Decimal(assessment.weight))
            course_score += score_value
            course_max_score += assessment.weight

        min_score = Decimal(microcredential.get_min_score(course))
        course_passed = course_completed and course_score >= min_score

        course_progress.append({
            'course': course,
            'user_score': course_score,
            'max_score': course_max_score,
            'min_score': min_score,
            'completed': course_completed,
            'passed': course_passed
        })

        total_user_score += course_score
        total_max_score += course_max_score
        if not course_passed:
            all_courses_completed = False

    microcredential_passed = all_courses_completed and total_user_score >= Decimal(microcredential.min_total_score)

    context = {
        'microcredential': microcredential,
        'course_progress': course_progress,
        'total_user_score': total_user_score,
        'total_max_score': total_max_score,
        'min_total_score': microcredential.min_total_score,
        'microcredential_passed': microcredential_passed,
        'current_date': timezone.now().date(),
        'is_enrolled': is_enrolled,  # Status enrollment
    }

    return render(request, 'learner/microcredential_detail.html', context)


# Configure weasyprint logging
logger = logging.getLogger(__name__)
logging.getLogger('weasyprint').setLevel(logging.DEBUG)

def generate_microcredential_certificate(request, id):
    if not request.user.is_authenticated:
        return redirect("/login/?next=%s" % request.path)

    # Ambil MicroCredential yang dipilih
    microcredential = get_object_or_404(MicroCredential, id=id)
    required_courses = microcredential.required_courses.all()

    total_user_score = Decimal(0)
    total_max_score = Decimal(0)
    all_courses_completed = True
    course_grades = []

    # Loop untuk menghitung nilai per course
    for course in required_courses:
        assessments = Assessment.objects.filter(section__courses=course)
        course_score = Decimal(0)
        course_max_score = Decimal(0)
        course_completed = True

        # Periksa setiap assessment di course
        for assessment in assessments:
            score_value = Decimal(0)
            total_questions = assessment.questions.count()
            if total_questions > 0:
                total_correct_answers = 0
                answers_exist = False
                for question in assessment.questions.all():
                    answers = QuestionAnswer.objects.filter(question=question, user=request.user)
                    if answers.exists():
                        answers_exist = True
                    total_correct_answers += answers.filter(choice__is_correct=True).count()
                if not answers_exist:
                    course_completed = False
                score_value = (Decimal(total_correct_answers) / Decimal(total_questions)) * Decimal(assessment.weight)
            else:
                submissions = Submission.objects.filter(askora__assessment=assessment, user=request.user)
                if not submissions.exists():
                    course_completed = False
                else:
                    latest = submissions.order_by('-submitted_at').first()
                    score_obj = AssessmentScore.objects.filter(submission=latest).first()
                    if score_obj:
                        score_value = Decimal(score_obj.final_score)

            score_value = min(score_value, Decimal(assessment.weight))
            course_score += score_value
            course_max_score += assessment.weight

        min_score = Decimal(microcredential.get_min_score(course))
        if not (course_completed and course_score >= min_score):
            all_courses_completed = False

        grade_point = (course_score / course_max_score * 100) if course_max_score > 0 else Decimal(0)
        course_grades.append({
            'name': course.course_name,
            'grade_point': grade_point.quantize(Decimal('0.01')),
        })
        total_user_score += course_score
        total_max_score += course_max_score

    # Jika belum memenuhi syarat
    if not (all_courses_completed and total_user_score >= Decimal(microcredential.min_total_score)):
        return render(request, 'error_template.html', {'message': 'You have not yet completed this MicroCredential.'})

    # Buat certificate_id dan UUID untuk QR code
    base_url = request.build_absolute_uri('/')
    certificate_id = f"CERT-{microcredential.id}-{request.user.id}"
    certificate_uuid = str(uuid.uuid4())

    # Buat QR Code
    verification_url = f"{base_url.rstrip('/')}/verify-micro/{certificate_uuid}/"
    qr = qrcode.QRCode(version=1, box_size=10, border=4)
    qr.add_data(verification_url)
    qr.make(fit=True)
    qr_img = qr.make_image(fill_color="black", back_color="white")

    # Simpan QR Code di server
    qr_dir = os.path.join(settings.MEDIA_ROOT, 'qrcodes')
    os.makedirs(qr_dir, exist_ok=True)
    qr_path = os.path.join(qr_dir, f'certificate_{certificate_uuid}.png')
    qr_img.save(qr_path)

    qr_code_url = f"{base_url.rstrip('/')}{settings.MEDIA_URL}qrcodes/certificate_{certificate_uuid}.png"

    # Ambil gambar microcredential dan foto author jika ada
    microcredential_image_absolute_url = (
        f"{base_url.rstrip('/')}{microcredential.image.url}" if microcredential.image else None
    )
    author_photo_absolute_url = (
        f"{base_url.rstrip('/')}{microcredential.author.photo.url}"
        if hasattr(microcredential.author, 'photo') and microcredential.author.photo
        else None
    )

    # Siapkan konteks untuk render HTML sertifikat
    context = {
        'microcredential': microcredential,
        'user': request.user,
        'current_date': timezone.now().date(),
        'microcredential_image_absolute_url': microcredential_image_absolute_url,
        'author_photo_absolute_url': author_photo_absolute_url,
        'course_grades': course_grades,
        'certificate_id': certificate_id,
        'min_total_score': microcredential.min_total_score,
        'qr_code_url': qr_code_url,
        'certificate_uuid': certificate_uuid,
    }

    html_content = render_to_string('learner/microcredential_certificate.html', context)

    # Coba buat PDF dengan WeasyPrint
    try:
        pdf = HTML(string=html_content, base_url=base_url).write_pdf()
    except Exception as e:
        logger.error(f"Error generating PDF: {str(e)}")
        return render(request, 'error_template.html', {'message': f'Error generating PDF: {str(e)}'})

    filename = f"certificate_{microcredential.slug}.pdf"

    # Periksa jika klaim sudah ada di database
    existing_claim = MicroClaim.objects.filter(user=request.user, microcredential=microcredential).first()
    if not existing_claim:
        MicroClaim.objects.create(
            user=request.user,
            microcredential=microcredential,
            certificate_id=certificate_id,
            certificate_uuid=certificate_uuid  # simpan UUID yang sama dengan di QR
        )

    # Kembalikan response PDF
    response = HttpResponse(pdf, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response

def verify_certificate_micro(request, certificate_id):
    # Ambil MicroClaim berdasarkan certificate_uuid yang diberikan
    certificate = get_object_or_404(MicroClaim, certificate_uuid=certificate_id)

    # Jika form disubmit dan email yang dimasukkan cocok
    if request.method == 'POST':
        input_email = request.POST.get('email')  # Ambil email dari form
        # Periksa apakah email yang dimasukkan sesuai dengan email pengguna yang mengklaim sertifikat
        if input_email == certificate.user.email:
            if not certificate.verified:
                certificate.verified = True
                certificate.save()
            message = "Certificate verified successfully."
        else:
            message = "The email you entered does not match. Verification failed."

        # Kirim pesan status ke template
        context = {
            'certificate': certificate,
            'message': message,
            'base_url': request.build_absolute_uri('/')
        }
        return render(request, 'courses/verify_certificate_micro.html', context)

    # Jika GET request (halaman pertama kali dimuat), tampilkan form tanpa perubahan
    context = {
        'certificate': certificate,
        'base_url': request.build_absolute_uri('/')
    }
    return render(request, 'courses/verify_certificate_micro.html', context)

def deletemic(request, pk):
    if not request.user.is_authenticated:
        return redirect("/login/?next=%s" % request.path)
    if not request.user.is_superuser:
        # Jika pengguna bukan superuser, beri pesan dan arahkan ke halaman lain (misalnya halaman utama)
        messages.error(request, "You do not have permission to delete this microcredential.")
        return redirect('courses:microcredential-list')
    
    microcredential = get_object_or_404(MicroCredential, pk=pk)  # Get the MicroCredential by pk

    if request.method == 'POST':  # Confirm deletion after form submission
        microcredential.delete()
        return redirect('courses:microcredential-list')  # Redirect to the list after deletion

    return render(request, 'micro/delete_micro.html', {'microcredential': microcredential})



def editmic(request, pk):
    if not request.user.is_authenticated:
        return redirect("/login/?next=%s" % request.path)
    microcredential = get_object_or_404(MicroCredential, pk=pk)  # Get the MicroCredential by pk

    if not request.user.is_superuser:
        # Jika pengguna bukan superuser, beri pesan dan arahkan ke halaman lain (misalnya halaman utama)
        messages.error(request, "You do not have permission to edit this microcredential.")
        return redirect('courses:microcredential-list')  

    if request.method == 'POST':
        form = MicroCredentialForm(request.POST, request.FILES, instance=microcredential)  # Prepopulate form with existing data
        if form.is_valid():
            form.save()
            return redirect('courses:microcredential-list')  # Redirect to the list after saving
    else:
        form = MicroCredentialForm(instance=microcredential)

    return render(request, 'micro/edit_micro.html', {'form': form, 'microcredential': microcredential})

@login_required  # Cara yang lebih bersih daripada manual redirect
def course_autocomplete(request):
    query = request.GET.get('q', '').strip()
    results = []

    if query:
        courses = Course.objects.filter(
            Q(course_name__icontains=query),
            status_course__status='published',
            end_enrol__gte=timezone.now()
        ).order_by('course_name')[:20]  # Limit hasil pencarian

        results = [{'id': c.id, 'text': c.course_name} for c in courses]

    return JsonResponse({'results': results})

def addmic(request):
    if not request.user.is_authenticated:
        return redirect("/login/?next=%s" % request.path)
    if not request.user.is_superuser:
        # Jika pengguna bukan superuser, beri pesan dan arahkan ke halaman lain (misalnya halaman utama)
        messages.error(request, "You do not have permission to add this microcredential.")
        return redirect('courses:microcredential-list')
    
    if request.method == 'POST':
        form = MicroCredentialForm(request.POST, request.FILES)  # Handle file uploads for the image field
        if form.is_valid():
            # Automatically set the author field to the logged-in user
            form.instance.author = request.user
            form.save()
            return redirect('courses:microcredential-list')  # Redirect to the list of microcredentials
    else:
        form = MicroCredentialForm()

    return render(request, 'micro/add_micro.html', {'form': form})
    
def detailmic(request, pk):
    if not request.user.is_authenticated:
        return redirect("/login/?next=%s" % request.path)
    # Fetch the MicroCredential object by its primary key
    microcredential = get_object_or_404(MicroCredential, pk=pk)

    return render(request, 'micro/detail_micro.html', {'microcredential': microcredential})


def listmic(request):
    if not request.user.is_authenticated:
        return redirect("/login/?next=%s" % request.path)

    if not (request.user.is_staff or request.user.is_superuser):
        messages.error(request, "You do not have permission to add this microcredential.")
        return redirect('authentication:dasbord')

    # Search logic
    search_query = request.GET.get('search', '')
    microcredentials = MicroCredential.objects.all()
    if search_query:
        microcredentials = microcredentials.filter(title__icontains=search_query)

    # Annotate dengan perhitungan yang akurat
    microcredentials = microcredentials.annotate(
        num_enrollments=Count('enrollments', distinct=True),
        avg_rating=Avg('reviews__rating'),
        num_courses=Count('required_courses', distinct=True),
        num_reviews=Count('reviews', distinct=True)
    ).order_by('-id')

    # Pagination
    paginator = Paginator(microcredentials, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    return render(request, 'micro/list_micro.html', {
        'page_obj': page_obj,
        'search_query': search_query,
    })





def calculate_score_for_user_and_course(user, course):
    # Implementasikan logika untuk menghitung skor berdasarkan asesmen yang ada
    assessments = Assessment.objects.filter(course=course)
    total_score = 0
    total_max_score = 0

    for assessment in assessments:
        # Hitung skor untuk setiap asesmen berdasarkan jawaban yang benar
        total_correct_answers = 0
        total_questions = assessment.questions.count()

        for question in assessment.questions.all():
            answers = QuestionAnswer.objects.filter(question=question, user=user)
            correct_answers = answers.filter(choice__is_correct=True).count()
            total_correct_answers += correct_answers

        score_value = (Decimal(total_correct_answers) / Decimal(total_questions)) * Decimal(assessment.weight)
        total_score += score_value
        total_max_score += assessment.weight

    if total_max_score > 0:
        percentage = (total_score / total_max_score) * 100
        # Simpan skor ke dalam Score
        score = Score(user=user, course=course, score=total_score, total_questions=total_max_score, percentage=percentage)
        score.save()
        return score
    return None

    
#ora create question
@csrf_exempt
def create_askora(request, idcourse, idsection, idassessment):
    # Cek apakah pengguna sudah login
    if not request.user.is_authenticated:
        return redirect("/login/?next=%s" % request.path)
    
    # Tentukan course berdasarkan peran pengguna
    if request.user.is_superuser:
        course = get_object_or_404(Course, id=idcourse)
    elif request.user.is_partner:
        course = get_object_or_404(Course, id=idcourse, org_partner__user_id=request.user.id)
    elif request.user.is_instructor:
        course = get_object_or_404(Course, id=idcourse, instructor__user_id=request.user.id)
    else:
        messages.error(request, "Anda tidak memiliki izin untuk membuat pertanyaan di kursus ini.")
        return redirect('courses:home')  # Redirect ke halaman aman

    # Pastikan section milik course
    section = get_object_or_404(Section, id=idsection, courses=course)

    # Pastikan assessment milik section
    assessment = get_object_or_404(Assessment, id=idassessment, section=section)

    # Menangani form jika metode adalah POST
    if request.method == 'POST':
        # Membuat form untuk AskOra
        question_form = AskOraForm(request.POST)

        # Validasi form
        if question_form.is_valid():
            # Menyimpan AskOra (pertanyaan)
            askora = question_form.save(commit=False)
            askora.assessment = assessment  # Tentukan assessment yang sesuai
            askora.save()  # Simpan pertanyaan

            messages.success(request, "question open response assement successfully to add")
            return redirect('courses:view-question', idcourse=course.id, idsection=section.id, idassessment=assessment.id)  # Redirect kembali ke halaman yang sama

    else:
        # Menangani GET request
        question_form = AskOraForm()

    return render(request, 'courses/create_ora.html', {
        'course': course,
        'section': section,
        'assessment': assessment,
        'question_form': question_form,
    })


def edit_askora(request, idcourse, idaskora, idsection, idassessment):
    # Fetch the objects needed (course, section, assessment, and askora)
    course = get_object_or_404(Course, id=idcourse)
    section = get_object_or_404(Section, id=idsection)
    assessment = get_object_or_404(Assessment, id=idassessment, section=section)
    askora = get_object_or_404(AskOra, id=idaskora, assessment=assessment)

    # Handle the form submission (POST)
    if request.method == 'POST':
        form = AskOraForm(request.POST, instance=askora)  # pre-populate with the existing data
        if form.is_valid():
            form.save()  # Save the updated AskOra
            messages.success(request, "AskOra question updated successfully!")
            return redirect('courses:view-question', idcourse=course.id, idsection=section.id, idassessment=assessment.id)
    else:
        form = AskOraForm(instance=askora)  # Populate the form with existing data

    # Render the template with the form
    return render(request, 'courses/edit_askora.html', {
        'course': course,
        'section': section,
        'assessment': assessment,
        'askora': askora,
        'question_form': form  # Pass the form to the template
    })


def delete_askora(request, idcourse, idaskora, idsection, idassessment):
    # Fetch the relevant objects
    course = get_object_or_404(Course, id=idcourse)
    section = get_object_or_404(Section, id=idsection)
    assessment = get_object_or_404(Assessment, id=idassessment, section=section)
    askora = get_object_or_404(AskOra, id=idaskora, assessment=assessment)

    # Check if the user has permission to delete (optional, based on your logic)
    if request.user.is_authenticated:
        

        # Delete the AskOra object
        askora.delete()
        messages.error(request, "AskOra question deleted successfully.")

        # Redirect after deletion
        return redirect('courses:view-question', idcourse=course.id, idsection=section.id, idassessment=assessment.id)

    # Redirect if not authenticated
    return redirect("/login/?next=%s" % request.path)


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

def is_suspicious(request):
    """Check if the request is suspicious based on User-Agent or missing Referer."""
    user_agent = request.META.get('HTTP_USER_AGENT', '')
    referer = request.META.get('HTTP_REFERER', '')
    
    # Bot detection (simple heuristic)
    if 'bot' in user_agent.lower() or not referer:
        return True
    return False

def add_comment(request, material_id):
    # Pastikan pengguna terautentikasi
    if not request.user.is_authenticated:
        return redirect("/login/?next=%s" % request.path)

    # Ambil objek material berdasarkan material_id yang diberikan
    material = get_object_or_404(Material, id=material_id)

    # Memastikan bahwa material terhubung dengan kursus dan bagian yang valid
    if material.section:
        if material.section.courses:
            course_slug = material.section.courses.slug
        else:
            # Jika tidak ada kursus yang terhubung, lakukan redirect
            return redirect('courses:course_list')
    else:
        return redirect('courses:course_list')  # Redirect jika bagian tidak ditemukan

    if request.method == 'POST':
        if is_suspicious(request):
            messages.warning(request, "Suspicious activity detected. Comment not posted.")
            return redirect(reverse('courses:course_learn', kwargs={'username': request.user.username, 'slug': course_slug}) + f"?material_id={material.id}")
        
        content = request.POST.get('content')
        parent_id = request.POST.get('parent_id')  # Ambil parent_id dari form

        parent_comment = None
        if parent_id:
            parent_comment = get_object_or_404(Comment, id=parent_id)  # Cari komentar induk berdasarkan parent_id

        # Memeriksa apakah komentar adalah spam
        if is_spam(request, request.user, content):
            messages.warning(request, "Komentar Anda terdeteksi sebagai spam!")
            return redirect(reverse('courses:course_learn', kwargs={'username': request.user.username, 'slug': course_slug}) + f"?material_id={material.id}")

        # Buat komentar baru atau balasan jika tidak terdeteksi sebagai spam
        Comment.objects.create(
            user=request.user,
            content=content,
            material=material,
            parent=parent_comment  # Menghubungkan balasan dengan komentar induk jika ada
        )

        # Redirect kembali ke halaman kursus
        messages.success(request, "Komentar berhasil diposting!")
        return redirect(reverse('courses:course_learn', kwargs={'username': request.user.username, 'slug': course_slug}) + f"?material_id={material.id}")

    # Jika bukan POST, hanya redirect ke halaman material yang sama
    return redirect(reverse('courses:course_learn', kwargs={'username': request.user.username, 'slug': course_slug}) + f"?material_id={material.id}")

#add coment course


@require_POST  # Hanya izinkan metode POST
@ratelimit(key='ip', rate='10/m', block=True)  # Batasi 10 request per menit per IP
@csrf_protect  # Pastikan CSRF protection aktif
def add_comment_course(request, course_id):
    # Cek akses
    if not request.user.is_authenticated:
        return redirect("/login/?next=%s" % request.path)
    
    try:
        course = get_object_or_404(Course, id=course_id)
    except Http404:
        messages.error(request, "Course not found.")
        return redirect('courses:course_list')

    if request.method == 'POST':
        # Mengecek apakah request mencurigakan (bot detection)
        if is_suspicious(request):
            messages.warning(request, "Suspicious activity detected. Comment not posted.")
            return redirect('courses:course_lms_detail', id=course.id, slug=course.slug)

        content = request.POST.get('content', '').strip()  # Ambil dan bersihkan input
        if not content:  # Validasi input kosong
            messages.error(request, "Comment cannot be empty.")
            return redirect('courses:course_lms_detail', id=course.id, slug=course.slug)

        parent_id = request.POST.get('parent_id')
        parent_comment = None

        # Menentukan apakah ini komentar balasan
        if parent_id:
            try:
                parent_comment = get_object_or_404(CourseComment, id=parent_id, course=course)
            except Http404:
                messages.error(request, "Invalid parent comment.")
                return redirect('courses:course_lms_detail', id=course.id, slug=course.slug)

        # Membuat objek komentar
        comment = CourseComment(
            user=request.user,
            content=content,
            course=course,
            parent=parent_comment
        )

        # Memeriksa apakah komentar mengandung kata kunci terlarang
        if comment.contains_blacklisted_keywords():
            messages.warning(request, "Your comment contains blacklisted content.")
            return redirect('courses:course_lms_detail', id=course.id, slug=course.slug)

        # Memeriksa apakah komentar adalah spam berdasarkan cooldown
        if comment.is_spam():
            messages.warning(request, "You are posting too frequently. Please wait a moment before posting again.")
            return redirect('courses:course_lms_detail', id=course.id, slug=course.slug)

        # Validasi dan simpan komentar
        try:
            comment.full_clean()  # Validasi model Django
            comment.save()
            messages.success(request, "Comment posted successfully!")
        except ValidationError as e:
            messages.error(request, f"Error posting comment: {e}")
            return redirect('courses:course_lms_detail', id=course.id, slug=course.slug)

        # Redirect aman dengan validasi referer
        referer = request.META.get('HTTP_REFERER')
        if referer and course_id in referer:
            return redirect(referer)
        return redirect('courses:course_lms_detail', id=course.id, slug=course.slug)

    return redirect('courses:course_lms_detail', id=course.id, slug=course.slug)

# Fungsi contoh untuk is_suspicious (harus didefinisikan)
def is_suspicious(request):
    # Logika deteksi bot (misalnya, cek header, CAPTCHA, dll.)
    # Contoh sederhana: return True jika tidak ada user agent
    user_agent = request.META.get('HTTP_USER_AGENT', '')
    return not user_agent or 'bot' in user_agent.lower()





def submit_assessment(request, assessment_id):
    if not request.user.is_authenticated:
        logger.info(f"Unauthenticated user attempted to submit assessment {assessment_id}")
        return redirect("/login/?next=%s" % request.path)

    # Ambil assessment berdasarkan ID
    assessment = get_object_or_404(Assessment, id=assessment_id)
    # Ambil course (pastikan hanya satu course terkait)
    try:
        course = assessment.section.courses.first()
        if not course:
            raise ValueError("No course associated with this assessment")
    except Exception as e:
        logger.error(f"Error retrieving course for assessment {assessment_id}: {str(e)}")
        messages.error(request, "Course not found for this assessment.")
        return redirect('authentication:dashbord')

    # Cek honeypot (bot jika terisi)
    honeypot = request.POST.get('honeypot')
    if honeypot:
        logger.warning(f"Spam detected for assessment {assessment_id} by user {request.user.username}")
        messages.error(request, "Spam terdeteksi. Pengiriman dibatalkan.")
        return redirect(reverse('courses:course_learn', kwargs={'username': request.user.username, 'slug': course.slug}) + f"?assessment_id={assessment.id}")

    # Periksa waktu pengisian form (cegah pengiriman terlalu cepat)
    start_time = request.POST.get('start_time')
    if start_time:
        try:
            start_time_obj = timezone.make_aware(datetime.strptime(start_time, '%Y-%m-%dT%H:%M:%S.%fZ'))
            elapsed_time = timezone.now() - start_time_obj
            if elapsed_time < timedelta(seconds=10):
                logger.warning(f"Submission too fast for assessment {assessment_id} by user {request.user.username}")
                messages.error(request, "Pengiriman terlalu cepat. Coba lagi setelah beberapa detik.")
                return redirect(reverse('courses:course_learn', kwargs={'username': request.user.username, 'slug': course.slug}) + f"?assessment_id={assessment.id}")
        except ValueError as e:
            logger.error(f"Invalid start time format for assessment {assessment_id}: {str(e)}")
            messages.error(request, "Format waktu mulai tidak valid.")
            return redirect(reverse('courses:course_learn', kwargs={'username': request.user.username, 'slug': course.slug}) + f"?assessment_id={assessment.id}")

    # Cek apakah user sudah pernah submit untuk assessment ini
    if Score.objects.filter(user=request.user, course=course, section=assessment.section, submitted=True).exists():
        logger.info(f"User {request.user.username} already submitted assessment {assessment_id}")
        messages.info(request, "Anda sudah mengirimkan jawaban untuk ujian ini.")
        return redirect(reverse('courses:course_learn', kwargs={'username': request.user.username, 'slug': course.slug}) + f"?assessment_id={assessment.id}")

    # Cek sesi dan waktu hanya jika durasi > 0
    session = AssessmentSession.objects.filter(user=request.user, assessment=assessment).first()
    if assessment.duration_in_minutes > 0:  # Hanya cek waktu jika bukan unlimited
        if not session:
            logger.warning(f"No session found for user {request.user.username}, assessment {assessment_id}")
            messages.error(request, "Sesi ujian tidak ditemukan.")
            return redirect(reverse('courses:course_learn', kwargs={'username': request.user.username, 'slug': course.slug}) + f"?assessment_id={assessment.id}")

        # Cek apakah waktu ujian sudah habis
        if timezone.now() > session.end_time:
            logger.warning(f"Assessment session expired for user {request.user.username}, assessment {assessment_id}")
            messages.warning(request, "Waktu ujian telah habis, Anda tidak dapat mengirimkan jawaban.")
            return redirect(reverse('courses:course_learn', kwargs={'username': request.user.username, 'slug': course.slug}) + f"?assessment_id={assessment.id}")

    if request.method == 'POST':
        correct_answers = 0
        total_questions = assessment.questions.count()

        # Proses setiap soal di assessment
        for question in assessment.questions.all():
            if QuestionAnswer.objects.filter(user=request.user, question=question).exists():
                logger.debug(f"Answer already exists for question {question.id} by user {request.user.username}")
                continue

            user_answer = request.POST.get(f"question_{question.id}")
            if user_answer:
                try:
                    choice = Choice.objects.get(id=user_answer)
                    QuestionAnswer.objects.create(user=request.user, question=question, choice=choice)
                    if choice.is_correct:
                        correct_answers += 1
                    logger.debug(f"Processed answer for question {question.id}: choice {choice.id}, correct={choice.is_correct}")
                except Choice.DoesNotExist:
                    logger.warning(f"Invalid choice ID {user_answer} for question {question.id} by user {request.user.username}")
                    continue

        # Menghitung nilai berdasarkan jawaban yang benar
        score_percentage = (correct_answers / total_questions) * 100 if total_questions > 0 else 0
        grade = calculate_grade(score_percentage, course)

        # Menyimpan hasil score ke model Score
        try:
            score = Score.objects.create(
                user=request.user,  # Gunakan objek User
                course=course,
                section=assessment.section,
                score=correct_answers,
                total_questions=total_questions,
                grade=grade,
                submitted=True
            )
            logger.info(f"Score saved for user {request.user.username}, assessment {assessment_id}, score {correct_answers}/{total_questions}")
        except Exception as e:
            logger.error(f"Error saving score for user {request.user.username}, assessment {assessment_id}: {str(e)}")
            messages.error(request, "Error submitting assessment. Please try again.")
            return redirect(reverse('courses:course_learn', kwargs={'username': request.user.username, 'slug': course.slug}) + f"?assessment_id={assessment.id}")

        # Perbarui progress user
        try:
            user_progress, created = CourseProgress.objects.get_or_create(user=request.user, course=course)
            user_progress.progress_percentage = score_percentage  # Asumsi field progress_percentage
            user_progress.save()
            logger.info(f"Updated progress for user {request.user.username}, course {course.id}, progress {score_percentage}%")
        except Exception as e:
            logger.error(f"Error updating progress for user {request.user.username}, course {course.id}: {str(e)}")

        # Hapus sesi asesmen jika ada
        if session:
            session.delete()
            logger.debug(f"Deleted session for user {request.user.username}, assessment {assessment_id}")

        messages.success(request, "Jawaban Anda telah berhasil disubmit. Terima kasih!")
        return redirect(reverse('courses:course_learn', kwargs={'username': request.user.username, 'slug': course.slug}) + f"?assessment_id={assessment.id}")

    logger.debug(f"Rendering submit_assessment.html for assessment {assessment_id}, user {request.user.username}")
    return render(request, 'submit_assessment.html', {'assessment': assessment})

def calculate_overall_pass_fail(user, course):
    
    # Ambil semua asesmen untuk kursus ini
    assessments = Assessment.objects.filter(section__courses=course)
    total_max_score = 0  # Total skor maksimal dari semua asesmen
    total_score = 0  # Total skor yang didapatkan dari pengguna
    all_passed = True  # Untuk melacak apakah semua asesmen lulus

    # Hitung skor untuk setiap asesmen
    for assessment in assessments:
        total_questions = assessment.questions.count()  # Jumlah soal pada asesmen ini
        total_correct_answers = 0  # Jumlah jawaban benar dari pengguna

        for question in assessment.questions.all():
            # Mengambil jawaban yang dipilih oleh pengguna untuk pertanyaan ini
            answers = QuestionAnswer.objects.filter(question=question, user=user)
            
            # Cek apakah jawaban yang dipilih benar
            correct_answers = answers.filter(choice__is_correct=True).count()  # Jawaban benar
            total_correct_answers += correct_answers

        # Tentukan skor berdasarkan jumlah jawaban benar dan jumlah soal
        score_value = 0
        if total_questions > 0:
            # Menghitung skor berdasarkan jawaban benar dan total soal
            score_value = (Decimal(total_correct_answers) / Decimal(total_questions)) * Decimal(assessment.weight)

        # Tentukan status kelulusan per asesmen
        passing_threshold = 60  # Ambang batas kelulusan per asesmen (misalnya 60%)
        if (score_value / assessment.weight) * 100 < passing_threshold:
            all_passed = False  # Jika ada asesmen yang tidak lulus, status keseluruhan adalah "Fail"

        total_max_score += assessment.weight  # Bobot maksimal
        total_score += score_value  # Skor yang didapat pengguna

    # Hitung persentase keseluruhan
    if total_max_score > 0:
        overall_percentage = (total_score / total_max_score) * 100
    else:
        overall_percentage = 0

    # Ambil ambang batas kelulusan dari GradeRange
    grade_range = GradeRange.objects.filter(course=course).first()  # Ambil grade range untuk kursus ini

    if grade_range:
        passing_threshold = grade_range.min_grade
    else:
        passing_threshold = 60  # Default jika tidak ada GradeRange

    status = "Pass" if all_passed and overall_percentage >= passing_threshold else "Fail"

    return total_score, overall_percentage, status






def calculate_total_score_and_status(user_id, course):
    # Ambil semua asesmen untuk kursus yang ditentukan
    assessments = Assessment.objects.filter(section__courses=course)
    print(f"Assessments for course {course.course_name}: {assessments.count()}")  # Debugging

    if not assessments.exists():
        return 0, 0, "No assessments available"  # Jika tidak ada asesmen

    total_score = 0
    total_weight = 0
    total_questions = 0  # Menyimpan total pertanyaan

    # Hitung total skor berdasarkan nilai yang diperoleh dari setiap asesmen
    for assessment in assessments:
        # Ambil nilai dari model Score yang relevan
        score_entry = Score.objects.filter(user=user_id, course=course, section=assessment.section).first()
        print(f"Score entry for assessment {assessment.name}: {score_entry}")  # Debugging
        if score_entry:
            total_score += score_entry.score  # Tambahkan skor yang diperoleh
            total_weight += assessment.weight  # Tambahkan bobot asesmen
            total_questions += score_entry.total_questions  # Tambahkan total pertanyaan

    if total_weight == 0 or total_questions == 0:
        return total_score, 0, "No assessments available"  # Jika tidak ada bobot atau pertanyaan

    overall_percentage = (total_score / total_questions) * 100  # Hitung persentase berdasarkan total pertanyaan

    # Ambil rentang nilai untuk kursus ini
    grade_ranges = GradeRange.objects.filter(course=course).order_by('min_grade')

    # Tentukan status kelulusan berdasarkan rentang nilai
    for grade_range in grade_ranges:
        if overall_percentage >= grade_range.min_grade and overall_percentage <= grade_range.max_grade:
            return total_score, overall_percentage, grade_range.name  # Mengembalikan total skor, persentase, dan nama grade

    # Jika tidak ada grade range yang sesuai, default ke "Fail"
    return total_score, overall_percentage, "Fail"

def calculate_grade(overall_percentage, course):
    # Ambil grade ranges untuk course ini
    grade_ranges = GradeRange.objects.filter(course=course).order_by('min_grade')

    # Memeriksa score_percentage dalam rentang grade yang ditemukan
    for grade_range in grade_ranges:
        # Periksa jika overall_percentage berada dalam rentang nilai yang valid
        if overall_percentage >= grade_range.min_grade and overall_percentage <= grade_range.max_grade:
            return grade_range.name  # Mengembalikan nama grade

    # Jika tidak ada grade range yang sesuai, default ke "Fail"
    return 'Fail'  # Default ke Fail jika tidak ada grade range yang sesuai

def start_assessment(request, assessment_id):
    if not request.user.is_authenticated:
        return redirect("/login/?next=%s" % request.path)
    # Get the assessment using the provided ID
    assessment = get_object_or_404(Assessment, id=assessment_id)

    # Check if the user already has a session for this assessment
    existing_session = AssessmentSession.objects.filter(user=request.user, assessment=assessment).first()

    if not existing_session:
        # If the session doesn't exist, create a new one with start_time set to now
        session = AssessmentSession(
            user=request.user,
            assessment=assessment,
            start_time=timezone.now()  # Set the start time to now
        )
        # Calculate the end time by adding the duration of the assessment to the start time
        session.end_time = session.start_time + timedelta(minutes=assessment.duration_in_minutes)
        session.save()  # Save the session

    # Get the associated course slug and username for redirecting
    username = request.user.username
    slug = assessment.section.courses.slug

    # Redirect back to the course or assessment page after starting
    return redirect(reverse('courses:course_learn', kwargs={'username': request.user.username, 'slug': assessment.section.courses.slug}) + f"?assessment_id={assessment.id}")


def course_learn(request, username, slug):
    if not request.user.is_authenticated:
        logger.info(f"Unauthenticated user attempted to access course {slug}")
        return redirect("/login/?next=%s" % request.path)
    if request.user.is_authenticated:
        UserActivityLog.objects.create(user=request.user, activity_type='course_learn')

    course = get_object_or_404(Course, slug=slug)

    if request.user.username != username:
        logger.warning(f"User {request.user.username} attempted to access course {slug} with username {username}")
        return redirect('authentication:course_list')

    if not Enrollment.objects.filter(user=request.user, course=course).exists():
        logger.info(f"User {request.user.username} not enrolled in course {slug}")
        return redirect('courses:course_lms_detail', id=course.id, slug=course.slug)

    course_name = course.course_name

    sections = Section.objects.filter(courses=course).prefetch_related(
        Prefetch('materials', queryset=Material.objects.all()),
        Prefetch('assessments', queryset=Assessment.objects.all().prefetch_related(
            Prefetch('questions', queryset=Question.objects.all().prefetch_related(
                Prefetch('choices', queryset=Choice.objects.all())
            )),
            Prefetch('ask_oras', queryset=AskOra.objects.all()),
            Prefetch('lti_tools', queryset=LTIExternalTool.objects.all())
        ))
    )

    combined_content = []
    for section in sections:
        for material in section.materials.all():
            combined_content.append(('material', material, section))
        for assessment in section.assessments.all():
            combined_content.append(('assessment', assessment, section))

    total_content = len(combined_content)

    material_id = request.GET.get('material_id')
    assessment_id = request.GET.get('assessment_id')

    current_content = None
    assessment_locked = False
    payment_required_url = None

    if not material_id and not assessment_id:
        current_content = combined_content[0] if combined_content else None
    elif material_id:
        material = get_object_or_404(Material, id=material_id)
        current_content = ('material', material, next((s for s in sections if material in s.materials.all()), None))
    elif assessment_id:
        assessment = get_object_or_404(Assessment, id=assessment_id)
        # Cek pembayaran untuk pay_for_exam
        if course.payment_model == 'pay_for_exam':
            payment = Payment.objects.filter(
                user=request.user,
                course=course,
                status='completed',
                payment_model='pay_for_exam'
            ).first()
            if not payment:
                assessment_locked = True
                payment_required_url = reverse('payments:process_payment', kwargs={'course_id': course.id, 'payment_type': 'exam'})
                messages.info(request, "This exam requires payment. You can add it to your cart or proceed to the next content.")
                logger.info(f"Payment required for exam in course {course.id} for user {request.user.username}")
                # Tetap atur current_content untuk assessment terkunci
                current_content = ('assessment', assessment, next((s for s in sections if assessment in s.assessments.all()), None))
            else:
                current_content = ('assessment', assessment, next((s for s in sections if assessment in s.assessments.all()), None))
        else:
            current_content = ('assessment', assessment, next((s for s in sections if assessment in s.assessments.all()), None))

    comments = None
    page_comments = []
    if current_content:
        if current_content[0] == 'material':
            material = current_content[1]
            comments = Comment.objects.filter(material=material, parent=None).order_by('-created_at')
        elif current_content[0] == 'assessment':
            section = current_content[2]
            comments = Comment.objects.filter(material__section=section, parent=None).order_by('-created_at')

        if comments:
            paginator = Paginator(comments, 5)
            page_number = request.GET.get('page')
            page_comments = paginator.get_page(page_number)

    material = None
    assessment = None

    if current_content:
        if current_content[0] == 'material':
            material = current_content[1]
        elif current_content[0] == 'assessment':
            assessment = current_content[1]

        LastAccessCourse.objects.update_or_create(
            user=request.user,
            course=course,
            defaults={
                'material': material,
                'assessment': assessment
            }
        )

    is_started = False
    is_expired = False
    remaining_time = 0

    if assessment:
        session = AssessmentSession.objects.filter(user=request.user, assessment=assessment).first()
        if session:
            is_started = True
            remaining_time = int((session.end_time - timezone.now()).total_seconds())
            if remaining_time <= 0:
                is_expired = True
                remaining_time = 0
        else:
            if assessment.duration_in_minutes == 0:
                is_started = True
                remaining_time = 0
            else:
                is_started = False

    current_index = -1
    if current_content:
        for i, content in enumerate(combined_content):
            if (content[0] == current_content[0] and 
                content[1].id == current_content[1].id and 
                content[2].id == current_content[2].id):
                current_index = i
                break
    elif assessment_locked and assessment_id:
        # Pastikan current_content untuk assessment terkunci
        assessment = get_object_or_404(Assessment, id=assessment_id)
        current_content = ('assessment', assessment, next((s for s in sections if assessment in s.assessments.all()), None))
        for i, content in enumerate(combined_content):
            if content[0] == 'assessment' and content[1].id == int(assessment_id):
                current_index = i
                break
        if current_index == -1:
            current_index = 0  # Fallback untuk mencegah error

    previous_content = combined_content[current_index - 1] if current_index > 0 else None
    next_content = combined_content[current_index + 1] if current_index < len(combined_content) - 1 and current_index != -1 else None
    is_last_content = next_content is None

    previous_url = None
    next_url = None
    if previous_content:
        previous_url = reverse('courses:course_learn', kwargs={'username': username, 'slug': slug}) + f"?{previous_content[0]}_id={previous_content[1].id}"
    if next_content:
        next_url = reverse('courses:course_learn', kwargs={'username': username, 'slug': slug}) + f"?{next_content[0]}_id={next_content[1].id}"

    if current_content:
        if current_content[0] == 'material':
            material = current_content[1]
            if not MaterialRead.objects.filter(user=request.user, material=material).exists():
                MaterialRead.objects.create(user=request.user, material=material)
        elif current_content[0] == 'assessment':
            assessment = current_content[1]
            if not AssessmentRead.objects.filter(user=request.user, assessment=assessment).exists():
                AssessmentRead.objects.create(user=request.user, assessment=assessment)

    user_progress, created = CourseProgress.objects.get_or_create(user=request.user, course=course)
    if current_content and (current_index + 1) > user_progress.progress_percentage / 100 * total_content:
        user_progress.progress_percentage = (current_index + 1) / total_content * 100
        user_progress.save()

    score = Score.objects.filter(user=request.user.username, course=course).order_by('-date').first()
    user_grade = 'Fail'
    if score:
        score_percentage = (score.score / score.total_questions) * 100
        user_grade = calculate_grade(score_percentage, course)

    assessments = Assessment.objects.filter(section__courses=course)
    assessment_scores = []
    total_max_score = 0
    total_score = 0
    all_assessments_submitted = True

    grade_range = GradeRange.objects.filter(course=course).all()
    if grade_range:
        pass_range = grade_range.filter(name='Pass').first()
        passing_threshold = pass_range.min_grade
        max_grade = pass_range.max_grade
    else:
        return render(request, 'error_template.html', {'error': 'Grade range not found for this course.'})

    for assessment in assessments:
        score_value = Decimal(0)
        total_correct_answers = 0
        total_questions = assessment.questions.count()
        if total_questions > 0:
            answers_exist = False
            for question in assessment.questions.all():
                answers = QuestionAnswer.objects.filter(question=question, user=request.user)
                if answers.exists():
                    answers_exist = True
                total_correct_answers += answers.filter(choice__is_correct=True).count()
            if not answers_exist:
                all_assessments_submitted = False
            if total_questions > 0:
                score_value = (Decimal(total_correct_answers) / Decimal(total_questions)) * Decimal(assessment.weight)
        else:
            askora_submissions = Submission.objects.filter(askora__assessment=assessment, user=request.user)
            if not askora_submissions.exists():
                all_assessments_submitted = False
            else:
                latest_submission = askora_submissions.order_by('-submitted_at').first()
                assessment_score = AssessmentScore.objects.filter(submission=latest_submission).first()
                if assessment_score:
                    score_value = Decimal(assessment_score.final_score)

        score_value = min(score_value, Decimal(assessment.weight))
        assessment_scores.append({
            'assessment': assessment,
            'score': score_value,
            'weight': assessment.weight
        })
        total_max_score += assessment.weight
        total_score += score_value

    total_score = min(total_score, total_max_score)
    overall_percentage = (total_score / total_max_score) * 100 if total_max_score > 0 else 0
    passing_criteria_met = overall_percentage >= passing_threshold
    status = "Pass" if all_assessments_submitted and passing_criteria_met else "Fail"

    assessment_results = [
        {'name': score['assessment'].name, 'max_score': score['weight'], 'score': score['score']}
        for score in assessment_scores
    ]
    assessment_results.append({'name': 'Total', 'max_score': total_max_score, 'score': total_score})

    askoras = AskOra.objects.filter(assessment__section__courses=course)
    try:
        submissions = Submission.objects.filter(
            askora__in=AskOra.objects.filter(assessment__section__courses=course),
            user=request.user
        )
    except Exception as e:
        submissions = []

    questions = Question.objects.filter(assessment__in=assessments)
    answered_questions = {q.id: QuestionAnswer.objects.filter(user=request.user, question=q).first() for q in questions}

    peer_submissions = Submission.objects.filter(
        askora__in=AskOra.objects.filter(assessment__section__courses=course)
    ).exclude(user=request.user).prefetch_related('peer_reviews')

    peer_submissions_data = []
    for submission in peer_submissions:
        has_reviewed = submission.peer_reviews.filter(reviewer=request.user).exists()
        assessment_score, created = AssessmentScore.objects.get_or_create(submission=submission)
        peer_reviews = submission.peer_reviews.all()
        assessment_weight = float(submission.askora.assessment.weight)
        max_peer_score = 5.0

        user_has_submitted = Submission.objects.filter(
            askora=submission.askora,
            user=request.user
        ).exists()

        if peer_reviews:
            total_score_reviews = sum(float(review.score) * float(review.weight) for review in peer_reviews)
            peer_review_count = peer_reviews.count()
            avg_peer_score = total_score_reviews / peer_review_count
            scaled_peer_score = (avg_peer_score / max_peer_score) * assessment_weight
            participant_score = assessment_weight
            final_score = (participant_score * 0.5) + (scaled_peer_score * 0.5)
        else:
            final_score = assessment_weight * 0.5

        try:
            assessment_score.final_score = final_score
            assessment_score.save()
        except Exception as e:
            final_score = float(assessment_score.final_score or 0.0)

        peer_submissions_data.append({
            'submission': submission,
            'has_reviewed': has_reviewed,
            'final_score': final_score,
            'can_review': user_has_submitted
        })

    lti_tools = LTIExternalTool.objects.filter(assessment__section__courses=course)
    context = {
        'course': course,
        'course_name': course_name,
        'sections': sections,
        'current_content': current_content,
        'previous_url': previous_url,
        'next_url': next_url,
        'course_progress': user_progress.progress_percentage,
        'user_grade': user_grade,
        'assessment_results': assessment_results,
        'total_score': total_score,
        'overall_percentage': overall_percentage,
        'total_weight': total_max_score,
        'status': status,
        'is_started': is_started,
        'is_expired': is_expired,
        'remaining_time': remaining_time,
        'max_grade': max_grade,
        'passing_threshold': passing_threshold,
        'is_last_content': is_last_content,
        'comments': page_comments,
        'material': current_content[1] if current_content and current_content[0] == 'material' else None,
        'assessment': current_content[1] if current_content and current_content[0] == 'assessment' else None,
        'answered_questions': answered_questions,
        'askoras': askoras,
        'submissions': submissions,
        'lti_tools': lti_tools,
        'peer_submissions_data': peer_submissions_data,
        'assessment_locked': assessment_locked,
        'payment_required_url': payment_required_url,
    }

    return render(request, 'learner/course_learn.html', context)

def submit_peer_review(request, submission_id):
    submission = get_object_or_404(Submission, id=submission_id)
    if request.method == 'POST':
        if not PeerReview.objects.filter(submission=submission, reviewer=request.user).exists():
            try:
                peer_review = PeerReview(
                    submission=submission,
                    reviewer=request.user,
                    score=int(request.POST.get('score')),
                    comment=request.POST.get('comment'),
                    weight=1.0
                )
                peer_review.save()
                #print(f"Peer review saved for Submission {submission.id} by {request.user.username}")

                # Hitung skor akhir secara manual
                assessment_score, created = AssessmentScore.objects.get_or_create(submission=submission)
                peer_reviews = submission.peer_reviews.all()
                if peer_reviews:
                    total_score = sum(float(review.score) * float(review.weight) for review in peer_reviews)
                    peer_review_count = peer_reviews.count()
                    avg_peer_score = total_score / peer_review_count
                    participant_score = 5.0
                    assessment_score.final_score = (participant_score * 0.5) + (avg_peer_score * 0.5)
                else:
                    assessment_score.final_score = 2.5
                assessment_score.save()
                print(f"Final score updated: {assessment_score.final_score}")
            except Exception as e:
                print(f"Error in peer review process for Submission {submission.id}: {e}")
    
    assessment = submission.askora.assessment
    course_slug = assessment.section.courses.slug
    return redirect(
        reverse('courses:course_learn', kwargs={'username': request.user.username, 'slug': course_slug}) + 
        f"?assessment_id={assessment.id}"
    )

def submit_answer(request, askora_id):
    askora = get_object_or_404(AskOra, id=askora_id)
    if request.method == 'POST' and askora.is_responsive():
        try:
            submission = Submission(
                askora=askora,
                user=request.user,
                answer_text=request.POST.get('answer_text'),
                answer_file=request.FILES.get('answer_file')
            )
            submission.save()
            print(f"Submission saved for AskOra {askora.id}")
        except Exception as e:
            print(f"Error saving submission: {e}")
    
    # Redirect ke course_learn dengan assessment_id
    assessment = askora.assessment
    course_slug = assessment.section.courses.slug  # Ganti .first() dengan akses langsung
    return redirect(
        reverse('courses:course_learn', kwargs={'username': request.user.username, 'slug': course_slug}) + 
        f"?assessment_id={assessment.id}"
    )


# Setup logging untuk debugging
def generate_certificate(request, course_id):
    if not request.user.is_authenticated:
        logger.info(f"Unauthenticated user attempted to claim certificate for course {course_id}")
        return redirect("/login/?next=%s" % request.path)

    course = get_object_or_404(Course, id=course_id)

    # Cek apakah pengguna terdaftar di kursus
    if not Enrollment.objects.filter(user=request.user, course=course).exists():
        logger.warning(f"User {request.user.username} not enrolled in course {course.id}")
        messages.error(request, "You are not enrolled in this course.")
        return redirect('authentication:dashbord')

    # Cek pembayaran untuk sertifikat jika diperlukan
    if course.payment_model == 'pay_for_certificate':
        payment = Payment.objects.filter(
            user=request.user,
            course=course,
            status='completed',
            payment_model='pay_for_certificate'
        ).first()
        if not payment:
            logger.info(f"Payment required for certificate in course {course.id} for user {request.user.username}")
            messages.info(request, "This certificate requires payment. Please complete the payment to claim your certificate.")
            payment_url = reverse('payments:process_payment', kwargs={'course_id': course.id, 'payment_type': 'certificate'})
            return redirect(payment_url)

    # Ambil semua asesmen untuk kursus ini
    assessments = Assessment.objects.filter(section__courses=course)
    assessment_scores = []
    total_max_score = 0
    total_score = 0
    all_assessments_submitted = True

    # Ambil GradeRange yang terkait dengan kursus
    grade_range = GradeRange.objects.filter(course=course).all()
    if not grade_range:
        logger.error(f"No grade range found for course {course.id}")
        messages.error(request, "Passing grade not found for this course. Certificate cannot be issued.")
        return redirect('authentication:dashbord')

    passing_threshold = grade_range.filter(name='Pass').first().min_grade
    max_grade = grade_range.filter(name='Pass').first().max_grade

    for assessment in assessments:
        score_value = Decimal(0)
        total_correct_answers = 0
        total_questions = assessment.questions.count()
        if total_questions > 0:  # Assessment adalah multiple choice
            answers_exist = False
            for question in assessment.questions.all():
                answers = QuestionAnswer.objects.filter(question=question, user=request.user)
                if answers.exists():
                    answers_exist = True
                total_correct_answers += answers.filter(choice__is_correct=True).count()
            if not answers_exist:
                all_assessments_submitted = False
            if total_questions > 0:
                score_value = (Decimal(total_correct_answers) / Decimal(total_questions)) * Decimal(assessment.weight)
        else:  # Assessment adalah AskOra
            askora_submissions = Submission.objects.filter(
                askora__assessment=assessment,
                user=request.user
            )
            if not askora_submissions.exists():
                all_assessments_submitted = False
            else:
                latest_submission = askora_submissions.order_by('-submitted_at').first()
                assessment_score = AssessmentScore.objects.filter(submission=latest_submission).first()
                if assessment_score:
                    score_value = Decimal(assessment_score.final_score)

        score_value = min(score_value, Decimal(assessment.weight))
        assessment_scores.append({
            'assessment': assessment,
            'score': score_value,
            'weight': assessment.weight
        })
        total_max_score += assessment.weight
        total_score += score_value

    total_score = min(total_score, total_max_score)
    overall_percentage = (total_score / total_max_score) * 100 if total_max_score > 0 else 0
    passing_criteria_met = overall_percentage >= passing_threshold
    status = "Pass" if all_assessments_submitted and passing_criteria_met else "Fail"

    if status == "Fail":
        logger.error(f"User {request.user.username} failed to meet passing criteria for course {course.id}")
        messages.error(request, "You have not met the passing criteria for this course.")
        return redirect('authentication:dashbord')

    # Format hasil assessment
    assessment_results = [
        {'name': score['assessment'].name, 'max_score': score['weight'], 'score': score['score']}
        for score in assessment_scores
    ]
    assessment_results.append({'name': 'Total', 'max_score': total_max_score, 'score': total_score})

    # Ambil logo partner dari org_partner
    partner_logo_url = None
    base_url = request.build_absolute_uri('/')  # Misalnya, http://localhost:8000/
    try:
        if course.org_partner and course.org_partner.logo:
            partner_logo_url = base_url.rstrip('/') + course.org_partner.logo.url
            logger.info(f"Partner logo found: {partner_logo_url}")
        else:
            logger.warning(f"No logo found for partner {course.org_partner}")
    except Exception as e:
        logger.error(f"Error fetching partner logo: {str(e)}")

    # Cek apakah sertifikat sudah pernah diterbitkan
    existing_certificate = Certificate.objects.filter(user=request.user, course=course).first()
    if existing_certificate:
        logger.info(f"Certificate {existing_certificate.certificate_id} already exists for user {request.user.username}")
        messages.info(request, "You have already claimed a certificate for this course.")
        # Generate ulang QR code URL untuk sertifikat yang sudah ada
        qr_url = request.build_absolute_uri(settings.MEDIA_URL + f'qrcodes/certificate_{existing_certificate.certificate_id}.png')
        # Render template untuk sertifikat yang sudah ada
        html_content = render_to_string('learner/certificate_template.html', {
            'passing_threshold': passing_threshold,
            'status': status,
            'course': course,
            'total_score': total_score,
            'user': request.user,
            'issue_date': existing_certificate.issue_date.strftime('%Y-%m-%d'),
            'assessment_results': assessment_results,
            'partner_logo_url': partner_logo_url,
            'qr_code_url': qr_url,
            'base_url': base_url,
        })
        try:
            pdf = HTML(string=html_content, base_url=base_url).write_pdf()
            filename = f"certificate_{course.slug}.pdf"
            response = HttpResponse(pdf, content_type='application/pdf')
            response['Content-Disposition'] = f'attachment; filename="{filename}"'
            return response
        except Exception as e:
            logger.error(f"Error re-generating PDF for existing certificate: {str(e)}")
            messages.error(request, "Error retrieving certificate. Please contact support.")
            return redirect('authentication:dashbord')

    # Generate QR code dan simpan sertifikat baru
    certificate_id = uuid.uuid4()
    verification_url = f"{base_url.rstrip('/')}/verify/{certificate_id}/"
    qr = qrcode.QRCode(version=1, box_size=10, border=4)
    qr.add_data(verification_url)
    qr.make(fit=True)
    qr_img = qr.make_image(fill_color="black", back_color="white")
    qr_path = os.path.join(settings.MEDIA_ROOT, 'qrcodes', f'certificate_{certificate_id}.png')
    os.makedirs(os.path.dirname(qr_path), exist_ok=True)
    qr_img.save(qr_path)
    qr_url = base_url.rstrip('/') + settings.MEDIA_URL + f'qrcodes/certificate_{certificate_id}.png'
    logger.info(f"QR code generated: {qr_url}")

    # Simpan sertifikat ke database
    try:
        Certificate.objects.create(
            certificate_id=certificate_id,
            user=request.user,
            course=course,
            issue_date=timezone.now().date(),
            total_score=total_score,
            partner=course.org_partner
        )
        logger.info(f"Certificate {certificate_id} saved for user {request.user.username}")
    except Exception as e:
        logger.error(f"Error saving certificate: {str(e)}")
        messages.error(request, "Error generating certificate. Please try again.")
        return redirect('authentication:dashbord')

    # Render HTML untuk sertifikat
    html_content = render_to_string('learner/certificate_template.html', {
        'passing_threshold': passing_threshold,
        'status': status,
        'course': course,
        'total_score': total_score,
        'user': request.user,
        'issue_date': timezone.now().strftime('%Y-%m-%d'),
        'assessment_results': assessment_results,
        'partner_logo_url': partner_logo_url,
        'qr_code_url': qr_url,
        'base_url': base_url,
    })

    # Menghasilkan PDF dari HTML yang dirender
    try:
        pdf = HTML(string=html_content, base_url=base_url).write_pdf()
    except Exception as e:
        logger.error(f"Error generating PDF: {str(e)}")
        messages.error(request, "Error generating certificate. Please try again.")
        return redirect('authentication:dashbord')

    filename = f"certificate_{course.slug}.pdf"
    response = HttpResponse(pdf, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response



def verify_certificate(request, certificate_id):
    certificate = get_object_or_404(Certificate, certificate_id=certificate_id)
    context = {
        'certificate': certificate,
        'base_url': request.build_absolute_uri('/')
    }
    return render(request, 'courses/verify_certificate.html', context)

#re-runs course
def course_reruns(request, id):
    """ View for creating a re-run of a course, along with related data like CoursePrice, Assessments, Materials, and GradeRange """

    course = get_object_or_404(Course, id=id)

    # Check if the course status is "archive"
    try:
        archive_status = CourseStatus.objects.get(status='archived')
        draft_status = CourseStatus.objects.get(status='draft')
    except CourseStatus.DoesNotExist:
        messages.error(request, "The 'archived' or 'draft' status is missing. Please check your data.")
        return redirect('courses:studio', id=course.id)

    # Check if the course status is 'archived'
    if course.status_course != archive_status:
        messages.warning(request, "Only archived courses can be re-run.")
        return redirect('courses:studio', id=course.id)

    # Check if the user has permission to create a re-run for this course
    if not (request.user.is_superuser or request.user == course.org_partner.user or request.user == course.instructor.user):
        messages.error(request, "You do not have permission to create a re-run for this course.")
        return redirect('courses:studio', id=course.id)

    # If the request method is POST, the user is submitting the form to create the re-run
    if request.method == 'POST':
        form = CourseRerunForm(request.POST)

        if form.is_valid():
            today = timezone.now().date()

            # Check if a re-run already exists for today
            existing_rerun = Course.objects.filter(
                course_name=course.course_name,
                course_run__startswith="Run",
                created_at__date=today
            ).exists()

            if existing_rerun:
                messages.error(request, "A re-run for this course has already been created today.")
                return redirect('courses:studio', id=course.id)

            # Process the creation of the new course re-run
            new_course = form.save(commit=False)
            new_course.course_name = form.cleaned_data['course_name_hidden']
            new_course.org_partner = form.cleaned_data['org_partner_hidden']
            new_course.status_course = draft_status
            new_course.slug = f"{slugify(new_course.course_name)}-{new_course.course_run.lower().replace(' ', '-')}"
            new_course.created_at = timezone.now()
            new_course.author = request.user
            
            # Set fields from the original course
            new_course.instructor = course.instructor
            new_course.language = course.language
            new_course.image = course.image
            new_course.link_video = course.link_video
            new_course.description = course.description
            new_course.sort_description = course.sort_description
            new_course.hour = course.hour
            new_course.save()

            # Copy the CoursePrice related to the original course
            for course_price in course.prices.all():
                CoursePrice.objects.create(
                    course=new_course,
                    price_type=course_price.price_type,
                    partner=course_price.partner,
                    partner_price=course_price.partner_price,
                    discount_percent=course_price.discount_percent,
                    discount_amount=course_price.discount_amount,
                    ice_share_rate=course_price.ice_share_rate,
                    admin_fee=course_price.admin_fee,
                    sub_total=course_price.sub_total,
                    portal_price=course_price.portal_price,
                    normal_price=course_price.normal_price,
                    calculate_admin_price=course_price.calculate_admin_price,
                    platform_fee=course_price.platform_fee,
                    voucher=course_price.voucher,
                    user_payment=course_price.user_payment,
                    partner_earning=course_price.partner_earning,
                    ice_earning=course_price.ice_earning
                )

            # Copy GradeRange related to the original course
            grade_range_mapping = {}
            for grade_range in course.grade_ranges.all():
                new_grade_range = GradeRange.objects.create(
                    course=new_course,
                    name=grade_range.name,
                    min_grade=grade_range.min_grade,
                    max_grade=grade_range.max_grade,
                    created_at=grade_range.created_at
                )
                grade_range_mapping[grade_range.id] = new_grade_range

            # Copy the Sections and related Materials, Assessments, and AskOra
            for section in course.sections.all():
                # Check if the new section already exists for this course (avoid duplicates)
                existing_section = Section.objects.filter(
                    title=section.title,
                    courses=new_course,
                    parent__title=section.parent.title if section.parent else None
                ).first()

                if not existing_section:
                    parent_section = None
                    if section.parent:
                        parent_section = Section.objects.filter(
                            title=section.parent.title,
                            courses=new_course
                        ).first()

                    # Create the new section
                    new_section = Section.objects.create(
                        parent=parent_section,
                        title=section.title,
                        courses=new_course,
                        order=section.order  # Copy the order field
                    )

                    # Copy the materials associated with the section
                    for material in section.materials.all():
                        Material.objects.create(
                            section=new_section,
                            title=material.title,
                            description=material.description,
                            created_at=material.created_at
                        )

                    # Copy the assessments associated with the section
                    for assessment in section.assessments.all():
                        new_assessment = Assessment.objects.create(
                            name=assessment.name,
                            section=new_section,
                            weight=assessment.weight,
                            description=assessment.description,
                            flag=assessment.flag,
                            duration_in_minutes=assessment.duration_in_minutes,
                            grade_range=grade_range_mapping.get(assessment.grade_range.id) if assessment.grade_range else None,
                            created_at=assessment.created_at
                        )

                        # Copy the questions associated with the assessment
                        for question in assessment.questions.all():
                            new_question = Question.objects.create(
                                assessment=new_assessment,
                                text=question.text,
                                created_at=question.created_at
                            )

                            # Copy the choices associated with the question
                            for choice in question.choices.all():
                                Choice.objects.create(
                                    question=new_question,
                                    text=choice.text,
                                    is_correct=choice.is_correct
                                )

                        # Copy the AskOra associated with the assessment
                        for ask_ora in assessment.ask_oras.all():
                            AskOra.objects.create(
                                assessment=new_assessment,
                                title=ask_ora.title,
                                question_text=ask_ora.question_text,
                                response_deadline=ask_ora.response_deadline,
                                created_at=ask_ora.created_at
                            )

            messages.success(request, f"Re-run of course '{new_course.course_name}' created successfully!")
            return redirect('courses:studio', id=new_course.id)

        else:
            messages.error(request, "There was an error with the form. Please correct the errors below.")
            print(form.errors)  # Debugging form errors

    else:
        form = CourseRerunForm(instance=course)
        form.fields['course_name_hidden'].initial = course.course_name
        form.fields['org_partner_hidden'].initial = course.org_partner

    return render(request, 'courses/course_reruns.html', {'form': form, 'course': course})

#add course price
def add_course_price(request, id):
    if not request.user.is_authenticated:
        return redirect(f"/login/?next={request.path}")

    course = None
    if hasattr(request.user, 'is_partner') and request.user.is_partner:
        course = get_object_or_404(Course, id=id, org_partner__user_id=request.user.id)
        existing_price = CoursePrice.objects.filter(course=course, price_type__isnull=False).first()
    else:
        messages.error(request, "Anda tidak memiliki izin untuk menambahkan harga ke kursus ini.")
        return redirect('courses:studio', id=id)

    if request.method == 'POST':
        print("✅ POST request received")
        print("📨 Data yang dikirim:", request.POST)

        form = CoursePriceForm(request.POST, user=request.user, course=course, instance=existing_price)
        if form.is_valid():
            print("✅ Form is valid")
            course_price = form.save(commit=False)
            course_price.course = course
            course_price.save()
            messages.success(request, "✅ Harga kursus berhasil disimpan!")
            print("✅ Data berhasil disimpan!")
            # Simpan ID instance di session
            request.session['last_course_price_id'] = course_price.id
            return redirect(reverse('courses:add_course_price', args=[course.id]))
        else:
            print("❌ Form is NOT valid")
            print(form.errors)
            for error in form.errors.get("__all__", []):
                messages.error(request, error)
    else:
        # Cek apakah ada instance dari session
        last_price_id = request.session.get('last_course_price_id')
        if last_price_id:
            try:
                last_price = CoursePrice.objects.get(id=last_price_id, course=course)
                form = CoursePriceForm(user=request.user, course=course, instance=last_price)
            except CoursePrice.DoesNotExist:
                form = CoursePriceForm(user=request.user, course=course, instance=existing_price)
            # Hapus session setelah digunakan
            request.session.pop('last_course_price_id', None)
        else:
            form = CoursePriceForm(user=request.user, course=course, instance=existing_price)

    return render(request, 'courses/course_price_form.html', {'form': form, 'course': course})


#instrcutor profile
def instructor_profile(request, username):
    # Fetch the instructor object
    instructor = get_object_or_404(Instructor, user__username=username)

    # Ensure that the instructor has a provider (Partner) with a slug in the related Universiti
    if not instructor.provider or not hasattr(instructor.provider.name, 'slug'):
        partner_slug = None
    else:
        partner_slug = instructor.provider.name.slug  # Access slug from Universiti model

    # Get the search term from the GET request (if any)
    search_term = request.GET.get('search', '')

    # Get the 'published' status from CourseStatus model
    published_status = CourseStatus.objects.get(status='published')  # Assuming 'status' field is used to store 'published'

    # Filter courses based on the search term, published status, and end_date
    courses = instructor.courses.filter(
        Q(course_name__icontains=search_term) &  # Search by course name
        Q(status_course=published_status) &      # Filter by 'published' status (corrected)
        Q(end_date__gte=datetime.now())          # Only courses that haven't ended yet
    ).order_by('start_date')  # Optional: Order by start date or any other field

    # Annotate each course with the total number of enrollments (participants)
    courses = courses.annotate(total_enrollments=Count('enrollments'))

    # Get the count of filtered courses
    courses_count = courses.count()

    # Calculate the total number of unique participants across all courses
    total_participants = courses.aggregate(total_participants=Count('enrollments__user', distinct=True))['total_participants']

    # Implement pagination: Show 6 courses per page
    paginator = Paginator(courses, 6)

    # Get the current page number from GET params (default to 1 if invalid)
    page_number = request.GET.get('page', 1)  # Default to page 1 if not specified

    # Ensure the page number is a positive integer
    try:
        page_number = int(page_number)
        if page_number < 1:
            page_number = 1  # If the page number is less than 1, set it to 1
    except ValueError:
        page_number = 1  # If the page number is not a valid integer, set it to 1

    # Get the page object
    try:
        page_obj = paginator.get_page(page_number)
    except EmptyPage:
        page_obj = paginator.get_page(1)  # If page number is out of range, show first page

    # Pass the instructor, courses, paginated courses, and courses count to the template
    return render(request, 'home/instructor_profile.html', {
        'instructor': instructor,
        'page_obj': page_obj,
        'courses_count': courses_count,  # Pass the count to the template
        'search_term': search_term,
        'partner_slug': partner_slug,  # Pass partner_slug to the template
        'total_participants': total_participants,  # Pass total participants to the template
    })
#ernroll

logger = logging.getLogger(__name__)

@login_required
@require_POST
def enroll_course(request, course_id):
    course = get_object_or_404(Course, id=course_id)
    partner = course.org_partner
    user = request.user
    today = timezone.now().date()

    # Cek apakah pengguna memiliki lisensi terkait
    licenses = user.licenses.all()  # Ambil semua lisensi pengguna
    logger.info(f"Checking licenses for user {user.email} in course {course.course_name} (ID: {course.id}): {licenses.values('name', 'start_date', 'expiry_date', 'status')}")
    if licenses.exists():  # Jika pengguna terkait lisensi
        active_license = user.licenses.filter(
            start_date__lte=today,
            expiry_date__gte=today,
            status=True
        ).exists()
        if not active_license:
            logger.error(f"No active license found for user {user.email} in course {course.course_name}")
            messages.error(request, "Lisensi Anda sudah tidak aktif atau tidak valid. Silakan hubungi admin untuk perpanjangan.")
            return redirect('learner:course_learn', username=user.username,id=course.id, slug=course.slug)

    # Pilih price type sesuai skema pembayaran
    price_type_map = {
        'buy_first': 'buy_first',
        'pay_for_exam': 'pay_for_exam',
        'pay_for_certificate': 'pay_for_certificate',
        'free': 'free',
        'subscription': 'free',
    }

    logger.info(f"Attempting to enroll user {user.username} in course {course_id}, payment_model: {course.payment_model}")
    try:
        price_type = PricingType.objects.get(name=price_type_map.get(course.payment_model, 'buy_first'))
        logger.info(f"Price type found: {price_type.name}")
    except PricingType.DoesNotExist:
        logger.error(f"Price type for {course.payment_model} not found.")
        messages.error(request, f"Tipe harga untuk model {course.payment_model} tidak ditemukan.")
        return redirect('courses:course_lms_detail', id=course_id, slug=course.slug)

    # Lanjutkan enrollment
    response = course.enroll_user(user, partner=partner, price_type=price_type)
    logger.info(f"Enroll response: {response}")

    if response["status"] == "success":
        messages.success(request, response["message"])
        return redirect('courses:course_learn', username=user.username, slug=course.slug)
    elif response["status"] == "error":
        if course.payment_model == 'buy_first' and "Payment required" in response["message"]:
            logger.info("Redirecting to payment for buy_first")
            return redirect('payments:process_payment', course_id=course.id)
        messages.error(request, response["message"])
    else:
        messages.info(request, response["message"])

    return redirect('courses:course_lms_detail', id=course_id, slug=course.slug)

def draft_lms(request, id):
    if not request.user.is_authenticated:
        return redirect("/login/?next=%s" % request.path)  # Redirect to login if not authenticated

    user = request.user
    course = None

    # Determine the course based on the user's role
    if request.user.is_superuser:
        course = get_object_or_404(Course, id=id)
    elif user.is_partner:
        course = get_object_or_404(Course, id=id, org_partner__user_id=user.id)
    elif user.is_instructor:
        course = get_object_or_404(Course, id=id, instructor__user_id=user.id)

    # If no course is found, redirect to the homepage
    if not course:
        return redirect('/')  # Redirect to the homepage if the course is not found

    # If the course is found, render the course page
    return render(request, 'courses/course_draft_view.html', {'course': course})


def get_client_ip(request):
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        return x_forwarded_for.split(',')[0]
    return request.META.get('REMOTE_ADDR')


@ratelimit(key='ip', rate='30/h', method='GET', block=True)
def course_lms_detail(request, id, slug):
    if getattr(request, 'limited', False):
        return HttpResponse("Terlalu banyak permintaan. Coba lagi nanti.", status=429)
    
    course = get_object_or_404(Course, id=id, slug=slug)

    try:
        published_status = CourseStatus.objects.get(status='published')
    except CourseStatus.DoesNotExist:
        return redirect('/')

    today = now().date()  # ✅ hanya panggil sekali

    is_enrolled = request.user.is_authenticated and course.enrollments.filter(user=request.user).exists()

    if not is_enrolled and (course.status_course != published_status or course.end_enrol < today):
        return redirect('/')

    # ✅ Hitung view unik per IP (bukan bot)
    user_agent = request.META.get('HTTP_USER_AGENT', '').lower()
    if 'bot' not in user_agent:
        ip = get_client_ip(request)
        if not CourseViewIP.objects.filter(course=course, ip_address=ip).exists():
            CourseViewIP.objects.create(course=course, ip_address=ip)
            Course.objects.filter(id=course.id).update(view_count=F('view_count') + 1)

        view_log, created = CourseViewLog.objects.get_or_create(course=course, date=today)
        if not created:
            CourseViewLog.objects.filter(pk=view_log.pk).update(count=F('count') + 1)

    similar_courses = Course.objects.filter(
        category=course.category,
        status_course=published_status,
        end_enrol__gte=today
    ).exclude(id=course.id)[:5]

    comments = CourseComment.objects.filter(course=course, parent=None).order_by('-created_at')
    for comment in comments:
        for reply in comment.replies.all().order_by('-created_at'):
            reply.sub_replies = reply.replies.all().order_by('-created_at')

    section_data = Section.objects.filter(parent=None, courses=course).prefetch_related('materials')
    total_sections = section_data.count()
    total_materials = sum(section.materials.count() for section in section_data)
    total_students = course.enrollments.count()
    total_effort_hours = course.hour if course.hour else "N/A"

    instructor = course.instructor
    instructor_courses = Course.objects.filter(
        instructor=instructor,
        status_course=published_status,
        end_enrol__gte=today
    )

    instructor_total_courses = instructor_courses.count()
    instructor_total_students = sum(c.enrollments.count() for c in instructor_courses)
    instructor_total_effort_hours = sum(int(c.hour) for c in instructor_courses if c.hour and str(c.hour).isdigit())
    instructor_sections = Section.objects.filter(courses__in=instructor_courses, parent=None).prefetch_related('materials')
    instructor_total_sections = instructor_sections.count()
    instructor_total_materials = sum(s.materials.count() for s in instructor_sections)

    reviews = CourseRating.objects.filter(course=course).order_by('-created_at')
    paginator = Paginator(reviews, 5)
    page_obj = paginator.get_page(request.GET.get('page'))

    user_has_rated = request.user.is_authenticated and CourseRating.objects.filter(user=request.user, course=course).exists()

    average_rating = course.average_rating
    full_stars = int(average_rating)
    half_star = (average_rating % 1) >= 0.5
    empty_stars = 5 - (full_stars + (1 if half_star else 0))

    course_price = course.get_course_price()

    return render(request, 'home/course_detail.html', {
        'course': course,
        'is_enrolled': is_enrolled,
        'similar_courses': similar_courses,
        'comments': comments,
        'section_data': section_data,
        'total_sections': total_sections,
        'total_materials': total_materials,
        'total_students': total_students,
        'total_effort_hours': total_effort_hours,
        'instructor': instructor,
        'instructor_total_courses': instructor_total_courses,
        'instructor_total_students': instructor_total_students,
        'instructor_total_effort_hours': instructor_total_effort_hours,
        'instructor_total_sections': instructor_total_sections,
        'instructor_total_materials': instructor_total_materials,
        'reviews': page_obj,
        'user_has_rated': user_has_rated,
        'range': range(1, 6),
        'full_star_range': range(full_stars),
        'half_star': half_star,
        'empty_star_range': range(empty_stars),
        'average_rating': average_rating,
        'course_price': course_price,
    })


logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

def course_instructor(request, id):
    if not request.user.is_authenticated:
        return redirect(f"/login/?next={request.path}")
    
    user = request.user
    course = None

    if user.is_superuser:
        course = get_object_or_404(Course, id=id)
    elif user.is_partner:
        course = get_object_or_404(Course, id=id, org_partner__user_id=user.id)
    elif user.is_instructor:
        messages.error(request, "You do not have permission to manage this course.")
        return redirect('/courses')

    if not course:
        return redirect('/courses')

    if request.method == 'POST':
        logger.debug(f"Raw POST data: {request.POST}")
        form = CourseInstructorForm(request.POST, instance=course, request=request)
        if form.is_valid():
            logger.debug(f"Cleaned data: {form.cleaned_data}")
            form.save()
            messages.success(request, "Instructor has been successfully added to the course.")
            return redirect('courses:course_instructor', id=course.id)
        else:
            logger.debug(f"Form errors: {form.errors}")
    else:
        form = CourseInstructorForm(instance=course, request=request)

    return render(request, 'instructor/course_instructor.html', {'course': course, 'form': form})

# Fungsi untuk pencarian instruktur menggunakan Select2 (AJAX)


def search_instructors(request):
    q = request.GET.get('q', '')
    if request.user.is_authenticated:
        if request.user.is_superuser:
            instructors = Instructor.objects.filter(user__username__icontains=q)
        elif request.user.is_partner:
            instructors = Instructor.objects.filter(user__username__icontains=q, provider__user=request.user)
        else:
            instructors = Instructor.objects.none()

        results = [{'id': i.id, 'text': str(i.user.username)} for i in instructors[:10]]
        logger.debug(f"Search results: {results}")
        return JsonResponse({'results': results})
    return JsonResponse({'results': []})

#create grade
#@login_required
def course_grade(request, id):
    # Check if the user is authenticated
    if not request.user.is_authenticated:
        return redirect("/login/?next=%s" % request.path)
    

    user = request.user
    course = None

  
    # Determine the course based on the user's role
    if request.user.is_superuser:
        course = get_object_or_404(Course, id=id)
    elif user.is_partner:
        #course = Course.objects.filter(id=id, org_partner_id=request.user.id).first()
        course = get_object_or_404(Course, id=id, org_partner__user_id=user.id)
        #print(course)
    elif user.is_instructor:
        course = get_object_or_404(Course, id=id, instructor__user_id=user.id)
    # If no course is found, redirect to the courses list page
        #print(course)
    if not course:
        return redirect('/courses')
    
    course = get_object_or_404(Course, id=id)
     # Retrieve sections related to this course
    sections = Section.objects.filter(courses=course)  # Get all sections related to the course
   # Ensure grade ranges exist; create defaults if necessary
    grade_fail, created_fail = course.grade_ranges.get_or_create(
        name="Fail",
        defaults={"min_grade": 0, "max_grade": 59},
    )
    grade_pass, created_pass = course.grade_ranges.get_or_create(
        name="Pass",
        defaults={"min_grade": 60, "max_grade": 100},
    )

    # Compute widths for display
    total_grade_range = 100
    fail_width = (grade_fail.max_grade / total_grade_range) * 100
    pass_width = 100 - fail_width

    # Compute grade ranges
    fail_range_max = int(grade_fail.max_grade)
    pass_range_min = fail_range_max + 1

     # Retrieve the sections for the course
    sections = Section.objects.filter(courses=course)  # Get all sections related to this course

    # Retrieve all assessments associated with these sections
    assessments = Assessment.objects.filter(section__in=sections)
    total_weight = sum(assessment.weight for assessment in assessments)
    
    return render(request, 'courses/course_grade.html', {
        'course': course,
        'sections': sections,  # Pass the sections
        "fail_width": fail_width,
        "pass_width": pass_width,
        "fail_range_max": fail_range_max,
        "pass_range_min": pass_range_min,
        'assessments': assessments,  # Pass assessments to the template
        'total_weight': total_weight,
    })


#@login_required
def update_grade_range(request, id):
    # Check if the user is authenticated
    if not request.user.is_authenticated:
        return redirect("/login/?next=%s" % request.path)
    
    user = request.user
    course = None

     # Determine the course based on the user's role
    if request.user.is_superuser:
        course = get_object_or_404(Course, id=id)
    elif user.is_partner:
        #course = Course.objects.filter(id=id, org_partner_id=request.user.id).first()
        course = get_object_or_404(Course, id=id, org_partner__user_id=user.id)
        #print(course)
    elif user.is_instructor:
        course = get_object_or_404(Course, id=id, instructor__user_id=user.id)
    # If no course is found, redirect to the courses list page
        #print(course)
    if not course:
        # Instructors can delete sections only for their own courses
        if course.instructor.user_id != request.user.id:
            return JsonResponse({'status': 'error', 'message': 'Permission denied.'})



    if request.method == "POST":
        try:
            # Fetch course
            course = get_object_or_404(Course, id=id)

            # Get Fail and Pass widths from the AJAX request
            fail_width = Decimal(request.POST.get("fail_width", 50))  # Example: 40.0
            pass_width = Decimal(request.POST.get("pass_width", 50))  # Example: 60.0

            # Get Fail and Pass grade ranges
            grade_fail = course.grade_ranges.filter(name="Fail").first()
            grade_pass = course.grade_ranges.filter(name="Pass").first()

            if not grade_fail or not grade_pass:
                return JsonResponse({"success": False, "message": "Fail or Pass grade range not found!"})

            # Dynamically calculate and update ranges
            grade_fail.max_grade = int((fail_width / 100) * 100)  # Fail max_grade = % of total grade
            grade_pass.min_grade = grade_fail.max_grade + 1  # Pass starts right after Fail's max_grade
            grade_pass.max_grade = 100  # Pass always ends at 100

            # Save updates
            grade_fail.save()
            grade_pass.save()

            return JsonResponse({"success": True, "message": "Grade ranges updated dynamically!"})

        except Exception as e:
            return JsonResponse({"success": False, "message": str(e)})
    return JsonResponse({"success": False, "message": "Invalid request"})


#creat assesment type name
#@login_required
@csrf_exempt
def create_assessment(request, idcourse, idsection):
    # Check if the user is authenticated
    if not request.user.is_authenticated:
        return redirect("/login/?next=%s" % request.path)

    # Determine the course based on the user's role
    if request.user.is_superuser:
        course = get_object_or_404(Course, id=idcourse)
    elif request.user.is_partner:
        # Ensure the course is associated with the partner
        course = get_object_or_404(Course, id=idcourse, org_partner__user_id=request.user.id)
    elif request.user.is_instructor:
        # Ensure the course is associated with the instructor
        course = get_object_or_404(Course, id=idcourse, instructor__user_id=request.user.id)
    else:
        # Unauthorized access
        messages.error(request, "You do not have permission to create assessments for this course.")
        return redirect('courses:home')  # Redirect to a safe page

    # Ensure the section belongs to the course
    section = get_object_or_404(Section, id=idsection, courses=course)

    if request.method == 'POST':
        form = AssessmentForm(request.POST)
        if form.is_valid():
            # Convert new_weight to Decimal
            new_weight = Decimal(form.cleaned_data['weight'])
            # Calculate total weight for the course
            total_weight = Assessment.objects.filter(section__courses=course).aggregate(Sum('weight'))['weight__sum']
            total_weight = total_weight if total_weight is not None else Decimal('0')

            if total_weight + new_weight > Decimal('100'):
                messages.error(request, "Total bobot untuk penilaian dalam course ini tidak boleh melebihi 100")
                return render(request, 'courses/course_assessement.html', {'form': form, 'course': course, 'section': section})

            # Create the assessment instance but don't save it yet
            assessment = form.save(commit=False)
            # Set the section field
            assessment.section = section
            # Save the assessment
            assessment.save()
            messages.success(request, "Assessment created successfully!")
            return redirect('courses:view-question', idcourse=course.id, idsection=section.id, idassessment=assessment.id)
    else:
        form = AssessmentForm()

    return render(request, 'courses/course_assessement.html', {'form': form, 'course': course, 'section': section})

#edit assesment type name
#@login_required
@csrf_exempt
def edit_assessment(request, idcourse, idsection, idassessment):
    # Check if the user is authenticated
    if not request.user.is_authenticated:
        return redirect("/login/?next=%s" % request.path)

    # Determine the course based on the user's role
    if request.user.is_superuser:
        course = get_object_or_404(Course, id=idcourse)
    elif request.user.is_partner:
        course = get_object_or_404(Course, id=idcourse, org_partner__user_id=request.user.id)
    elif request.user.is_instructor:
        course = get_object_or_404(Course, id=idcourse, instructor__user_id=request.user.id)
    else:
        # Unauthorized access
        messages.error(request, "You do not have permission to edit assessments for this course.")
        return redirect('courses:home')  # Redirect to a safe page

    # Ensure the section belongs to the course
    section = get_object_or_404(Section, id=idsection, courses=course)

    # Fetch the assessment based on its ID
    assessment = get_object_or_404(Assessment, id=idassessment, section=section)

    if request.method == 'POST':
        form = AssessmentForm(request.POST, instance=assessment)  # Populate the form with current assessment data
        if form.is_valid():
            # Save without committing
            assessment = form.save(commit=False)

            # Check total weight
            total_weight = Assessment.objects.filter(section=section).exclude(id=idassessment).aggregate(Sum('weight'))['weight__sum'] or Decimal('0')
            if total_weight + Decimal(form.cleaned_data['weight']) > Decimal('100'):
                messages.error(request, "Total bobot untuk penilaian dalam section ini tidak boleh melebihi 100")
                return render(request, 'courses/course_assessement_edit.html', {
                    'form': form,
                    'course': course,
                    'section': section,
                    'assessment': assessment,
                })

            # Now save the assessment
            assessment.save()
            messages.warning(request, "Assessment updated successfully!")
            return redirect('courses:view-question', idcourse=course.id, idsection=section.id, idassessment=assessment.id)

    else:
        # Create an empty form or pre-populated form with existing data
        form = AssessmentForm(instance=assessment)

    return render(request, 'courses/course_assessement_edit.html', {
        'form': form,
        'course': course,
        'section': section,
        'assessment': assessment,
    })

#delete assesment type name
#@login_required
@csrf_exempt
def delete_assessment(request, idcourse, idsection, idassessment):
    # Check if the user is authenticated
    if not request.user.is_authenticated:
        return redirect("/login/?next=%s" % request.path)
    # Determine the course based on the user's role
    if request.user.is_superuser:
        course = get_object_or_404(Course, id=idcourse)
    elif request.user.is_partner:
        # Ensure the course is associated with the partner
        course = get_object_or_404(Course, id=idcourse, org_partner__user_id=request.user.id)
    elif request.user.is_instructor:
        # Ensure the course is associated with the instructor
        course = get_object_or_404(Course, id=idcourse, instructor__user_id=request.user.id)
    else:
        # Unauthorized access
        messages.error(request, "You do not have permission to delete assessments for this course.")
        return redirect('courses:home')  # Redirect to a safe page

    # Ensure the section belongs to the course
    section = get_object_or_404(Section, id=idsection, courses=course)

    # Fetch the assessment
    assessment = get_object_or_404(Assessment, id=idassessment, section=section)

    if request.method == 'POST':
        # Perform the deletion
        assessment.delete()
        messages.success(request, "Assessment deleted successfully!")
        return redirect('courses:studio', id=course.id)

    # Render confirmation page for GET requests
    return render(request, 'courses/confirm_delete_assessment.html', {
        'course': course,
        'section': section,
        'assessment': assessment,
    })


#edit question and choice
#@login_required
@csrf_exempt
def edit_question(request, idcourse, idquestion, idsection, idassessment):
    # Check if the user is authenticated
    if not request.user.is_authenticated:
        return redirect("/login/?next=%s" % request.path)
    # Determine the course based on the user's role
    if request.user.is_superuser:
        course = get_object_or_404(Course, id=idcourse)
    elif request.user.is_partner:
        # Ensure the course is associated with the partner
        course = get_object_or_404(Course, id=idcourse, org_partner__user_id=request.user.id)
    elif request.user.is_instructor:
        # Ensure the course is associated with the instructor
        course = get_object_or_404(Course, id=idcourse, instructor__user_id=request.user.id)
    else:
        # Unauthorized access
        messages.error(request, "You do not have permission to edit questions for this course.")
        return redirect('courses:home')  # Redirect to a safe page

    # Ensure the section belongs to the course
    section = get_object_or_404(Section, id=idsection, courses=course)

    # Ensure the assessment belongs to the section
    assessment = get_object_or_404(Assessment, id=idassessment, section=section)

    # Ensure the question belongs to the assessment
    question = get_object_or_404(Question, id=idquestion, assessment=assessment)

    # Pass the assessment to the forms
    form = QuestionForm(request.POST or None, instance=question, assessment=assessment)
    choice_formset = ChoiceFormSet(request.POST or None, instance=question)

    # Pass assessment to each form in the formset
    for choice_form in choice_formset.forms:
        choice_form.fields['text'].widget = (
            CKEditor5Widget("extends") if assessment.flag else forms.TextInput(attrs={'class': 'form-control'})
        )

    if request.method == 'POST':
        if form.is_valid() and choice_formset.is_valid():
            # Save the question form
            question = form.save(commit=False)
            question.section = section
            question.save()

            # Save the formset
            choice_formset.instance = question
            choice_formset.save()

            messages.success(request, "Question and choices updated successfully!")

            # Check if 'save and add another' button was clicked
            if 'save_and_add_another' in request.POST:
                return redirect('courses:create_question', idcourse=course.id, idsection=section.id, idassessment=assessment.id)

            return redirect('courses:view-question', idcourse=course.id, idsection=section.id, idassessment=assessment.id)
        else:
            print("Form errors:", form.errors)
            print("Formset errors:", [choice_form.errors for choice_form in choice_formset.forms])
            messages.error(request, "There was an error updating the question. Please check your inputs.")

    return render(request, 'courses/edit_question.html', {
        'form': form,
        'choice_formset': choice_formset,
        'course': course,
        'section': section,
        'assessment': assessment,
    })

#delete question
@csrf_exempt
def delete_question(request, idcourse, idquestion, idsection, idassessment):
    # Check if the user is authenticated
    if not request.user.is_authenticated:
        return redirect("/login/?next=%s" % request.path)

    # Determine the course based on the user's role
    if request.user.is_superuser:
        course = get_object_or_404(Course, id=idcourse)
    elif request.user.is_partner:
        # Ensure the course is associated with the partner
        course = get_object_or_404(Course, id=idcourse, org_partner__user_id=request.user.id)
    elif request.user.is_instructor:
        # Ensure the course is associated with the instructor
        course = get_object_or_404(Course, id=idcourse, instructor__user_id=request.user.id)
    else:
        # Unauthorized access
        messages.error(request, "You do not have permission to delete questions for this course.")
        return redirect('courses:home')  # Redirect to a safe page

    # Ensure the section belongs to the course
    section = get_object_or_404(Section, id=idsection, courses=course)

    # Ensure the assessment belongs to the section
    assessment = get_object_or_404(Assessment, id=idassessment, section=section)

    # Ensure the question belongs to the assessment
    question = get_object_or_404(Question, id=idquestion, assessment=assessment)

    if request.method == 'POST':
        try:
            # Deleting the question
            question.delete()
            messages.success(request, "Question deleted successfully.")
        except Exception as e:
            messages.error(request, f"Error deleting question: {e}")

        # Redirecting back to the page with the list of questions
        return redirect('courses:view-question', idcourse=course.id, idsection=section.id, idassessment=assessment.id)

    return render(request, 'courses/view_question.html', {
        'course': course,
        'section': section,
        'assessment': assessment,
    })

#create question and choice
#@login_required
@csrf_exempt
def create_question_view(request, idcourse, idsection, idassessment):
    # Check if the user is authenticated
    if not request.user.is_authenticated:
        return redirect("/login/?next=%s" % request.path)
    
    # Determine the course based on the user's role
    if request.user.is_superuser:
        course = get_object_or_404(Course, id=idcourse)
    elif request.user.is_partner:
        # Ensure the course is associated with the partner
        course = get_object_or_404(Course, id=idcourse, org_partner__user_id=request.user.id)
    elif request.user.is_instructor:
        # Ensure the course is associated with the instructor
        course = get_object_or_404(Course, id=idcourse, instructor__user_id=request.user.id)
    else:
        # Unauthorized access
        messages.error(request, "You do not have permission to create questions for this course.")
        return redirect('courses:home')  # Redirect to a safe page

    # Ensure the section belongs to the course
    section = get_object_or_404(Section, id=idsection, courses=course)

    # Ensure the assessment belongs to the section
    assessment = get_object_or_404(Assessment, id=idassessment, section=section)

    # Initialize forms
    question_form = QuestionForm(request.POST or None, assessment=assessment)
    choice_formset = ChoiceFormSet(request.POST or None, instance=Question())

    # Pass assessment to each form in the formset
    for choice_form in choice_formset.forms:
        choice_form.fields['text'].widget = (
            CKEditor5Widget("extends") if assessment.flag else forms.TextInput(attrs={'class': 'form-control'})
        )

    if request.method == 'POST':
        if question_form.is_valid() and choice_formset.is_valid():
            # Save question instance
            question = question_form.save(commit=False)
            question.section = section
            question.assessment = assessment
            question.save()

            # Link and save choices
            choice_formset.instance = question
            choice_formset.save()

            messages.success(request, "Question and choices created successfully!")

            # Check if 'save and add another' button was clicked
            if 'save_and_add_another' in request.POST:
                return redirect('courses:create_question', idcourse=course.id, idsection=section.id, idassessment=assessment.id)

            # Redirect to a view or list of questions
            return redirect('courses:view-question', idcourse=course.id, idsection=section.id, idassessment=assessment.id)
        else:
            messages.error(request, "There was an error saving the question. Please correct the errors below.")

    # For GET requests or if forms are invalid
    return render(request, 'courses/create_question.html', {
        'course': course,
        'section': section,
        'assessment': assessment,
        'question_form': question_form,
        'choice_formset': choice_formset,
    })



#view question
#@login_required
@csrf_exempt
def question_view(request, idcourse, idsection, idassessment):
    # Check if the user is authenticated
    if not request.user.is_authenticated:
        return redirect("/login/?next=%s" % request.path)
    
    # Determine the course based on the user's role
    if request.user.is_superuser:
        course = get_object_or_404(Course, id=idcourse)
    elif request.user.is_partner:
        # Ensure the course is associated with the partner
        course = get_object_or_404(Course, id=idcourse, org_partner__user_id=request.user.id)
    elif request.user.is_instructor:
        # Ensure the course is associated with the instructor
        course = get_object_or_404(Course, id=idcourse, instructor__user_id=request.user.id)
    else:
        # Unauthorized access
        messages.error(request, "You do not have permission to view questions for this course.")
        return redirect('courses:home')  # Redirect to a safe page

    # Ensure the section belongs to the course
    section = get_object_or_404(Section, id=idsection, courses=course)

    # Ensure the assessment belongs to the section
    assessment = get_object_or_404(
        Assessment.objects.prefetch_related(
            'questions__choices',  # prefetch related choices for multiple-choice questions
            'ask_oras', #prefetch related ask_oras for open-response questions
            'lti_tools'  # prefetch related lti for lti_tools
        ),
        id=idassessment,
        section=section
    )

    return render(request, 'courses/view_question.html', {
        'course': course,
        'section': section,
        'assessment': assessment,
    })





#upprove user request
#@login_required
def instructor_check(request, instructor_id):
    # Check if the user is authenticated
    if not request.user.is_authenticated:
        return redirect("/login/?next=%s" % request.path)
    # Fetch the instructor object
    instructor = get_object_or_404(Instructor, id=instructor_id)
    
    # Check if the user has permission to approve (e.g., the user must be the provider)
    if request.user.is_partner and instructor.provider.user == request.user:
        # Update instructor status to "Approved"
        instructor.status = 'Approved'
        instructor.save()  # Save the status change

        # Now update the user's `is_partner` field to True
        user = instructor.user  # Get the related User object
        
        # Set is_partner to True
        user.is_instructor = True
        user.save()  # Save the user after the update

        # Success message
        messages.success(request, "Instructor has been approved.")
        
    else:
        # Error message if the user doesn't have permission
        messages.error(request, "You do not have permission to approve this instructor.")

    # Redirect to the instructor list or another page after approval
    return redirect('courses:instructor_view')  # Change this URL to your desired location


#instructor detail
#@login_required
def instructor_detail(request, id):
    # Check if the user is authenticated
    if not request.user.is_authenticated:
        return redirect("/login/?next=%s" % request.path)
    
    # Fetch the instructor object by the provided ID
    instructor = get_object_or_404(Instructor, id=id)

    # Ensure that the instructor has a provider (Partner) with a slug in the related Universiti
    if not instructor.provider or not hasattr(instructor.provider.name, 'slug'):
        # Handle the case where there is no provider or slug
        partner_slug = None
    else:
        partner_slug = instructor.provider.name.slug  # Access slug from Universiti model

    # Get the search term from the GET request (if any)
    search_term = request.GET.get('search', '')

    # Filter courses based on the search term
    courses = instructor.courses.filter(
        Q(course_name__icontains=search_term)  # Search by course name only
    ).order_by('start_date')  # Optional: Order by start date or any other field

    # Get the count of filtered courses
    courses_count = courses.count()

       # Hitung jumlah total siswa yang terdaftar di semua kursus yang diberikan instruktur ini
    total_students = Enrollment.objects.filter(course__in=courses).values('user').annotate(num_students=Count('user')).count()

    # Add a participant count for each course
    # We're using annotate to count the number of enrollments for each course
    courses = courses.annotate(participants_count=Count('enrollments'))

    # Implement pagination: Show 6 courses per page
    paginator = Paginator(courses, 6)

    # Get the current page number from GET params (default to 1 if invalid)
    page_number = request.GET.get('page', 1)  # Default to page 1 if not specified

    # Ensure the page number is a positive integer
    try:
        page_number = int(page_number)
        if page_number < 1:
            page_number = 1  # If the page number is less than 1, set it to 1
    except ValueError:
        page_number = 1  # If the page number is not a valid integer, set it to 1

    # Get the page object
    try:
        page_obj = paginator.get_page(page_number)
    except EmptyPage:
        page_obj = paginator.get_page(1)  # If page number is out of range, show first page

    # Create the context dictionary to pass to the template
    context = {
        'instructor': instructor,
        'page_obj': page_obj,  # Pass the paginated courses to the template
        'courses_count': courses_count,  # Total number of filtered courses
        'search_term': search_term,  # Pass the search query to the template
        'partner_slug': partner_slug,  # Pass the partner slug to the template
        'total_students': total_students,
    }

    # Render the instructor_detail template with the context
    return render(request, 'instructor/instructor_detail.html', context)

#view instructor
#@login_required

def instructor_view(request):
    # Check if the user is authenticated
    if not request.user.is_authenticated:
        return redirect("/login/?next=%s" % request.path)

    # Get search query from GET parameters
    search_query = request.GET.get('q', '').strip()
    
    # Define base queryset based on user role
    if request.user.is_superuser:
        # Admin sees all instructors
        instructors = Instructor.objects.all().annotate(num_courses=Count('courses'))
    elif request.user.is_partner:
        # Partner sees instructors linked to their provider
        instructors = Instructor.objects.filter(provider__user=request.user).annotate(num_courses=Count('courses'))
    elif request.user.is_instructor:
        messages.error(request, "You do not have permission to view this instructor list.")
        return render(request, 'instructor/instructor_list.html', {'instructors': []})
    else:
        messages.error(request, "You do not have permission to view this instructor list.")
        return render(request, 'instructor/instructor_list.html', {'instructors': []})

    # Apply search filter if query exists
    if search_query:
        instructors = instructors.filter(
            Q(user__username__icontains=search_query) | Q(user__email__icontains=search_query)
        )  # Pencarian berdasarkan username atau email dari model User

    # Pagination
    items_per_page = 10  # Jumlah item per halaman
    paginator = Paginator(instructors, items_per_page)
    page_number = request.GET.get('page')

    try:
        instructors_page = paginator.page(page_number)
    except PageNotAnInteger:
        instructors_page = paginator.page(1)
    except EmptyPage:
        instructors_page = paginator.page(paginator.num_pages)

    # Context untuk template
    context = {
        'instructors': instructors_page,
        'search_query': search_query,
        'paginator': paginator,
    }

    return render(request, 'instructor/instructor_list.html', context)

#delete instructor
#@login_required
def delete_instructor(request, instructor_id):
    # Check if the user is authenticated
    if not request.user.is_authenticated:
        return redirect("/login/?next=%s" % request.path)
   
    # Fetch the instructor object
    instructor = get_object_or_404(Instructor, id=instructor_id)
    
    # Ensure the user has permission to delete the instructor
    if request.user.is_partner and instructor.provider.user == request.user:
        instructor.delete()
        messages.success(request, "Instructor deleted successfully.")
    else:
        messages.error(request, "You do not have permission to delete this instructor.")

    # Redirect to the list of instructors
    return redirect('courses:instructor_view')


#intructor form for new request
#@login_required
def become_instructor(request):
    # Check if the user is authenticated
    if not request.user.is_authenticated:
        return redirect("/login/?next=%s" % request.path)
    # Check if the user is already an instructor
    try:
        application = Instructor.objects.get(user=request.user)
        if application.status == "Pending":
            
            messages.info(request, "Your application is under review.")
        elif application.status == "Approved":
            messages.success(request, "You are already an instructor!")
        return redirect('authentication:dasbord')
    except Instructor.DoesNotExist:
        if request.method == "POST":
            form = InstructorForm(request.POST)
            if form.is_valid():
                application = form.save(commit=False)
                application.user = request.user
                application.save()
                messages.success(request, "Your application has been submitted!")
                return redirect('authentication:dasbord')
        else:
            form = InstructorForm()

    return render(request, 'home/become_instructor.html', {'form': form})

#add course team
#@login_required

def course_team(request, id):
    # Check if the user is authenticated
    if not request.user.is_authenticated:
        return redirect("/login/?next=%s" % request.path)
    # Fetch the course object
    user = request.user

    # Retrieve the course based on the provided ID

    course = get_object_or_404(Course, id=id)


    # Check if the user is either the instructor or an organization partner

    is_instructor = course.instructor is not None and course.instructor.user == user

    is_partner = course.org_partner is not None and course.org_partner.user == user
    is_superuser = user.is_superuser

    if not (is_instructor or is_partner or is_superuser):

        return redirect('/courses')  # Redirect if the user is not authorized


    if request.method == 'POST':

        form = TeamMemberForm(request.POST)

        if form.is_valid():

            email = form.cleaned_data['email']  # Get the email from the form

            try:

                user_instance = CustomUser.objects.get(email=email)  # Retrieve the User instance

                team_member = TeamMember(course=course, user=user_instance)

                team_member.save()  # Save the new team member

                return redirect('courses:course_team', id=course.id)

            except CustomUser.DoesNotExist:

                form.add_error('email', "No user found with this email.")  # Add an error if user not found

    else:

        form = TeamMemberForm()


    team_members = course.team_members.all()


    return render(request, 'courses/course_team.html', {

        'course': course,

        'form': form,

        'team_members': team_members,

    })
#remove team
#@login_required

def remove_team_member(request, member_id):
    # Check if the user is authenticated
    if not request.user.is_authenticated:
        return redirect("/login/?next=%s" % request.path)
    # Check if the user is authorized to access the course
    team_member = get_object_or_404(TeamMember, id=member_id)

    course_id = team_member.course.id


    # Check if the user is the instructor or the organization partner

    is_instructor = getattr(team_member.course.instructor, 'user', None) == request.user

    is_partner = getattr(team_member.course.org_partner, 'user', None) == request.user
    is_superuser = request.user.is_superuser
    
    if is_instructor or is_partner or is_superuser:

        team_member.delete()  # Remove the team member


    return redirect('courses:course_team', id=course_id)  # Redir

#course profile
@csrf_exempt  # Be cautious with this decorator; it's better to avoid using it if unnecessary
def course_profile(request, id):
    # Check if the user is authenticated
    if not request.user.is_authenticated:
        return redirect("/login/?next=%s" % request.path)
    # Get the course based on the user's role
    user = request.user
    course = None
    # Determine the course based on the user's role
    if request.user.is_superuser:
        course = get_object_or_404(Course, id=id)
    elif user.is_partner:
        #course = Course.objects.filter(id=id, org_partner_id=request.user.id).first()
        course = get_object_or_404(Course, id=id, org_partner__user_id=user.id)
        print(course)
    elif user.is_instructor:
        course = get_object_or_404(Course, id=id, instructor__user_id=user.id)
    # If no course is found, redirect to the courses list page
        print(course)
    if not course:
        return redirect('/courses')

    # Handle POST request to update course data
    if request.method == 'POST':
        form = ProfilForm(request.POST,request.FILES, instance=course)
        if form.is_valid():
            form.save()  # Save the updated course data
            
            #print(reverse('course_profile', kwargs={'id': course.id}))
            return redirect('courses:course_profile', id=course.id)  # Redirect back to the updated course profile
    else:
        form = ProfilForm(instance=course)  # For GET requests, display the form with existing course data

    return render(request, 'courses/course_profile.html', {'course': course, 'form': form})




#add section
#@login_required
@csrf_exempt
def create_section(request, idcourse):
    # Check if the user is authenticated
    if not request.user.is_authenticated:
        return redirect("/login/?next=%s" % request.path)
    # Get the course based on the user's role
    if request.method == "POST":
        # Check user permissions
        if request.user.is_superuser:
            course = get_object_or_404(Course, id=idcourse)
        elif request.user.is_partner:
            course = get_object_or_404(Course, id=idcourse, org_partner__user_id=request.user.id)
        elif request.user.is_instructor:
            course = get_object_or_404(Course, id=idcourse, instructor__user_id=request.user.id)
        else:
            return JsonResponse({'status': 'error', 'message': 'Permission denied.'})

        form = SectionForm(request.POST)
        if form.is_valid():
            section = form.save(commit=False)
            section.courses = course
            section.save()
            return JsonResponse({'status': 'success', 'message': 'Section created successfully!'})
        else:
            return JsonResponse({'status': 'error', 'message': 'Form is not valid', 'errors': form.errors})

    return JsonResponse({'status': 'error', 'message': 'Invalid request method.'})



# Delete section
#@login_required
@csrf_exempt
def delete_section(request, pk):
    # Check if the user is authenticated
    if not request.user.is_authenticated:
        return redirect("/login/?next=%s" % request.path)
    # Fetch the section
    section = get_object_or_404(Section, pk=pk)
    course = section.courses  # Use the correct relationship field name

    # Check user roles
    if request.user.is_superuser:
        # Superusers can delete any section
        pass
    elif request.user.is_partner:
        # Partners can delete sections only for their associated courses
        if course.org_partner.user_id != request.user.id:
            return JsonResponse({'status': 'error', 'message': 'Permission denied.'})
    elif request.user.is_instructor:
        # Instructors can delete sections only for their own courses
        if course.instructor.user_id != request.user.id:
            return JsonResponse({'status': 'error', 'message': 'Permission denied.'})
    else:
        # Unauthorized user
        return JsonResponse({'status': 'error', 'message': 'Permission denied.'})

    # If role check passes, delete the section
    if request.method == 'POST':
        section.delete()
        return JsonResponse({'status': 'success', 'message': 'Section deleted!'})
    else:
        return JsonResponse({'status': 'error', 'message': 'Invalid request method.'})


# Update Section
# Update Section with Role-Based Access
#@login_required
@csrf_exempt
def update_section(request, pk):
    # Check if the user is authenticated
    if not request.user.is_authenticated:
        return redirect("/login/?next=%s" % request.path)
    # Fetch the section
    section = get_object_or_404(Section, pk=pk)
    course = section.courses  # Use the correct relationship field name

    # Check user roles
    if request.user.is_superuser:
        # Superusers can update any section
        pass
    elif request.user.is_partner:
        # Partners can update sections only for their associated courses
        if course.org_partner.user_id != request.user.id:
            return JsonResponse({'status': 'error', 'message': 'Permission denied.'})
    elif request.user.is_instructor:
        # Instructors can update sections only for their own courses
        if course.instructor.user_id != request.user.id:
            return JsonResponse({'status': 'error', 'message': 'Permission denied.'})
    else:
        # Unauthorized user
        return JsonResponse({'status': 'error', 'message': 'Permission denied.'})

    if request.method == "POST":
        # Handle form submission
        form = SectionForm(request.POST, instance=section)
        if form.is_valid():
            # Save the updated section
            form.save()
            return JsonResponse({'status': 'success', 'message': 'Section updated successfully!'})
        else:
            # Return specific form errors for debugging
            return JsonResponse({'status': 'error', 'message': 'Form is not valid', 'errors': form.errors})
    return JsonResponse({'status': 'error', 'message': 'Invalid request method.'})



#add matrial course
#@login_required
@csrf_exempt
def add_matrial(request, idcourse, idsection):
    # Check if the user is authenticated
    if not request.user.is_authenticated:
        return redirect("/login/?next=%s" % request.path)
    # Determine the course based on the user's role
    if request.user.is_superuser:
        course = get_object_or_404(Course, id=idcourse)
    elif request.user.is_partner:
        # Ensure the course is associated with the partner
        course = get_object_or_404(Course, id=idcourse, org_partner__user_id=request.user.id)
    elif request.user.is_instructor:
        # Ensure the course is associated with the instructor
        course = get_object_or_404(Course, id=idcourse, instructor__user_id=request.user.id,instructor__status='Approved')
    else:
        messages.error(request, "You do not have permission to add materials to this course.")
        return redirect('courses:home')  # Redirect to a safe page for unauthorized users

    # Fetch the section (update the field name to 'courses')
    section = get_object_or_404(Section, id=idsection, courses=course)

    if request.method == 'POST':
        # Handle form submission
        form = MatrialForm(request.POST)  # Include file uploads

        if form.is_valid():
            # Save the material and associate it with the course and section
            material = form.save(commit=False)
            material.section = section
            material.courses = course
            material.save()

            messages.success(request, "Material successfully added to the course.")
            return redirect('courses:studio', id=course.id)
        else:
            # Provide error feedback
            messages.error(request, "Failed to add material. Please check the form for errors.")
            print(form.errors)  # Debugging (optional)

    else:
        # Initialize an empty form for GET requests
        form = MatrialForm()

    # Render the form template
    return render(request, 'courses/course_matrial.html', {
        'form': form,
        'course': course,
        'section': section,
    })


#edit matrial course
#@login_required
@csrf_exempt
def edit_matrial(request, idcourse, idmaterial):
    # Check the role of the user and determine access permissions
    # Check if the user is authenticated
    if not request.user.is_authenticated:
        return redirect("/login/?next=%s" % request.path)
    # Superuser can access and edit any material
    if request.user.is_superuser:
        # Superuser can access any material, get the associated course via section
        material = get_object_or_404(Material, id=idmaterial)
        course = get_object_or_404(Course, id=idcourse)
    
    # Partner can only access materials related to their course
    elif request.user.is_partner:
        course = get_object_or_404(Course, id=idcourse, org_partner__user_id=request.user.id)
        # Ensure the material belongs to the course's section
        material = get_object_or_404(Material, id=idmaterial, section__courses=course)
    
    # Instructor can only access and edit materials related to their courses
    elif request.user.is_instructor:
        course = get_object_or_404(Course, id=idcourse, instructor__user_id=request.user.id)
        # Ensure the material belongs to the course's section
        material = get_object_or_404(Material, id=idmaterial, section__courses=course)
    
    else:
        # Unauthorized access for users who are not superuser, partner, or instructor
        messages.error(request, "You do not have permission to edit materials in this course.")
        return redirect('courses:home')

    # Handle POST request to update the material
    if request.method == 'POST':
        form = MatrialForm(request.POST, request.FILES, instance=material)
        if form.is_valid():
            form.save()  # Save the updated material
            messages.success(request, "Successfully updated material.")
            return redirect('courses:studio', id=course.id)  # Redirect to the course studio page
        else:
            messages.error(request, "Failed to update material. Please check the form for errors.")
            print(form.errors)  # Debugging (optional)
    else:
        # For GET requests, populate the form with existing material
        form = MatrialForm(instance=material)

    # Render the template with the form and context
    return render(request, 'courses/edit_matrial_course.html', {
        'form': form,
        'course': course,
        'material': material,
    })





#delete matrial course
#@login_required
@csrf_exempt
def delete_matrial(request, pk):
    # Check if the user is authenticated
    if not request.user.is_authenticated:
        return redirect("/login/?next=%s" % request.path)
    # Ensure the request is a POST request
    if request.method == 'POST':
        # Fetch the material and its section
        material = get_object_or_404(Material, id=pk)
        section = material.section
        course = section.courses  # Adjust this if the field name is different

        # Check user roles
        if request.user.is_superuser:
            # Superuser can delete any material
            pass
        elif request.user.is_partner:
            # Partner can delete material only for their associated courses
            if not course.org_partner or course.org_partner.user_id != request.user.id:
                return JsonResponse({'status': 'error', 'message': 'Permission denied. You do not own this course.'})
        elif request.user.is_instructor:
            # Instructor can delete material only for their own courses
            if not course.instructor or course.instructor.user_id != request.user.id:
                return JsonResponse({'status': 'error', 'message': 'Permission denied. This is not your course.'})
        else:
            # Unauthorized user
            return JsonResponse({'status': 'error', 'message': 'Permission denied.'})

        # Delete the material if the role check passes
        material.delete()
        return JsonResponse({'status': 'success', 'message': 'Material deleted successfully!'})
    else:
        # Handle invalid request methods
        return JsonResponse({'status': 'error', 'message': 'Invalid request method. Only POST requests are allowed.'})



#course view 
#@login_required



def courseView(request):
    # Check if the user is authenticated
    if not request.user.is_authenticated:
        return redirect("/login/?next=%s" % request.path)

    user = request.user
    course_filter = request.GET.get('filter', 'all')  # Get filter from query string

    # Update status for published courses that have passed end_enrol
    try:
        published_status = CourseStatus.objects.get(status='published')
        archive_status = CourseStatus.objects.get(status='archived')
        
        # Find published courses where end_enrol has passed and update to archived
        Course.objects.filter(
            status_course=published_status,
            end_enrol__lt=timezone.now().date()  # Gunakan date untuk DateField
        ).update(status_course=archive_status)
    except CourseStatus.DoesNotExist:
        # Jika status tidak ditemukan, lanjutkan tanpa pembaruan
        pass

    # Filter courses based on the user's role and selected filter
    if user.is_superuser:
        courses = Course.objects.all()
    elif user.is_partner:
        courses = Course.objects.filter(org_partner__user=user)
    elif user.is_instructor:
        courses = Course.objects.filter(instructor__user=user, instructor__status='Approved')
    else:
        courses = Course.objects.none()

    # Apply the filter for the course status
    if course_filter == 'draft':
        courses = courses.filter(status_course__status='draft')
    elif course_filter == 'published':
        courses = courses.filter(status_course__status='published')
    elif course_filter == 'archive':
        courses = courses.filter(status_course__status='archived')
    elif course_filter == 'curation':
        courses = courses.filter(status_course__status='curation')

    # Get search query if any
    search_query = request.GET.get('search', '').strip()
    if search_query:
        courses = courses.filter(course_name__icontains=search_query)

    # Annotate instructor_email and org_partner_name
    courses = courses.annotate(
        instructor_email=F('instructor__user__email'),
        org_partner_name=F('org_partner__name__name')
    )

    # Correctly annotate the enrolment count based on the relationship
    courses = courses.annotate(
        enrolment_count=Count('enrollments')  # Adjust based on your model
    )

    # Paginate the courses
    paginator = Paginator(courses, 10)  # 10 courses per page
    page_number = request.GET.get('page', 1)
    try:
        page_obj = paginator.page(page_number)
    except PageNotAnInteger:
        page_obj = paginator.page(1)
    except EmptyPage:
        page_obj = paginator.page(paginator.num_pages)

    # Fetch CourseStatus for counts
    try:
        draft_status = CourseStatus.objects.get(status='draft')
        published_status = CourseStatus.objects.get(status='published')
        archive_status = CourseStatus.objects.get(status='archived')
        curation_status = CourseStatus.objects.get(status='curation')
    except ObjectDoesNotExist:
        draft_status = published_status = archive_status = curation_status = None

    # Calculate counts based on filtered courses
    draft_count = courses.filter(status_course=draft_status).count() if draft_status else 0
    published_count = courses.filter(status_course=published_status).count() if published_status else 0
    archive_count = courses.filter(status_course=archive_status).count() if archive_status else 0
    curation_count = courses.filter(status_course=curation_status).count() if curation_status else 0

    # If there's a search query, update the counts to reflect only the filtered results
    if search_query:
        draft_count = courses.filter(status_course=draft_status).count() if draft_status else 0
        published_count = courses.filter(status_course=published_status).count() if published_status else 0
        archive_count = courses.filter(status_course=archive_status).count() if archive_status else 0
        curation_count = courses.filter(status_course=curation_status).count() if curation_status else 0

    # Pass the filtered courses count to the template
    return render(request, 'courses/course_view.html', {
        'page_obj': page_obj,
        'course_filter': course_filter,
        'all_count': courses.count(),
        'draft_count': draft_count,
        'published_count': published_count,
        'archive_count': archive_count,
        'curation_count': curation_count
    })

@login_required
def user_detail(request, user_id):
    # Ambil pengguna berdasarkan user_id
    user = get_object_or_404(CustomUser, id=user_id)

    # Ambil daftar enrollment untuk pengguna ini
    enrollments = Enrollment.objects.filter(user=user).select_related('course')

    # Implementasi pencarian berdasarkan course_name
    search_query = request.GET.get('search', '')
    if search_query:
        enrollments = enrollments.filter(course__course_name__icontains=search_query)

    # Siapkan data untuk pagination
    course_details = []
    for enrollment in enrollments:
        course = enrollment.course

        # Ambil total skor dan status dari setiap kursus
        total_max_score = Decimal(0)
        total_score = Decimal(0)
        all_assessments_submitted = True  # Untuk memastikan semua asesmen diselesaikan

        # Ambil grade range untuk kursus tersebut
        grade_range = GradeRange.objects.filter(course=course).first()
        passing_threshold = grade_range.min_grade if grade_range else Decimal(50)  # Default jika tidak ada grade range

        # Hitung skor dari asesmen
        assessments = Assessment.objects.filter(section__courses=course)
        for assessment in assessments:
            score_value = Decimal(0)
            total_correct_answers = 0
            total_questions = assessment.questions.count()

            if total_questions > 0:  # Multiple choice
                answers_exist = False
                for question in assessment.questions.all():
                    answers = QuestionAnswer.objects.filter(question=question, user=user)
                    if answers.exists():
                        answers_exist = True
                    total_correct_answers += answers.filter(choice__is_correct=True).count()
                if not answers_exist:
                    all_assessments_submitted = False
                if total_questions > 0:
                    score_value = (Decimal(total_correct_answers) / Decimal(total_questions)) * Decimal(assessment.weight)

            total_max_score += assessment.weight
            total_score += score_value

        # Hitung persentase skor
        overall_percentage = (total_score / total_max_score) * 100 if total_max_score > 0 else 0

        # Ambil progress dari CourseProgress
        course_progress = CourseProgress.objects.filter(user=user, course=course).first()
        progress_percentage = course_progress.progress_percentage if course_progress else Decimal(0)

        # Tentukan status kelulusan
        status = "Fail"  # Default status
        if progress_percentage == 100 and all_assessments_submitted and overall_percentage >= passing_threshold:
            status = "Pass"

        # Tambahkan detail kursus ke daftar
        course_details.append({
            'course_name': course.course_name,
            'total_score': total_score,
            'total_max_score': total_max_score,
            'status': status,
            'progress_percentage': progress_percentage,  # Untuk debug atau tampilan
            'overall_percentage': overall_percentage,    # Untuk debug atau tampilan
        })

    # Pagination untuk hasil kursus
    paginator = Paginator(course_details, 5)  # 5 kursus per halaman
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'user': user,
        'course_details': page_obj,
        'search_query': search_query,
    }
    
    return render(request, 'authentication/user_detail.html', context)


def filter_courses_by_query(request, posts):
    """Filter courses based on search query."""
    query = request.GET.get('q')
    if query is not None and query !='':
        posts = posts.filter(Q(course_name__icontains=query) | Q(status_course__icontains=query)).distinct()
    return posts

def paginate_courses(request, posts):
    """Paginate the course list."""
    paginator = Paginator(posts, 5)
    page_number = request.GET.get('page')
    return paginator.get_page(page_number)


#create course
#@login_required

def course_create_view(request):
    # Check if the user is authenticated
    if not request.user.is_authenticated:
        return redirect("/login/?next=%s" % request.path)

    if request.user.is_partner or request.user.is_superuser or request.user.is_instructor:
        if request.method == 'POST':
            form = CourseForm(request.POST, user=request.user)  # Pass the logged-in user to the form

            if form.is_valid():
                course = form.save(commit=False)  # Create a Course instance but don't save to the database yet

                # Set the author to the logged-in user
                course.author = request.user
                
                # If the user is a partner or superuser, set the org_partner
                if request.user.is_superuser or request.user.is_partner:
                    partner = form.cleaned_data['org_partner']  # Get the selected partner from the form
                    course.org_partner = partner  # Set the partner for the course

                # If the user is an instructor, set the instructor
                if request.user.is_instructor:
                    instructor = Instructor.objects.get(user=request.user)  # Assuming a one-to-one relationship
                    course.instructor = instructor

                # Set status_course programmatically (e.g., default to 'draft')
                try:
                    draft_status = CourseStatus.objects.get(status='draft')
                except CourseStatus.DoesNotExist:
                    draft_status = None  # Or provide a default value or take any other action

                #draft_status = CourseStatus.objects.get(status='draft')  # Assuming 'draft' exists in CourseStatus
                course.status_course = draft_status  # Set the default status

                # Save the course instance to the database
                course.save()

                return redirect('/courses/')  # Redirect to a course list page or success page
            else:
                print(form.errors)  # Print form errors to the console for debugging
        else:
            form = CourseForm(user=request.user)  # Pass the logged-in user to the form

    else:
        return redirect('/courses/')

    return render(request, 'courses/course_add.html', {'form': form})

#studio detail courses

def studio(request, id):
    # Check if the user is authenticated
    if not request.user.is_authenticated:
        return redirect("/login/?next=%s" % request.path)
    if request.user.is_authenticated:
        UserActivityLog.objects.create(user=request.user, activity_type='course_learn')
    user = request.user
    course = None

  
    # Determine the course based on the user's role
    if request.user.is_superuser:
        course = get_object_or_404(Course, id=id)
    elif user.is_partner:
        #course = Course.objects.filter(id=id, org_partner_id=request.user.id).first()
        course = get_object_or_404(Course, id=id, org_partner__user_id=user.id)
        #print(course)
    elif user.is_instructor:
        course = get_object_or_404(Course, id=id, instructor__user_id=user.id)
    # If no course is found, redirect to the courses list page
        #print(course)
    if not course:
        return redirect('/courses')

    # Fetch sections related to the specific course
    #section = Section.objects.filter(parent=None, courses_id=course.id)
    #section = Section.objects.filter(parent=None, courses=course).prefetch_related('materials')
    #section = Section.objects.filter(parent=None, courses=course).prefetch_related('questions')
    section = Section.objects.filter(
    parent=None, courses=course
).prefetch_related('materials', 'assessments')  # Add all necessary relationships

    # Render the page with the course and sections data
    return render(request, 'courses/course_detail.html', {'course': course, 'section': section})





def convert_image_to_webp(uploaded_image):
    """
    Konversi gambar yang diunggah ke format WebP dan kembalikan ContentFile
    """
    img = Image.open(uploaded_image)

    # Pastikan gambar berada dalam mode RGB
    img = img.convert('RGB')

    # Simpan gambar ke buffer dalam format WebP
    buffer = BytesIO()
    img.save(buffer, format='WEBP', quality=85)  # Adjust kualitas sesuai kebutuhan
    buffer.seek(0)

    # Kembalikan file dalam format ContentFile
    return ContentFile(buffer.read(), name='logo.webp')

@login_required
def update_partner(request, partner_id):
       # Cek apakah user adalah superuser atau staf
    if not request.user.is_superuser and not request.user.is_staff:
        return redirect('/')  # Redirect ke halaman utama jika bukan superuser atau staf

    partner = get_object_or_404(Partner, pk=partner_id)
    
    # Pastikan pengguna yang mengakses adalah pemilik partner atau admin
    if not request.user.is_authenticated or (request.user != partner.user and not request.user.is_superuser):
        return redirect("/login/?next=%s" % request.path)

    old_logo = partner.logo.path if partner.logo else None
    old_user = partner.user  # Menyimpan user lama

    if request.method == "POST":
        form = PartnerForm(request.POST, request.FILES, instance=partner)
        print("POST data:", request.POST)  # Debug data mentah
        if form.is_valid():
            print("Cleaned data:", form.cleaned_data)  # Debug setelah validasi
            partner_instance = form.save(commit=False)
            print("Instance before save:", partner_instance.__dict__)  # Debug sebelum simpan

            # Jika ada logo yang di-upload, ganti dengan yang baru
            if 'logo' in request.FILES:
                uploaded_logo = request.FILES['logo']
                converted_logo = convert_image_to_webp(uploaded_logo)
                partner_instance.logo = converted_logo

            # Simpan partner instance
            partner_instance.save()
            print("Instance after save:", partner_instance.__dict__)  # Debug setelah simpan

            # Jika ada perubahan user, update status is_partner
            if old_user != partner_instance.user:  # Jika user lama berbeda dengan user baru
                # Update status is_partner user lama menjadi False
                old_user.is_partner = False
                old_user.save()  # Simpan perubahan status user lama

                # Pastikan user baru mendapatkan status is_partner=True
                partner_instance.user.is_partner = True
                partner_instance.user.save()  # Simpan perubahan status user baru

            # Hapus logo lama jika sudah diganti
            if old_logo and old_logo != partner.logo.path:
                if os.path.exists(old_logo):
                    os.remove(old_logo)

            # Redirect ke detail partner setelah update
            return redirect('courses:partner_detail', partner_id=partner.id)
        else:
            print("Form errors:", form.errors)  # Debug jika form tidak valid
    else:
        form = PartnerForm(instance=partner)

    return render(request, 'partner/update_partner.html', {'form': form, 'partner': partner})


#partner view
#@cache_page(60 * 5)
def partnerView(request):
    if not request.user.is_authenticated:
        return redirect("/login/?next=%s" % request.path)

    query = request.GET.get('q', '')

    # Ambil semua partner (jika superuser) atau hanya milik user saat ini
    partners = Partner.objects.all() if request.user.is_superuser else Partner.objects.filter(user_id=request.user.id)

    # Filter berdasarkan pencarian
    if query:
        partners = partners.filter(
            Q(name__icontains=query) |
            Q(user__email__icontains=query) |
            Q(phone__icontains=query)
        )

    # Annotasi jumlah kursus, peserta unik, dan rating rata-rata
    partners = partners.annotate(
        total_courses=Count('courses', distinct=True),
        total_learners=Count('courses__enrollments__user', distinct=True),
        average_rating=Avg('courses__ratings__rating')
    )

    paginator = Paginator(partners, 10)
    page_number = request.GET.get('page')
    page = paginator.get_page(page_number)

    context = {
        'count': partners.count(),
        'page': page,
        'query': query
    }

    return render(request, 'partner/partner_view.html', context)


#detail_partner
def partner_detail(request, partner_id):
    if not request.user.is_authenticated:
        return redirect("/login/?next=%s" % request.path)

    # Retrieve the partner using the provided partner_id
    partner = get_object_or_404(Partner, id=partner_id)

    # Get the search query and category filter from the request
    search_query = request.GET.get('search', '')
    selected_category = request.GET.get('category', '')
    sort_by = request.GET.get('sort_by', 'name')

    # Filter courses related to the partner
    related_courses = Course.objects.filter(org_partner_id=partner.id)

    # Apply search filter if provided
    if search_query:
        related_courses = related_courses.filter(course_name__icontains=search_query)

    # Apply category filter if provided
    if selected_category:
        related_courses = related_courses.filter(category__name=selected_category)

    # Annotate each course with the number of enrollments (learners)
    related_courses = related_courses.annotate(learner_count=Count('enrollments'))

    # Sort the courses based on the sort_by value
    if sort_by == 'name':
        related_courses = related_courses.order_by('course_name')
    elif sort_by == 'date':
        related_courses = related_courses.order_by('created_at')
    elif sort_by == 'learners':
        related_courses = related_courses.order_by('-learner_count')
    elif sort_by == 'status':
        related_courses = related_courses.order_by('status_course')

    # Count the total number of related courses
    total_courses = related_courses.count()

    # Group courses by category (if category field exists)
    grouped_courses = {}
    for course in related_courses:
        category_name = course.category.name if course.category else 'Uncategorized'
        if category_name not in grouped_courses:
            grouped_courses[category_name] = []
        grouped_courses[category_name].append(course)

    # Fetch categories that have courses linked to this partner
    categories_with_courses = Category.objects.filter(category_courses__org_partner_id=partner.id).distinct()

    # --- Calculate unique learners across all courses ---
    unique_learners = Enrollment.objects.filter(course__in=related_courses).values('user').distinct().count()

    # --- Calculate total reviews and average rating across all courses ---
    course_ids = related_courses.values_list('id', flat=True)
    total_reviews = CourseRating.objects.filter(course_id__in=course_ids).count()  # Total reviews
    average_rating = CourseRating.objects.filter(course_id__in=course_ids).aggregate(
        avg_rating=Avg('rating')
    )['avg_rating'] or 0  # Average rating, default to 0 if no ratings exist

    # Pagination setup
    page_number = request.GET.get('page')
    paginator = Paginator(related_courses, 10)
    page_obj = paginator.get_page(page_number)

    # Context data
    context = {
        'partner': partner,
        'page_obj': page_obj,
        'total_courses': total_courses,
        'search_query': search_query,
        'grouped_courses': grouped_courses,
        'selected_category': selected_category,
        'categories': categories_with_courses,  # Only categories with courses
        'sort_by': sort_by,
        'unique_learners': unique_learners,  # Add unique learners to the context
        'total_reviews': total_reviews,  # Add total reviews to the context
        'average_rating': round(average_rating, 1),  # Add average rating to the context
    }

    return render(request, 'partner/partner_detail.html', context)


#org partner from lms
logger = logging.getLogger(__name__)



logger = logging.getLogger(__name__)

def org_partner(request, slug):
    partner = get_object_or_404(Partner, name__slug=slug)
    search_query = request.GET.get('search', '')
    selected_category = request.GET.get('category', '')
    sort_by = request.GET.get('sort_by', 'name')

    try:
        published_status = CourseStatus.objects.get(status='published')
    except CourseStatus.DoesNotExist:
        published_status = None

    if published_status:
        now_time = now()  # ✅ Simpan agar tidak dipanggil berulang-ulang
        related_courses = Course.objects.filter(
            org_partner_id=partner.id,
            status_course=published_status,
            end_enrol__gte=now_time
        ).select_related(
            'category', 'instructor__user', 'org_partner'
        ).prefetch_related('enrollments')

        if search_query:
            related_courses = related_courses.filter(course_name__icontains=search_query)

        if selected_category:
            related_courses = related_courses.filter(category__name=selected_category)

        if sort_by == 'learners':
            related_courses = related_courses.annotate(
                total_enrollments=Count('enrollments')
            ).order_by('-total_enrollments')
        elif sort_by == 'date':
            related_courses = related_courses.order_by('created_at')
        else:
            related_courses = related_courses.order_by('course_name')

        categories = Category.objects.filter(
            category_courses__org_partner_id=partner.id,
            category_courses__status_course=published_status,
            category_courses__end_enrol__gte=now_time
        ).annotate(course_count=Count('category_courses')).distinct()
    else:
        related_courses = Course.objects.none()
        categories = Category.objects.none()

    # Pagination
    page_number = request.GET.get('page')
    paginator = Paginator(related_courses, 10)
    page_obj = paginator.get_page(page_number)

    unique_learners = related_courses.aggregate(
        unique_users=Count('enrollments__user', distinct=True)
    )['unique_users'] or 0

    total_reviews = 0
    total_rating_sum = 0
    courses_data = []
    total_enrollments = 0

    for course in page_obj:
        try:
            num_enrollments = course.enrollments.count()
        except AttributeError as e:
            logger.error(f"Error accessing enrollments for course {course.course_name}: {str(e)}")
            num_enrollments = 0

        total_enrollments += num_enrollments

        review_qs = CourseRating.objects.filter(course=course)
        review_count = review_qs.count()
        total_reviews += review_count
        total_rating_sum += review_qs.aggregate(total_rating=Sum('rating'))['total_rating'] or 0

        average_rating = round(total_rating_sum / review_count, 1) if review_count > 0 else 0
        full_stars = int(average_rating)
        half_star = (average_rating % 1) >= 0.5
        empty_stars = 5 - full_stars - (1 if half_star else 0)

        course_data = {
            'course_name': course.course_name,
            'hour': course.hour,
            'course_id': course.id,
            'num_enrollments': num_enrollments,
            'course_slug': course.slug,
            'course_image': course.image.url if course.image else None,
            'instructor': course.instructor.user.get_full_name() if course.instructor else None,
            'instructor_username': course.instructor.user.username if course.instructor else None,
            'photo': course.instructor.user.photo.url if course.instructor and course.instructor.user.photo else None,
            'partner': course.org_partner.name if course.org_partner else None,
            'partner_kode': course.org_partner.name.kode if course.org_partner else None,
            'category': course.category.name if course.category else None,
            'language': course.language,
            'average_rating': average_rating,
            'review_count': review_count,
            'full_star_range': range(full_stars),
            'half_star': half_star,
            'empty_star_range': range(empty_stars),
        }
        courses_data.append(course_data)

    average_rating_all_courses = round(total_rating_sum / total_reviews, 1) if total_reviews > 0 else 0

    context = {
        'partner': partner,
        'page_obj': page_obj,
        'courses': courses_data,
        'total_courses': related_courses.count(),
        'unique_learners': unique_learners,
        'total_enrollments': total_enrollments,
        'total_reviews': total_reviews,
        'average_rating': average_rating_all_courses,
        'search_query': search_query,
        'selected_category': selected_category,
        'categories': list(categories.values('id', 'name', 'course_count')),
        'sort_by': sort_by,
    }

    return render(request, 'partner/org_partner.html', context)



def search_users(request):
    term = request.GET.get('q', '')
    users = CustomUser.objects.filter(username__icontains=term, is_active=True)[:20]  # Batasi hasil
    results = [{"id": user.id, "text": user.username} for user in users]
    return JsonResponse({"users": results})

def search_partner(request):  # Dalam kasus ini, saya asumsikan mencari Universiti
    term = request.GET.get('q', '')
    universities = Universiti.objects.filter(name__icontains=term)[:20]  # Batasi hasil
    results = [{"id": uni.id, "text": uni.name} for uni in universities]
    return JsonResponse({"partners": results})





@login_required
def partner_create_view(request):
    # Cek apakah user adalah superuser atau staf
    if not request.user.is_superuser and not request.user.is_staff:
        return redirect('/')  # Redirect ke halaman utama jika bukan superuser atau staf

    if request.method == 'POST':
        form = PartnerForm(request.POST)
        if form.is_valid():
            partner = form.save(commit=False)  # Simpan instance ke variabel terpisah
            partner.author_id = request.user.id
            partner.save()  # Simpan instance
            # Update user's is_partner field
            user = partner.user  # Ambil user dari instance
            user.is_partner = True
            user.save()
            return redirect('/partner')
    else:
        form = PartnerForm()
    return render(request, 'partner/partner_add.html', {'form': form})


#contoh ajax
def course_create(request):
    data = dict()
    
    # Check if it's a POST request
    if request.method == 'POST':
        form = CourseForm(request.POST)
        
        if form.is_valid():
            # Save the new course if the form is valid
            form.save()
            data['form_is_valid'] = True
            
            # Fetch the updated course list after adding a new course
            courses = Course.objects.all()  # Corrected from Course.all() to Course.objects.all()
            data['course_list'] = render_to_string('courses/course_list.html', {'courses': courses})
        else:
            # Form is not valid, send this info back
            data['form_is_valid'] = False
    else:
        # For GET request, create an empty form
        form = CourseForm()
    
    # Render the course creation form
    context = {'form': form}
    data['html_form'] = render_to_string('courses/course_create.html', context, request=request)
    
    return JsonResponse(data)

# Delete Book
def course_delete(request, pk):
    courses = get_object_or_404(Course, pk=pk)
    data = dict()
    if request.method == 'POST':
        courses.delete()
        data['form_is_valid'] = True
        books = Course.objects.all()
        data['course_list'] = render_to_string('courses/course_list.html', {'courses': courses})
    return JsonResponse(data)

# View to fetch the list of books (for initial load)
@cache_page(60 * 15)
def course_list(request):
    courses = Course.objects.all()[:100]
    return render(request, 'courses/course_list.html', {'courses': courses})
