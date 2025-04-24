# blog/urls.py
from django.urls import path
from . import views

app_name = 'blog'

urlpatterns = [
    path('blog/', views.BlogListView.as_view(), name='blog-list'),
    path('post/<slug:slug>/', views.BlogDetailView.as_view(), name='blog-detail'),
    path('blog/category/<slug:slug>/', views.CategoryPostListView.as_view(), name='category-posts'),
    path('tag/<slug:slug>/', views.TagPostListView.as_view(), name='tag-posts'),
    path('admin/posts/', views.BlogPostListAdminView.as_view(), name='blog-list-admin'),
    path('admin/post/create/', views.BlogPostCreateView.as_view(), name='blog-create'),
    path('admin/post/<int:pk>/update/', views.BlogPostUpdateView.as_view(), name='blog-update'),
    path('admin/post/<int:pk>/delete/', views.BlogPostDeleteView.as_view(), name='blog-delete'),
   
]