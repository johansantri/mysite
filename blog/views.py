from django.views.generic import ListView, DetailView
from django.shortcuts import get_object_or_404, redirect
from .models import BlogPost, Tag, BlogComment
from .forms import NewCommentForm
from courses.models import Course, Category as CourseCategory

class BlogListView(ListView):
    model = BlogPost
    template_name = 'blog/blog_list.html'
    context_object_name = 'posts'
    paginate_by = 6

    def get_queryset(self):
        return BlogPost.objects.filter(status='published').order_by('-date_posted')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Kategori dengan postingan dan jumlah postingan
        categories = CourseCategory.objects.filter(blogpost__status='published').distinct()
        context['categories'] = [
            {'category': cat, 'post_count': cat.blogpost_set.filter(status='published').count()}
            for cat in categories
        ]
        # Tag dengan postingan
        context['tags'] = Tag.objects.filter(blogpost__status='published').distinct()
        return context


class BlogDetailView(DetailView):
    model = BlogPost
    template_name = 'blog/blog_detail.html'
    context_object_name = 'post'

    def get_queryset(self):
        return BlogPost.objects.filter(status='published')

    def get_object(self, queryset=None):
        obj = super().get_object(queryset)
        obj.views += 1
        obj.save()
        return obj

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['comments'] = self.object.comments.filter(parent__isnull=True).order_by('-date_posted')
        context['comment_form'] = NewCommentForm()
        categories = CourseCategory.objects.filter(blogpost__status='published').distinct()
        context['categories'] = [
            {'category': cat, 'post_count': cat.blogpost_set.filter(status='published').count()}
            for cat in categories
        ]
        tags = Tag.objects.filter(blogpost__status='published').distinct()
        context['tags'] = [
            {'tag': tag, 'post_count': tag.blogpost_set.filter(status='published').count()}
            for tag in tags
        ]
        # Filter kursus terkait yang memiliki id dan slug
        context['related_courses'] = self.object.related_courses.filter(id__isnull=False, slug__isnull=False).exclude(slug='')
        return context

    def post(self, request, *args, **kwargs):
        post = self.get_object()
        form = NewCommentForm(request.POST)
        if form.is_valid():
            comment = form.save(commit=False)
            comment.blogpost_connected = post
            parent_id = request.POST.get('parent_id')
            if parent_id:
                comment.parent = get_object_or_404(BlogComment, id=parent_id)
            comment.save()
            return redirect('blog:blog-detail', slug=post.slug)
        return self.get(request, *args, **kwargs)


class CategoryPostListView(ListView):
    model = BlogPost
    template_name = 'blog/blog_list.html'
    context_object_name = 'posts'
    paginate_by = 6

    def get_queryset(self):
        category = get_object_or_404(CourseCategory, slug=self.kwargs['slug'])
        return BlogPost.objects.filter(category=category, status='published').order_by('-date_posted')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        categories = CourseCategory.objects.filter(blogpost__status='published').distinct()
        context['categories'] = [
            {'category': cat, 'post_count': cat.blogpost_set.filter(status='published').count()}
            for cat in categories
        ]
        context['tags'] = Tag.objects.filter(blogpost__status='published').distinct()
        context['current_category'] = get_object_or_404(CourseCategory, slug=self.kwargs['slug'])
        return context

class TagPostListView(ListView):
    model = BlogPost
    template_name = 'blog/blog_list.html'
    context_object_name = 'posts'
    paginate_by = 6

    def get_queryset(self):
        tag = get_object_or_404(Tag, slug=self.kwargs['slug'])
        posts = BlogPost.objects.filter(tags=tag, status='published').order_by('-date_posted')
        print(f"Tag: {tag}, Posts: {posts}")  # Debugging
        return posts

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        categories = CourseCategory.objects.filter(blogpost__status='published').distinct()
        context['categories'] = [
            {'category': cat, 'post_count': cat.blogpost_set.filter(status='published').count()}
            for cat in categories
        ]
        context['tags'] = Tag.objects.filter(blogpost__status='published').distinct()
        context['current_tag'] = get_object_or_404(Tag, slug=self.kwargs['slug'])
        return context