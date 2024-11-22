from django.db import models

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
    user = models.CharField(max_length=255, blank=True, null=True)  # Optional user identifier
    score = models.IntegerField()
    total_questions = models.IntegerField()
    grade = models.CharField(max_length=2)  # Add grade field (e.g., "A", "B", etc.)
    date = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user or 'Anonymous'} - {self.score}/{self.total_questions} ({self.grade}) on {self.date.strftime('%Y-%m-%d')}"