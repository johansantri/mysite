from django.views.generic import ListView, DetailView
from django.shortcuts import render,get_object_or_404, redirect
from .models import BlogPost, Tag, BlogComment
from .forms import NewCommentForm
from courses.models import Course, Category as CourseCategory
from django.urls import reverse
from django.contrib.auth.views import redirect_to_login

class BlogListView(ListView):
    model = BlogPost
    template_name = 'blog/blog_list.html'
    context_object_name = 'posts'
    paginate_by = 6

    def get_queryset(self):
        return BlogPost.objects.filter(status='published').order_by('-date_posted')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        categories = CourseCategory.objects.filter(blogpost__status='published').distinct()
        context['categories'] = [
            {
                'category': cat,
                'post_count': cat.blogpost_set.filter(status='published').count(),
                'url': reverse('blog:category-posts', kwargs={'slug': cat.slug})  # Sekarang menghasilkan /blog/category/<slug>/
            }
            for cat in categories
        ]
        tags = Tag.objects.filter(blogpost__status='published').distinct()
        context['tags'] = [
            {'tag': tag, 'post_count': tag.blogpost_set.filter(status='published').count()}
            for tag in tags
        ]
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
        
        # Fetch other posts in the same category (exclude the current post)
        context['related_posts'] = BlogPost.objects.filter(
            category=self.object.category
        ).exclude(id=self.object.id)[:5]  # Adjust the number as needed
        
        context['comments'] = self.object.comments.filter(parent__isnull=True).order_by('-date_posted')
        context['comment_form'] = NewCommentForm()
        
        categories = CourseCategory.objects.filter(blogpost__status='published').distinct()
        context['categories'] = [
            {
                'category': cat,
                'post_count': cat.blogpost_set.filter(status='published').count(),
                'url': reverse('blog:category-posts', kwargs={'slug': cat.slug})
            }
            for cat in categories
        ]
        
        tags = Tag.objects.filter(blogpost__status='published').distinct()
        context['tags'] = [
            {'tag': tag, 'post_count': tag.blogpost_set.filter(status='published').count()}
            for tag in tags
        ]
        
        # If you want to keep related courses as well
        context['related_courses'] = self.object.related_courses.filter(
            id__isnull=False, slug__isnull=False
        ).exclude(slug='')
        
        return context

    def post(self, request, *args, **kwargs):
        # Ensure the object is fetched
        self.object = self.get_object()  # Set self.object explicitly
        form = NewCommentForm(request.POST)

        if form.is_valid():
            if not request.user.is_authenticated:
                # Redirect to login with 'next' parameter to return to this page
                next_url = reverse('blog:blog-detail', kwargs={'slug': self.object.slug})
                return redirect_to_login(next_url, login_url='authentication:login')  # Use named URL 'login' or /accounts/login/
                
            # Save the comment for authenticated users
            comment = form.save(commit=False)
            comment.blogpost_connected = self.object
            comment.author = request.user  # Set the authenticated user as the author
            
            # Validate parent_id safely
            parent_id = request.POST.get('parent_id')
            if parent_id:
                try:
                    parent = get_object_or_404(BlogComment, id=int(parent_id), blogpost_connected=self.object)
                    comment.parent = parent
                except (ValueError, BlogComment.DoesNotExist):
                    # Invalid parent_id, ignore or handle as needed
                    pass
            
            comment.save()
            return redirect('blog:blog-detail', slug=self.object.slug)
        
        # If form is invalid, render the template with the form and context
        context = self.get_context_data()
        context['comment_form'] = form
        return render(request, self.template_name, context)


class CategoryPostListView(ListView):
    model = BlogPost
    template_name = 'blog/blog_list.html'
    context_object_name = 'posts'
    paginate_by = 6

    def get_queryset(self):
        category = get_object_or_404(CourseCategory, slug=self.kwargs['slug'])
        queryset = BlogPost.objects.filter(category=category, status='published').order_by('-date_posted')
        print(f"Category: {category}, Posts: {queryset}")  # Debugging
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        categories = CourseCategory.objects.filter(blogpost__status='published').distinct()
        context['categories'] = [
            {
                'category': cat,
                'post_count': cat.blogpost_set.filter(status='published').count(),
                'url': reverse('blog:category-posts', kwargs={'slug': cat.slug})  # Sekarang menghasilkan /blog/category/<slug>/
            }
            for cat in categories
        ]
        context['tags'] = Tag.objects.filter(blogpost__status='published').distinct()
        context['current_category'] = get_object_or_404(CourseCategory, slug=self.kwargs['slug'])
        print(f"Context keys: {context.keys()}")  # Debugging
        return context

    def render_to_response(self, context, **response_kwargs):
        print(f"Rendering template: {self.template_name}")  # Debugging
        return super().render_to_response(context, **response_kwargs)

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