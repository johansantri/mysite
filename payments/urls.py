from django.urls import path
from . import views

app_name = 'payments'

urlpatterns = [
    path('add-to-cart/<int:course_id>/course', views.add_to_cart, name='add_to_cart'),
    path('cart/', views.view_cart, name='view_cart'),  # contoh tampilan cart
    path('checkout/', views.checkout, name='checkout'),
    path('cart/delete/<int:pk>/', views.cart_item_delete, name='cart_item_delete'),
    path('transactions/', views.transaction_history, name='transaction_history'),
    path('transactions/<int:pk>/invoice/detail', views.transaction_invoice_detail, name='transaction_invoice_detail'),
    path('course/<int:course_id>/payment/<str:payment_type>/', views.process_payment, name='process_payment'),
    path('payment-report/', views.payment_report_view, name='payment_report'),
    path('report/<int:pk>/detail', views.payment_detail_view, name='payment_detail'),
    path('payments/tripay-callback/', views.tripay_webhook, name='tripay_webhook'),
    path('payments/return/', views.payment_return, name='payment_return'),
    
]