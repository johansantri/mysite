from django.urls import path
from .views import quiz_view, check_answer, quiz_result,score_list,restart_quiz,question_history

urlpatterns = [
    path('quiz', quiz_view, name='quiz'),
    path('check/<int:question_id>/', check_answer, name='check_answer'),
    path('result/', quiz_result, name='quiz_result'),
    path('scores/', score_list, name='score_list'),
    path('restart/', restart_quiz, name='restart_quiz'),
    path('history/', question_history, name='question_history'),
]
