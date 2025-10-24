# payments/views.py

import requests
from django.conf import settings
from django.shortcuts import render
from django.db.models import Sum, Count
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.shortcuts import get_object_or_404, redirect
from django.contrib import messages
import logging
from courses.models import Course,CoursePrice,Partner,Enrollment,CalculateAdminPrice
from payments.models import CartItem,Transaction,Payment, Voucher,VoucherUsage  # pastikan model keranjang belanja kamu ini
from django.utils.timezone import now
from django.db import IntegrityError
from django.contrib.auth.decorators import login_required, user_passes_test
from django.core.paginator import Paginator
from django.utils.http import urlencode
from django.db.models import Q
from django.utils import timezone
import json, time
from datetime import timedelta
from weasyprint import HTML
from django.http import HttpResponse
from django.template.loader import render_to_string
from .utils import get_client_ip, get_geo_from_ip, validate_voucher, get_tripay_payment_channels,create_tripay_transaction
from decimal import Decimal
from django.db import transaction as db_transaction
import uuid
from django.http import JsonResponse, HttpResponseBadRequest, HttpResponse
from django.views.decorators.csrf import csrf_exempt
import hmac
import hashlib
import json
import time
import csv
from datetime import datetime, timezone as dt_timezone
from payments.utils import create_tripay_transaction
from django.db.models import F, Sum, Count
from django.db.models.functions import Coalesce
from django.db import models 

@csrf_exempt
def tripay_webhook(request):
    if request.method != 'POST':
        return HttpResponseBadRequest('Invalid method')

    raw_body = request.body

    # Pastikan header signature sesuai dengan header Tripay yang kamu dapat
    signature_header = request.headers.get('X-Callback-Signature')
    if not signature_header:
        return HttpResponseBadRequest('Missing signature header')

    computed_signature = hmac.new(
        key=settings.TRIPAY_PRIVATE_KEY.encode('latin-1'),
        msg=raw_body,
        digestmod=hashlib.sha256
    ).hexdigest()

    if not hmac.compare_digest(computed_signature, signature_header):
        return HttpResponseBadRequest('Invalid signature')

    try:
        data = json.loads(raw_body)
    except json.JSONDecodeError:
        return HttpResponseBadRequest('Invalid JSON payload')

    merchant_ref = data.get('merchant_ref')
    status = data.get('status')

    if not merchant_ref or not status:
        return HttpResponseBadRequest('Missing required fields')

    try:
        transaction = Transaction.objects.get(merchant_ref=merchant_ref)
    except Transaction.DoesNotExist:
        return HttpResponseBadRequest('Transaction not found')

    status_map = {
        'PAID': 'completed',
        'EXPIRED': 'cancelled',
        'FAILED': 'failed',
    }

    mapped_status = status_map.get(status.upper(), 'pending')
    transaction.status = mapped_status
    transaction.save()

    # Update semua Payment terkait
    payments = transaction.payments.all()
    payments.update(status=mapped_status)

    # Jalankan method status spesifik jika perlu
    if mapped_status == 'completed':
        for payment in payments:
            payment.mark_completed()
    elif mapped_status in ['failed', 'cancelled']:
        for payment in payments:
            payment.mark_failed()
    else:
        for payment in payments:
            payment.save()

    return JsonResponse({'success': True})
def payment_return(request):
    return render(request, 'payments/return.html')


logger = logging.getLogger(__name__)

@login_required
@user_passes_test(lambda u: u.is_superuser or getattr(u, 'is_partner', False) or getattr(u, 'is_finance', False))
def payment_detail_view(request, pk):
    payment = get_object_or_404(Payment.objects.select_related('user', 'course__org_partner'), pk=pk)
    return render(request, 'payments/payment_detail.html', {'payment': payment})


