from django.db import models
from django.conf import settings
from apps.core.models import TimeStampedModel


class Quiz(TimeStampedModel):
    """Quiz generated from document"""
    
    DIFFICULTY_CHOICES = [
        ('easy', 'Dễ'),
        ('medium', 'Trung bình'),
        ('hard', 'Khó'),
    ]
    
    document = models.ForeignKey(
        'documents.Document',
        on_delete=models.CASCADE,
        related_name='quizzes'
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='quizzes'
    )
    title = models.CharField(max_length=255)
    num_questions = models.IntegerField()
    difficulty = models.CharField(
        max_length=20,
        choices=DIFFICULTY_CHOICES,
        default='medium'
    )
    
    class Meta:
        db_table = 'quizzes'
        ordering = ['-created_at']
        verbose_name_plural = 'Quizzes'
    
    def __str__(self):
        return f"{self.title} ({self.num_questions} câu)"


class Question(models.Model):
    """Individual question in quiz"""
    
    quiz = models.ForeignKey(
        Quiz,
        on_delete=models.CASCADE,
        related_name='questions'
    )
    question_text = models.TextField()
    options = models.JSONField()  # ["Option A", "Option B", "Option C", "Option D"]
    correct_answer = models.IntegerField()  # Index: 0=A, 1=B, 2=C, 3=D
    explanation = models.TextField(blank=True, null=True)
    order = models.IntegerField(default=0)
    
    class Meta:
        db_table = 'questions'
        ordering = ['order', 'id']
    
    def __str__(self):
        return f"Q{self.order}: {self.question_text[:50]}..."
    
    def get_correct_answer_text(self):
        """Get the text of correct answer"""
        return self.options[self.correct_answer]


class UserQuizAttempt(TimeStampedModel):
    """User's attempt at a quiz"""
    
    quiz = models.ForeignKey(
        Quiz,
        on_delete=models.CASCADE,
        related_name='attempts'
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='quiz_attempts'
    )
    answers = models.JSONField()  # {question_id: selected_index}
    score = models.DecimalField(max_digits=5, decimal_places=2)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        db_table = 'user_quiz_attempts'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.user.username} - {self.quiz.title} - {self.score}%"