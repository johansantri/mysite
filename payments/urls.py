from django.urls import path
from . import views

app_name = 'payments'

urlpatterns = [
    path('add-to-cart/<int:course_id>/', views.add_to_cart, name='add_to_cart'),
    path('cart/', views.view_cart, name='view_cart'),  # contoh tampilan cart
    path('checkout/', views.checkout, name='checkout'),
    path('cart/delete/<int:pk>/', views.cart_item_delete, name='cart_item_delete'),
    path('transactions/', views.transaction_history, name='transaction_history'),
    path('course/<int:course_id>/payment/<str:payment_type>/', views.process_payment, name='process_payment'),
    path('payment-report/', views.payment_report_view, name='payment_report'),
]