@login_required
@user_passes_test(lambda u: u.is_superuser or getattr(u, 'is_partner', False) or getattr(u, 'is_finance', False))
def transaction_report_view(request):
    payments = Payment.objects.select_related('user', 'course__org_partner')

    if getattr(request.user, 'is_partner', False):
        payments = payments.filter(course__org_partner__user=request.user)

    # Filters
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')
    if start_date:
        payments = payments.filter(created_at__date__gte=start_date)
    if end_date:
        payments = payments.filter(created_at__date__lte=end_date)

    search = request.GET.get('search', '').strip()
    if search:
        payments = payments.filter(linked_transaction__id__icontains=search)

    paginator = Paginator(payments.order_by('-created_at'), 25)
    page_obj = paginator.get_page(request.GET.get('page'))

    return render(request, 'finance/transaction_report.html', {'page_obj': page_obj})




@login_required
@user_passes_test(lambda u: u.is_superuser or getattr(u, 'is_finance', False) or getattr(u, 'is_partner', False))
def invoice_receipt_view(request):
    payments = Payment.objects.select_related('user', 'course', 'course__org_partner')

    if getattr(request.user, 'is_partner', False):
        payments = payments.filter(course__org_partner__user=request.user)

    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')
    if start_date:
        payments = payments.filter(payment_date__date__gte=start_date)
    if end_date:
        payments = payments.filter(payment_date__date__lte=end_date)

    status = request.GET.get('status')
    if status:
        payments = payments.filter(status=status)

    paginator = Paginator(payments.order_by('-payment_date'), 10)  # 10 per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    print(f"Total payments: {payments.count()}, Page size: {len(page_obj)}")  # Debug print

    current = page_obj.number
    total = paginator.num_pages
    start = max(current - 2, 1)
    end = min(current + 2, total) + 1
    page_range = range(start, end)

    context = {
        'page_obj': page_obj,
        'page_range': page_range,
    }
    return render(request, 'finance/invoice_receipt.html', context)






@login_required
@user_passes_test(lambda u: u.is_superuser or getattr(u, 'is_finance', False) or getattr(u, 'is_partner', False))
def partner_commission_view(request):
    user = request.user
    
    # Skip missing fields check untuk superuser/finance
    if not (user.is_superuser or getattr(user, 'is_finance', False)):
        required_fields = {
            'first_name': 'First Name',
            'last_name': 'Last Name',
            'email': 'Email',
            'phone': 'Phone Number',
            'gender': 'Gender',
            'birth': 'Date of Birth',
        }
        missing_fields = [label for field, label in required_fields.items() if not getattr(user, field)]
        if missing_fields:
            messages.warning(request, f"Please complete the following information: {', '.join(missing_fields)}")
            return redirect('authentication:edit-profile', pk=user.pk)
    
    # Debug print (hapus setelah test)
    print(f"DEBUG: User {user.username} - is_superuser: {user.is_superuser}, is_finance: {getattr(user, 'is_finance', False)}")
    
    payments = Payment.objects.select_related('user', 'course__org_partner').all()

    # Filter berdasarkan role
    if getattr(request.user, 'is_partner', False):
        payments = payments.filter(course__org_partner__user=request.user)
        partner_id = None
    else:
        try:
            partner_id = int(request.GET.get('partner_id')) if request.GET.get('partner_id') else None
        except ValueError:
            partner_id = None
        if partner_id:
            payments = payments.filter(course__org_partner__id=partner_id)

    # Filter tanggal
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')
    if start_date:
        payments = payments.filter(created_at__date__gte=start_date)
    if end_date:
        payments = payments.filter(created_at__date__lte=end_date)

    # Filter berdasarkan ID Transaksi
    search_query = request.GET.get('search', '').strip()
    if search_query.isdigit():
        payments = payments.filter(linked_transaction__id=search_query)

    # Ringkasan
    summary = payments.values('payment_model', 'status').annotate(
        total_amount=Sum('amount'),
        count=Count('id')
    ).order_by('payment_model', 'status')

    # Pendapatan kotor (total yang dibayar user)
    total_paid = payments.filter(status='completed').aggregate(
        total=Sum('amount')
    )['total'] or 0

    # Pendapatan bersih untuk Partner & ICE Admin
    net_income_partner = payments.filter(status='completed').aggregate(
        total=Sum('snapshot_partner_earning')
    )['total'] or 0

    net_income_admin = payments.filter(status='completed').aggregate(
        total=Sum('snapshot_ice_earning')
    )['total'] or 0

    partner_courses = None
    if request.user.is_superuser or getattr(request.user, 'is_finance', False):
        partner_courses = Course.objects.values(
            'id', 'course_name', 'org_partner__name'
        ).annotate(
            total_amount=Sum('payments__amount')
        ).filter(
            payments__status='completed'
        )
        if partner_id:
            partner_courses = partner_courses.filter(org_partner__id=partner_id)

    # Pagination
    paginator = Paginator(payments.order_by('-created_at'), 25)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    # Buat querystring tanpa parameter "page"
    get_params = request.GET.copy()
    if 'page' in get_params:
        del get_params['page']
    querystring = get_params.urlencode()

    context = {
        'summary': summary,
        'total_paid': total_paid,
        'net_income_partner': net_income_partner,
        'net_income_admin': net_income_admin,
        'page_obj': page_obj,
        'partners': Partner.objects.all() if request.user.is_superuser or getattr(request.user, 'is_finance', False) else None,  # Fix: tambah is_finance
        'partner_courses': partner_courses,
        'search_query': search_query,
        'querystring': querystring,
    }
    
    return render(request, 'finance/partner_commission.html', context)





