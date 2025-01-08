from django.db import models
from courses.models import Course,Section,Material
from django.contrib.auth.models import User, Univer


class Question(models.Model):
    text = models.CharField(max_length=255)

    def __str__(self):
        return self.text

class Choice(models.Model):
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name='choices')
    text = models.CharField(max_length=255)
    is_correct = models.BooleanField(default=False)

    def __str__(self):
        return self.text
class Score(models.Model):
    user = models.CharField(max_length=255)  # Username or session key
    score = models.IntegerField()
    total_questions = models.IntegerField()
    grade = models.CharField(max_length=2, blank=True)
    time_taken = models.DurationField(null=True, blank=True)  # Store quiz duration
    date = models.DateTimeField(auto_now_add=True)
    submitted = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.user} - {self.score}/{self.total_questions} ({self.grade})"
    
class AttemptedQuestion(models.Model):
    user = models.CharField(max_length=255)  # Username or anonymous identifier
    question = models.ForeignKey('Question', on_delete=models.CASCADE)
    selected_choice = models.ForeignKey('Choice', on_delete=models.CASCADE)
    is_correct = models.BooleanField()
    date_attempted = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user} - {self.question.text} - {'Correct' if self.is_correct else 'Incorrect'}"