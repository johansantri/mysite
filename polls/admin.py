from django.contrib import admin
from .models import Post
from .models import Comment
from .models import Question 
from .models import Choice

admin.site.register(Question)
admin.site.register(Comment)
admin.site.register(Choice)

#@admin.register(Post)
class PostAdmin(admin.ModelAdmin):
    list_display = ('title', 'slug', 'status','created_on')
    list_filter = ("status",)
    search_fields = ['title', 'content']
    prepopulated_fields = {'slug': ('title',)}

admin.site.register(Post, PostAdmin)

#@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    list_display=('name','email','post','created','active')
    list_filter=('active','created','update')
    search_fields=('name','email','body')