@login_required
@user_passes_test(lambda u: u.is_superuser or getattr(u, 'is_finance', False))
def financial_export_view(request):
    payments = Payment.objects.filter(status='completed')

    if 'export' in request.GET:
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="financial_report.csv"'
        writer = csv.writer(response)
        writer.writerow(['Transaction ID', 'User', 'Course', 'Amount', 'Date'])
        for p in payments:
            writer.writerow([p.id, p.user.username, p.course.course_name, p.amount, p.created_at])
        return response

    return render(request, 'finance/financial_export.html')



@login_required
@user_passes_test(lambda u: u.is_superuser or getattr(u, 'is_finance', False) or getattr(u, 'is_partner', False))
def invoice_receipt_view(request):
    payments = Payment.objects.select_related('user', 'course', 'course__org_partner')

    # Filter berdasarkan role partner
    if getattr(request.user, 'is_partner', False):
        payments = payments.filter(course__org_partner__user=request.user)

    # Filter tanggal
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')
    if start_date:
        payments = payments.filter(payment_date__date__gte=start_date)
    if end_date:
        payments = payments.filter(payment_date__date__lte=end_date)

    # Filter status
    status = request.GET.get('status')
    if status:
        payments = payments.filter(status=status)

    # Pagination
    paginator = Paginator(payments.order_by('-payment_date'), 20)
    page_obj = paginator.get_page(request.GET.get('page'))

    context = {
        'page_obj': page_obj,
    }
    return render(request, 'finance/invoice_receipt.html', context)



