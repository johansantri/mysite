# payments/views.py

from django.shortcuts import render
from django.db.models import Sum, Count
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.shortcuts import get_object_or_404, redirect
from django.contrib import messages
import logging
from courses.models import Course,CoursePrice,Partner,Enrollment
from payments.models import CartItem,Transaction,Payment  # pastikan model keranjang belanja kamu ini
from django.utils.timezone import now
from django.db import IntegrityError
from django.contrib.auth.decorators import login_required, user_passes_test
from django.core.paginator import Paginator
from django.utils.http import urlencode
from django.db.models import Q
from django.utils import timezone
from datetime import timedelta
from .utils import get_client_ip, get_geo_from_ip



logger = logging.getLogger(__name__)

@login_required
@user_passes_test(lambda u: u.is_authenticated and (u.is_superuser or getattr(u, 'is_partner', False)))
def payment_detail_view(request, pk):
    payment = get_object_or_404(Payment.objects.select_related('user', 'course__org_partner'), pk=pk)
    return render(request, 'payments/payment_detail.html', {'payment': payment})


@login_required
@user_passes_test(lambda u: u.is_authenticated and (u.is_superuser or getattr(u, 'is_partner', False)))
def payment_report_view(request):
    user = request.user
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

    # ✅ Filter berdasarkan ID Transaksi
    search_query = request.GET.get('search', '').strip()
    if search_query.isdigit():
        payments = payments.filter(linked_transaction__id=search_query)



    # Ringkasan
    summary = payments.values('payment_model', 'status').annotate(
        total_amount=Sum('amount'),
        count=Count('id')
    ).order_by('payment_model', 'status')

    total_paid = payments.filter(status='completed').aggregate(total=Sum('amount'))['total'] or 0

    partner_courses = None
    if request.user.is_superuser:
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
        'page_obj': page_obj,
        'partners': Partner.objects.all() if request.user.is_superuser else None,
        'partner_courses': partner_courses,
        'search_query': search_query,
        'querystring': querystring,
    }
    return render(request, 'payments/payment_report.html', context)

