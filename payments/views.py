# payments/views.py

from django.shortcuts import render
from django.db.models import Sum
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.shortcuts import get_object_or_404, redirect
from django.contrib import messages

from courses.models import Course
from payments.models import CartItem,Transaction  # pastikan model keranjang belanja kamu ini
from django.utils.timezone import now

@login_required
@require_POST
def add_to_cart(request, course_id):
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
    item = get_object_or_404(CartItem, pk=pk, user=request.user)
    item.delete()
    return redirect('payments:view_cart')

@login_required
def transaction_history(request):
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