def process_payment(request, course_id, payment_type='enrollment'):
    from decimal import Decimal
    course = get_object_or_404(Course, id=course_id)
    logger.info(f"Processing payment for course {course_id}, payment_type: {payment_type}")

    # Petakan payment_type ke payment_model
    payment_model_map = {
        'enrollment': 'buy first',
        'exam': 'pay for exam',
        'certificate': 'pay for certificate'
    }
    payment_model = payment_model_map.get(payment_type, 'buy first')

    # Validasi payment_type
    if payment_type not in ['enrollment', 'exam', 'certificate']:
        messages.error(request, "Invalid payment type.")
        return redirect('courses:course_lms_detail', id=course.id, slug=course.slug)

    if payment_type in ['exam', 'certificate']:
        CartItem.objects.get_or_create(
            user=request.user,
            course=course,
            defaults={'added_at': timezone.now()}
        )
        messages.info(request, f"{course.course_name} telah ditambahkan ke keranjang. Silakan lanjutkan pembayaran melalui checkout.")
        return redirect('payments:view_cart')

    # Sudah pernah bayar
    if Payment.objects.filter(
        user=request.user,
        course=course,
        payment_model=payment_model,
        status='completed'
    ).exists():
        messages.info(request, f"Payment for {payment_type} already completed.")
        if payment_type == 'exam':
            return redirect('learner:course_learn', username=request.user.username, id=course.id, slug=course.slug)
        elif payment_type == 'certificate':
            return redirect('courses:claim_certificate', course_id=course.id)
        return redirect('courses:course_lms_detail', id=course.id, slug=course.slug)

    # Ambil harga
    course_price = CoursePrice.objects.filter(course=course, price_type__name=course.payment_model).first()
    if not course_price:
        messages.error(request, "Price not available for this course.")
        return redirect('courses:course_lms_detail', id=course.id, slug=course.slug)

    # Ambil global platform fee dan voucher
    platform_fee_obj = CalculateAdminPrice.objects.filter(name__iexact="Platform Fee").first()
    voucher_obj = CalculateAdminPrice.objects.filter(name__iexact="Voucher").first()
    platform_fee = platform_fee_obj.amount if platform_fee_obj else Decimal("0.00")
    voucher = voucher_obj.amount if voucher_obj else Decimal("0.00")

    # Hitung total bayar user
    total_payment = course_price.portal_price + platform_fee - voucher

    # Buat atau update Payment
    payment = Payment.objects.filter(
        user=request.user,
        course=course,
        payment_model=payment_model,
        status__in=['pending', 'failed']
    ).first()

    if payment:
        payment.amount = course_price.portal_price
        payment.status = 'pending'
        payment.course_price = course_price
        payment.snapshot_price = course_price.normal_price
        payment.snapshot_discount = course_price.discount_amount
        payment.snapshot_tax = course_price.tax
        payment.snapshot_ppn = course_price.ppn
        payment.snapshot_user_payment = course_price.portal_price
        payment.snapshot_partner_earning = course_price.partner_earning
        payment.snapshot_ice_earning = course_price.ice_earning
        payment.snapshot_platform_fee = platform_fee
        payment.snapshot_voucher = voucher
        payment.save()
    else:
        payment = Payment.objects.create(
            user=request.user,
            course=course,
            payment_model=payment_model,
            amount=course_price.portal_price,
            status='pending',
            course_price=course_price,
            snapshot_price=course_price.normal_price,
            snapshot_discount=course_price.discount_amount,
            snapshot_tax=course_price.tax,
            snapshot_ppn=course_price.ppn,
            snapshot_user_payment=course_price.portal_price,
            snapshot_partner_earning=course_price.partner_earning,
            snapshot_ice_earning=course_price.ice_earning,
            snapshot_platform_fee=platform_fee,
            snapshot_voucher=voucher
        )

    # Buat atau update Transaction
    transaction = None
    if payment.linked_transaction:
        transaction = payment.linked_transaction

    if not transaction:
        transaction = Transaction.objects.create(
            user=request.user,
            total_amount=total_payment,
            platform_fee=platform_fee,
            voucher=voucher,
            status='pending',
            description=f"Payment for {payment_type} in course {course.course_name}"
        )
        transaction.courses.add(course)
        payment.linked_transaction = transaction
        payment.save()

    return render(request, 'payments/payment_page.html', {
        'course': course,
        'payment': payment,
        'transaction': transaction,
        'payment_type': payment_type
    })


@login_required
@require_POST
def add_to_cart(request, course_id):
    if not request.user.is_authenticated:
        return redirect("/login/?next=%s" % request.path)
    course = get_object_or_404(Course, id=course_id)

    # Cegah jika course gratis, langsung arahkan ke enroll
    if course.payment_model == 'free':
        messages.info(request, "This course is free, please register directly.")
        return redirect('courses:enroll', course_id=course.id)

    # Cek apakah sudah ada di cart
    cart_item, created = CartItem.objects.get_or_create(
        user=request.user,
        course=course,
        defaults={'added_at': now()}
    )

    if created:
        messages.success(request, f"{course.course_name} has been successfully added to your cart.")
    else:
        messages.info(request, f"{course.course_name} is already in your cart.")

    return redirect('payments:view_cart')  # pastikan URL ini ada



