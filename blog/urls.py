# blog/urls.py
from django.urls import path
from . import views

app_name = 'blog'

urlpatterns = [
    path('blog/', views.BlogListView.as_view(), name='blog-list'),
    path('post/<slug:slug>/', views.BlogDetailView.as_view(), name='blog-detail'),
    path('blog/category/<slug:slug>/', views.CategoryPostListView.as_view(), name='category-posts'),
    path('tag/<slug:slug>/', views.TagPostListView.as_view(), name='tag-posts'),
   
   
]