def process_payment(request, course_id, payment_type='enrollment'):
    course = get_object_or_404(Course, id=course_id)
    logger.info(f"Processing payment for course {course_id}, payment_type: {payment_type}")

    # Petakan payment_type ke payment_model
    payment_model_map = {
        'enrollment': 'buy_first',
        'exam': 'pay_for_exam',
        'certificate': 'pay_for_certificate'
    }
    payment_model = payment_model_map.get(payment_type, 'buy_first')

    # Validasi payment_type
    if payment_type not in ['enrollment', 'exam', 'certificate']:
        messages.error(request, "Invalid payment type.")
        return redirect('courses:course_lms_detail', id=course.id, slug=course.slug)

    # Jika payment_type adalah exam atau certificate, arahkan user ke keranjang
    if payment_type in ['exam', 'certificate']:
        CartItem.objects.get_or_create(
            user=request.user,
            course=course,
            defaults={'added_at': timezone.now()}
        )
        messages.info(request, f"{course.course_name} telah ditambahkan ke keranjang. Silakan lanjutkan pembayaran melalui checkout.")
        return redirect('payments:view_cart')


    # Cek apakah pembayaran sudah selesai
    if Payment.objects.filter(
        user=request.user,
        course=course,
        payment_model=payment_model,
        status='completed'
    ).exists():
        messages.info(request, f"Payment for {payment_type} already completed.")
        if payment_type == 'exam':
            return redirect('learner:course_learn', username=request.user.username,id=course.id, slug=course.slug)
        elif payment_type == 'certificate':
            return redirect('courses:claim_certificate', course_id=course.id)
        return redirect('courses:course_lms_detail', id=course.id, slug=course.slug)

    # Ambil harga kursus
    course_price = CoursePrice.objects.filter(course=course, price_type__name=course.payment_model).first()
    if not course_price:
        messages.error(request, "Price not available for this course.")
        return redirect('courses:course_lms_detail', id=course.id, slug=course.slug)

    # Cek apakah ada entri Payment yang sudah ada dengan status pending atau failed
    existing_payment = Payment.objects.filter(
        user=request.user,
        course=course,
        payment_model=payment_model,
        status__in=['pending', 'failed']
    ).first()

    if existing_payment:
        # Perbarui entri yang sudah ada jika perlu
        existing_payment.amount = course_price.user_payment
        existing_payment.status = 'pending'
        existing_payment.save()
        payment = existing_payment
        logger.info(f"Reusing existing payment {payment.id} for user {request.user.username}, course {course.id}, payment_model: {payment_model}")
    else:
        # Buat entri Payment baru
        try:
            payment = Payment.objects.create(
                user=request.user,
                course=course,
                payment_model=payment_model,
                amount=course_price.user_payment,
                status='pending'
            )
            logger.info(f"Created new payment {payment.id} for user {request.user.username}, course {course.id}, payment_model: {payment_model}")
        except IntegrityError as e:
            logger.error(f"IntegrityError creating payment for user {request.user.username}, course {course.id}: {str(e)}")
            messages.error(request, "An error occurred while processing your payment. Please try again or contact support.")
            return redirect('courses:course_lms_detail', id=course.id, slug=course.slug)

    # Cek apakah ada Transaction yang terkait dengan payment
    transaction = None
    if payment.transaction_id:
        transaction = Transaction.objects.filter(id=payment.transaction_id, status='pending').first()

    if not transaction:
        # Buat entri Transaction baru
        transaction = Transaction.objects.create(
            user=request.user,
            total_amount=course_price.user_payment,
            status='pending',
            description=f"Payment for {payment_type} in course {course.course_name}"
        )
        transaction.courses.add(course)
        payment.transaction_id = str(transaction.id)
        payment.save()
        logger.info(f"Created new transaction {transaction.id} for payment {payment.id}")

    # Render halaman pembayaran
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
        messages.info(request, "Kursus ini gratis, silakan langsung daftar.")
        return redirect('courses:enroll', course_id=course.id)

    # Cek apakah sudah ada di cart
    cart_item, created = CartItem.objects.get_or_create(
        user=request.user,
        course=course,
        defaults={'added_at': now()}
    )

    if created:
        messages.success(request, f"{course.course_name} berhasil ditambahkan ke keranjang.")
    else:
        messages.info(request, f"{course.course_name} sudah ada di keranjang Anda.")

    return redirect('payments:view_cart')  # pastikan URL ini ada



@login_required
def view_cart(request):
    if not request.user.is_authenticated:
        return redirect("/login/?next=%s" % request.path)
    cart_items = CartItem.objects.select_related('course').filter(user=request.user)
    total_price = sum(item.course.get_course_price().user_payment for item in cart_items)

    context = {
        'cart_items': cart_items,
        'total_price': total_price,
    }
    return render(request, 'payments/cart.html', context)