@login_required
def view_cart(request):
    cart_items = CartItem.objects.select_related('course').filter(user=request.user)

    platform_fee_obj = CalculateAdminPrice.objects.filter(name__iexact="Platform Fee").first()
    voucher_obj = CalculateAdminPrice.objects.filter(name__iexact="Voucher").first()
    platform_fee = platform_fee_obj.amount if platform_fee_obj else Decimal("0.00")
    voucher = voucher_obj.amount if voucher_obj else Decimal("0.00")

    sub_total = Decimal('0.00')

    # Attach harga ke setiap cart item
    for item in cart_items:
        course_price = item.course.get_course_price()
        if course_price:
            item.course_price_portal_price = course_price.portal_price
            sub_total += course_price.portal_price
        else:
            item.course_price_portal_price = Decimal('0.00')

    total_price = sub_total + platform_fee - voucher

    context = {
        'cart_items': cart_items,
        'sub_total': sub_total,
        'platform_fee': platform_fee,
        'voucher': voucher,
        'total_price': total_price,
    }
    return render(request, 'payments/cart.html', context)






@login_required
def checkout(request):
    # ✅ Cek pending transaction terbaru (dalam 1 jam) untuk resume
    expire_limit = timezone.now() - timezone.timedelta(hours=1)
    pending_tx = Transaction.objects.filter(
        user=request.user,
        status='pending',
        created_at__gte=expire_limit
    ).prefetch_related('payments__course', 'courses').order_by('-created_at').first()

    if pending_tx:
        # Resume: Tampilkan info VA dari pending tx
        va_number = pending_tx.va_number
        bank_name = pending_tx.bank_name
        payment_url = pending_tx.payment_url
        merchant_ref = pending_tx.merchant_ref
        selected_payment_method = pending_tx.payment_method
        instructions = pending_tx.instructions  # Via getter, load dari instructions_json
        total_price = pending_tx.total_amount
        expired_at = pending_tx.expired_at
        # Reconstruct cart_items dari tx.courses (dummy object untuk template tabel)
        cart_items = []
        for course in pending_tx.courses.all():
            dummy_item = type('DummyCartItem', (object,), {
                'course': course,
                'get_course_price': lambda: course.get_course_price()
            })()
            cart_items.append(dummy_item)
        total_course_price = sum(course.get_course_price().portal_price for course in pending_tx.courses.all() if course.get_course_price())
        platform_fee = pending_tx.platform_fee
        voucher = pending_tx.voucher
        voucher_code = ''  # Tidak perlu untuk resume
        is_resume = True
        messages.info(request, "Anda memiliki transaksi pending. Lanjutkan pembayaran di bawah.")
    else:
        # Normal flow: Checkout baru
        is_resume = False
        cart_items = CartItem.objects.select_related('course').filter(user=request.user)
        if not cart_items.exists():
            messages.info(request, "Keranjang kamu kosong.")
            return redirect('payments:view_cart')

        PLATFORM_FEE = Decimal('5000.00')
        total_course_price = sum(item.course.get_course_price().portal_price for item in cart_items if item.course.get_course_price())

        voucher_code = request.GET.get('voucher') or request.POST.get('voucher')
        voucher_amount = Decimal('0.00')
        voucher_obj = None

        if voucher_code:
            voucher_obj, error_msg = validate_voucher(voucher_code, request.user)
            if error_msg:
                messages.warning(request, error_msg)
                return redirect('payments:checkout')
            else:
                # Cek voucher sudah dipakai oleh user?
                if VoucherUsage.objects.filter(user=request.user, voucher=voucher_obj).exists():
                    messages.warning(request, "Voucher sudah pernah digunakan.")
                    return redirect('payments:checkout')

                voucher_amount = voucher_obj.amount
                max_discount = total_course_price + PLATFORM_FEE
                if voucher_amount > max_discount:
                    voucher_amount = max_discount

        total_price = total_course_price + PLATFORM_FEE - voucher_amount
        if total_price < 0:
            total_price = Decimal('0.00')

        va_number = ''
        payment_url = ''
        merchant_ref = ''
        selected_payment_method = ''
        bank_name = ''
        instructions = []
        platform_fee = PLATFORM_FEE
        expired_at = None
        voucher = voucher_amount

        if request.method == 'POST':
            if 'apply_voucher' in request.POST:
                voucher_code = request.POST.get('voucher')
                return redirect(f"{request.path}?voucher={voucher_code}")

            elif 'checkout' in request.POST:
                payment_method = request.POST.get('payment_method')
                if not payment_method:
                    messages.error(request, "Pilih metode pembayaran terlebih dahulu.")
                    return redirect('payments:checkout')

                # Ambil voucher_code dari hidden input di form checkout
                voucher_code = request.POST.get('voucher_code', '')
                if voucher_code:
                    voucher_obj, error_msg = validate_voucher(voucher_code, request.user)
                    if error_msg:
                        messages.warning(request, error_msg)
                        return redirect('payments:checkout')
                    # Cek voucher sudah dipakai lagi sebelum buat transaksi
                    if VoucherUsage.objects.filter(user=request.user, voucher=voucher_obj).exists():
                        messages.warning(request, "Voucher sudah pernah digunakan.")
                        return redirect('payments:checkout')
                    voucher_amount = voucher_obj.amount
                    max_discount = total_course_price + PLATFORM_FEE
                    if voucher_amount > max_discount:
                        voucher_amount = max_discount
                    total_price = total_course_price + PLATFORM_FEE - voucher_amount
                    if total_price < 0:
                        total_price = Decimal('0.00')
                else:
                    voucher_obj = None
                    voucher_amount = Decimal('0.00')
                    total_price = total_course_price + PLATFORM_FEE

                # Validasi jumlah pembayaran sesuai
                total_payment_amount = sum(item.course.get_course_price().portal_price for item in cart_items if item.course.get_course_price())
                if (total_payment_amount + PLATFORM_FEE - voucher_amount) != total_price:
                    messages.error(request, "Total pembayaran tidak sesuai. Silakan coba lagi.")
                    return redirect('payments:checkout')

                ip = get_client_ip(request)
                geo = get_geo_from_ip(ip)
                user_agent = request.META.get('HTTP_USER_AGENT', '')

                with db_transaction.atomic():
                    merchant_ref = f"user-{request.user.id}-{int(time.time())}"

                    transaction = Transaction.objects.create(
                        user=request.user,
                        total_amount=total_price,
                        status='pending',
                        description='Course purchase',
                        platform_fee=PLATFORM_FEE,
                        voucher=voucher_amount,
                        merchant_ref=merchant_ref
                    )

                    for item in cart_items:
                        course = item.course
                        course_price = course.get_course_price()
                        if not course_price:
                            raise ValueError(f"Harga course {course.course_name} tidak tersedia")

                        Payment.objects.create(
                            user=request.user,
                            course=course,
                            payment_model=course.payment_model,
                            snapshot_price=course_price.normal_price,
                            snapshot_discount=course_price.discount_amount,
                            snapshot_tax=course.org_partner.tax if course.org_partner.is_pkp else Decimal('0.00'),
                            snapshot_ppn=course_price.ppn,
                            snapshot_user_payment=course_price.portal_price,
                            snapshot_partner_earning=course_price.partner_price,
                            snapshot_ice_earning=course_price.admin_fee,
                            snapshot_platform_fee=PLATFORM_FEE,
                            snapshot_voucher=voucher_amount,
                            ip_address=ip,
                            user_agent=user_agent,
                            location=f"{geo.get('city', '')}, {geo.get('country', '')}" if geo else None,
                            isp=geo.get('isp') if geo else None,
                            latitude=geo.get('lat') if geo else None,
                            longitude=geo.get('lon') if geo else None,
                            course_price={
                                "normal_price": str(course_price.normal_price),
                                "discount_amount": str(course_price.discount_amount),
                                "ppn": str(course_price.ppn),
                                "portal_price": str(course_price.portal_price),
                                "partner_price": str(course_price.partner_price),
                                "admin_fee": str(course_price.admin_fee),
                            },
                            linked_transaction=transaction,
                            amount=course_price.portal_price,
                            status='pending',
                        )

                        transaction.courses.add(course)

                    # Simpan voucher usage setelah berhasil buat transaksi dan payment
                    if voucher_obj:
                        VoucherUsage.objects.create(user=request.user, voucher=voucher_obj)
                        voucher_obj.used_count += 1
                        voucher_obj.save(update_fields=['used_count'])

                    cart_items.delete()

                    try:
                        va_number, bank_name, payment_url, tripay_transaction_id, instructions, tripay_expired_time = create_tripay_transaction(transaction, payment_method, request.user)

                        transaction.expired_at = datetime.fromtimestamp(tripay_expired_time).replace(tzinfo=dt_timezone.utc)
                        transaction.va_number = va_number
                        transaction.bank_name = bank_name
                        transaction.payment_url = payment_url
                        transaction.payment_method = payment_method
                        transaction.transaction_id = tripay_transaction_id
                        # ✅ FIX: Assign via property (setter dump ke instructions_json)
                        transaction.instructions = instructions
                        # ✅ Update: Include 'instructions_json' bukan 'instructions'
                        transaction.save(update_fields=['va_number', 'bank_name', 'payment_url', 'payment_method', 'transaction_id', 'instructions_json', 'expired_at'])

                        selected_payment_method = payment_method
                        logger.info(f"Checkout sukses untuk {merchant_ref}: VA {va_number}, Expired {transaction.expired_at}")

                        return redirect('payments:transaction_detail', merchant_ref=merchant_ref)
                    except Exception as e:
                        logger.error(f"Tripay error di checkout: {e}")
                        messages.error(request, f"Gagal membuat VA: {str(e)}")
                        transaction.status = 'failed'
                        transaction.save()
                        return redirect('payments:checkout')

    payment_channels = get_tripay_payment_channels()

    context = {
        'cart_items': cart_items,
        'total_course_price': total_course_price,
        'platform_fee': platform_fee,
        'voucher': voucher,
        'voucher_code': voucher_code,
        'total_price': total_price,
        'payment_channels': payment_channels,
        'bank_name': bank_name,
        'va_number': va_number,
        'payment_url': payment_url,
        'selected_payment_method': selected_payment_method,
        'merchant_ref': merchant_ref,
        'instructions': instructions,
        'expired_at': expired_at,
        'is_resume': is_resume,
    }
    return render(request, 'payments/checkout.html', context)


