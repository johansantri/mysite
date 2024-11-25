from django.contrib import admin
from .models import Question, Choice, Score, AttemptedQuestion

class ChoiceInline(admin.TabularInline):
    model = Choice
    extra = 4

class QuestionAdmin(admin.ModelAdmin):
    inlines = [ChoiceInline]

admin.site.register(Question, QuestionAdmin)
admin.site.register(Score)
admin.site.register(AttemptedQuestion)
class ScoreAdmin(admin.ModelAdmin):
    list_display = ('user', 'score', 'total_questions', 'grade', 'date')
    list_filter = ('grade', 'date')