@login_required
def checkout(request):
    cart_items = CartItem.objects.select_related('course').filter(user=request.user)

    if not cart_items.exists():
        messages.info(request, "Your cart is empty.")
        return redirect('payments:view_cart')

    total_price = sum(item.course.get_course_price().user_payment for item in cart_items)

    if request.method == 'POST':
        ip = get_client_ip(request)
        geo = get_geo_from_ip(ip)
        user_agent = request.META.get('HTTP_USER_AGENT', '')

        # Buat transaksi
        transaction = Transaction.objects.create(
            user=request.user,
            total_amount=total_price,
            status='pending',
            description='Course purchase',
        )
        for item in cart_items:
            transaction.courses.add(item.course)
            price = item.course.get_course_price()

            # Cek apakah payment sudah ada
            existing_payment = Payment.objects.filter(
                user=request.user,
                course=item.course,
                payment_model=item.course.payment_model,
            ).first()

            if existing_payment:
                if existing_payment.status in ['pending', 'failed']:
                    # Update jika sudah ada tapi belum berhasil
                    existing_payment.amount = price.user_payment
                    existing_payment.course_price = price
                    existing_payment.linked_transaction = transaction
                    existing_payment.status = 'pending'
                    existing_payment.snapshot_price = price.normal_price
                    existing_payment.snapshot_discount = price.discount_amount
                    existing_payment.snapshot_tax = price.tax
                    existing_payment.snapshot_ppn = price.ppn
                    existing_payment.snapshot_user_payment = price.user_payment
                    existing_payment.snapshot_partner_earning = price.partner_earning
                    existing_payment.snapshot_ice_earning = price.ice_earning
                    existing_payment.ip_address = ip
                    existing_payment.user_agent = user_agent
                    existing_payment.location = f"{geo['city']}, {geo['country']}" if geo else None
                    existing_payment.isp = geo['isp'] if geo else None
                    existing_payment.latitude = geo['lat'] if geo else None
                    existing_payment.longitude = geo['lon'] if geo else None
                    existing_payment.save()
                else:
                    # Lewati jika payment sudah completed
                    continue
            else:
                # Baru buat jika belum ada
                Payment.objects.create(
                    user=request.user,
                    course=item.course,
                    payment_model=item.course.payment_model,
                    status='pending',
                    amount=price.user_payment,
                    course_price=price,
                    snapshot_price=price.normal_price,
                    snapshot_discount=price.discount_amount,
                    snapshot_tax=price.tax,
                    snapshot_ppn=price.ppn,
                    snapshot_user_payment=price.user_payment,
                    snapshot_partner_earning=price.partner_earning,
                    snapshot_ice_earning=price.ice_earning,
                    linked_transaction=transaction,
                    ip_address=ip,
                    user_agent=user_agent,
                    location=f"{geo['city']}, {geo['country']}" if geo else None,
                    isp=geo['isp'] if geo else None,
                    latitude=geo['lat'] if geo else None,
                    longitude=geo['lon'] if geo else None,
                )    

        # Kosongkan keranjang
        cart_items.delete()

        if transaction.status == 'paid':
            for course in transaction.courses.all():
                Enrollment.objects.get_or_create(
                    user=request.user,
                    course=course,
                    defaults={
                        'enrolled_at': timezone.now(),
                        'certificate_issued': False,
                    }
                )
            

            messages.success(request, "Checkout successful. You have been enrolled in your courses.")
        else:
            messages.success(request, "Checkout pending. Please complete the payment to access your courses.")

        return redirect('authentication:dashbord')

    return render(request, 'payments/checkout.html', {
        'cart_items': cart_items,
        'total_price': total_price,
    })



@login_required
def cart_item_delete(request, pk):
    if not request.user.is_authenticated:
        return redirect("/login/?next=%s" % request.path)
    item = get_object_or_404(CartItem, pk=pk, user=request.user)
    item.delete()
    return redirect('payments:view_cart')

@login_required
def transaction_history(request):
    # 1️⃣ Update status pending yang sudah kadaluarsa
    expire_limit = timezone.now() - timedelta(hours=1)
    Payment.objects.filter(status='pending', created_at__lt=expire_limit).update(status='expired')
    Transaction.objects.filter(status='pending', created_at__lt=expire_limit).update(status='expired')

    # 2️⃣ Ambil filter status
    status_filter = request.GET.get('status', 'all')
    VALID_STATUSES = ['paid', 'pending', 'failed', 'expired']

    # 3️⃣ Ambil transaksi user
    transactions = Transaction.objects.filter(user=request.user)
    if status_filter in VALID_STATUSES:
        transactions = transactions.filter(status=status_filter)
    elif status_filter != 'all':
        messages.warning(request, "Status filter tidak dikenali. Menampilkan semua transaksi.")
        status_filter = 'all'

    # 4️⃣ Hitung total
    total_paid = transactions.filter(status='paid').aggregate(total=Sum('total_amount'))['total'] or 0
    total_pending = transactions.filter(status='pending').aggregate(total=Sum('total_amount'))['total'] or 0

    context = {
        'transactions': transactions.order_by('-created_at'),
        'total_transactions': transactions.count(),
        'total_paid': total_paid,
        'total_pending': total_pending,
        'selected_status': status_filter,
    }
    return render(request, 'payments/transaction_history.html', context)