@login_required
def transaction_detail(request, merchant_ref):
    # Ambil transaksi user yang sesuai merchant_ref
    transaction = get_object_or_404(
        Transaction.objects.prefetch_related('courses'),
        merchant_ref=merchant_ref
    )

    # Bangun cart_items dummy dengan method get_course_price
    cart_items = []
    for course in transaction.courses.all():
        price = course.get_course_price()
        dummy_item = type('DummyCartItem', (object,), {
            'course': course,
            'price': price
        })()
        cart_items.append(dummy_item)

    # Hitung total course price, safety check kalau get_course_price bisa None
    total_course_price = sum(
        (course.get_course_price().portal_price if course.get_course_price() else Decimal('0.00'))
        for course in transaction.courses.all()
    )

    context = {
        'transaction': transaction,  # kirim object lengkap
        'cart_items': cart_items,
        'total_course_price': total_course_price,
        'platform_fee': transaction.platform_fee or Decimal('0.00'),
        'voucher': transaction.voucher or Decimal('0.00'),
        'total_price': transaction.total_amount or Decimal('0.00'),
        'bank_name': transaction.bank_name or '',
        'va_number': transaction.va_number or '',
        'payment_url': transaction.payment_url or '',
        'selected_payment_method': transaction.payment_method or '',
        'merchant_ref': transaction.merchant_ref,
        'instructions': transaction.instructions or [],  # asumsi sudah dalam bentuk list/dict siap render
        'expired_at': transaction.expired_at,
        'is_resume': True,
    }
    return render(request, 'payments/transaction_detail.html', context)

