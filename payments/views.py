# payments/views.py

from django.shortcuts import render
from django.db.models import Sum
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.shortcuts import get_object_or_404, redirect
from django.contrib import messages
import logging
from courses.models import Course,CoursePrice
from payments.models import CartItem,Transaction,Payment  # pastikan model keranjang belanja kamu ini
from django.utils.timezone import now
from django.db import IntegrityError

logger = logging.getLogger(__name__)
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

    # Cek apakah pembayaran sudah selesai
    if Payment.objects.filter(
        user=request.user,
        course=course,
        payment_model=payment_model,
        status='completed'
    ).exists():
        messages.info(request, f"Payment for {payment_type} already completed.")
        if payment_type == 'exam':
            return redirect('courses:course_learn', username=request.user.username, slug=course.slug)
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
    if not request.user.is_authenticated:
        return redirect("/login/?next=%s" % request.path)
    cart_items = CartItem.objects.select_related('course').filter(user=request.user)

    if not cart_items.exists():
        messages.info(request, "Your cart is empty.")
        return redirect('payments:view_cart')

    total_price = sum(item.course.get_course_price().user_payment for item in cart_items)

    if request.method == 'POST':
        # Buat transaksi baru dengan status awal
        transaction = Transaction.objects.create(
            user=request.user,
            total_amount=total_price,
            status='pending',  # ganti jadi 'paid' jika pembayaran otomatis
            description='Course purchase',
        )

        # Tambahkan courses ke transaksi
        for item in cart_items:
            transaction.courses.add(item.course)

            # Enroll hanya jika course harus dibayar dulu DAN transaksinya sudah paid
            if item.course.payment_model == 'buy_first' and transaction.status == 'paid':
                item.course.enroll_user(request.user)

        # Kosongkan keranjang setelah checkout
        cart_items.delete()

        # Feedback untuk user berdasarkan status
        if transaction.status == 'paid':
            messages.success(request, "Checkout successful. You have been enrolled in your courses.")
        else:
            messages.success(request, "Checkout pending. Please complete the payment to access your courses.")

        return redirect('authentication:dashbord')  # redirect ke dashboard atau halaman course user

    context = {
        'cart_items': cart_items,
        'total_price': total_price,
    }
    return render(request, 'payments/checkout.html', context)


@login_required
def cart_item_delete(request, pk):
    if not request.user.is_authenticated:
        return redirect("/login/?next=%s" % request.path)
    item = get_object_or_404(CartItem, pk=pk, user=request.user)
    item.delete()
    return redirect('payments:view_cart')

@login_required
def transaction_history(request):
    if not request.user.is_authenticated:
        return redirect("/login/?next=%s" % request.path)
    status_filter = request.GET.get('status', 'all')
    transactions = Transaction.objects.filter(user=request.user)

    if status_filter in ['paid', 'pending', 'failed']:
        transactions = transactions.filter(status=status_filter)

    total_paid = transactions.filter(status='paid').aggregate(Sum('total_amount'))['total_amount__sum'] or 0
    total_pending = transactions.filter(status='pending').aggregate(Sum('total_amount'))['total_amount__sum'] or 0

    context = {
        'transactions': transactions.order_by('-created_at'),
        'total_transactions': transactions.count(),
        'total_paid': total_paid,
        'total_pending': total_pending,
        'selected_status': status_filter
    }
    return render(request, 'payments/transaction_history.html', context)