@login_required
def cart_item_delete(request, pk):
    if not request.user.is_authenticated:
        return redirect("/login/?next=%s" % request.path)
    item = get_object_or_404(CartItem, pk=pk, user=request.user)
    item.delete()
    messages.success(request, 'The item was successfully removed from the cart.')
    return redirect('payments:view_cart')

@login_required
def transaction_history(request):
    user = request.user

    # Validasi data diri wajib
    required_fields = {
        'first_name': 'First Name',
        'last_name': 'Last Name',
        'email': 'Email',
        'phone': 'Phone Number',
        'gender': 'Gender',
        'birth': 'Date of Birth',
    }

    missing_fields = [
        label for field, label in required_fields.items()
        if not getattr(user, field, None)
        or (isinstance(getattr(user, field), str) and not getattr(user, field).strip())
    ]

    if missing_fields:
        messages.warning(
            request,
            f"Please complete your profile before accessing microcredentials: {', '.join(missing_fields)}"
        )
        return redirect('authentication:edit-profile', pk=user.pk)
    
    # 1️⃣ Update status pending yang sudah kadaluarsa → Ubah ke 'cancelled' untuk konsistensi
    expire_limit = timezone.now() - timedelta(hours=1)
    Payment.objects.filter(status='pending', created_at__lt=expire_limit).update(status='cancelled')
    Transaction.objects.filter(status='pending', created_at__lt=expire_limit).update(status='cancelled')

    # 2️⃣ Ambil filter status → Ubah 'paid' ke 'completed', dan 'expired' ke 'cancelled'
    status_filter = request.GET.get('status', 'all')
    VALID_STATUSES = ['completed', 'pending', 'failed', 'cancelled']  # Konsisten dengan webhook

    # 3️⃣ Ambil transaksi user
    transactions = Transaction.objects.filter(user=request.user)
    if status_filter in VALID_STATUSES:
        transactions = transactions.filter(status=status_filter)
    elif status_filter != 'all':
        messages.warning(request, "Status filter tidak dikenali. Menampilkan semua transaksi.")
        status_filter = 'all'

    # 4️⃣ Hitung total → Ubah 'paid' ke 'completed'
    total_completed = transactions.filter(status='completed').aggregate(total=Sum('total_amount'))['total'] or 0
    total_pending = transactions.filter(status='pending').aggregate(total=Sum('total_amount'))['total'] or 0

    context = {
        'transactions': transactions.order_by('-created_at'),
        'total_transactions': transactions.count(),
        'total_completed': total_completed,  # Ubah nama variabel untuk clarity
        'total_pending': total_pending,
        'selected_status': status_filter,
    }
    return render(request, 'payments/transaction_history.html', context)



#untuk user mengunduh invoice pdf
@login_required
def transaction_invoice_detail(request, pk):
    transaction = get_object_or_404(
        Transaction.objects.prefetch_related('courses__org_partner'),
        pk=pk,
        user=request.user
    )

    # ✅ Validasi status: Hanya izinkan untuk 'completed' (konsisten dengan webhook & history)
    if transaction.status != 'completed':
        messages.warning(
            request,
            f"Invoice hanya tersedia untuk transaksi yang sudah completed. Status saat ini: {transaction.status.title()}."
        )
        return redirect('payments:transaction_history')  # Atau halaman history

    # Ambil unique partners (handle multiple courses/partners)
    partners = transaction.courses.values_list('org_partner', flat=True).distinct()
    partner = None
    if partners:
        partner = Partner.objects.get(id=partners[0])  # Atau loop kalau multiple, tapi untuk sekarang ambil first

    if request.GET.get('download') == 'pdf':
        # Tambah logger untuk debug
        logger.info(f"Generating PDF for transaction {pk} (status: {transaction.status})")
        
        html_string = render_to_string('payments/invoice_pdf.html', {
            'transaction': transaction,
            'partner': partner,
            'request': request,
        })
        html = HTML(string=html_string, base_url=request.build_absolute_uri())
        pdf = html.write_pdf()

        invoice_number = f"INV{transaction.created_at.strftime('%Y%m%d')}{transaction.id}"
        response = HttpResponse(pdf, content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="{invoice_number}.pdf"'
        return response

    return render(request, 'payments/invoice_detail.html', {
        'transaction': transaction,
        'partner': partner,
    })