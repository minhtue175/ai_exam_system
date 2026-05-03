from django.db import models
from django.conf import settings
from apps.core.models import TimeStampedModel

class Quiz(TimeStampedModel):
    """Quiz generated from document"""
    
    DIFFICULTY_CHOICES = [
        ('basic', 'Cơ Bản'),
        ('advanced', 'Nâng Cao'),
    ]
    
    document = models.ForeignKey(
        'documents.Document',
        on_delete=models.SET_NULL, 
        null=True,                 
        blank=True,                
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
        default='basic'
    )
    
    class Meta:
        db_table = 'quizzes'
        ordering = ['-created_at']
        verbose_name_plural = 'Quizzes'
        # THÊM INDEX TẠI ĐÂY
        indexes = [
            models.Index(fields=['user', '-created_at'], name='idx_quiz_user_created'),
        ]
    
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
        # THÊM INDEX TẠI ĐÂY
        indexes = [
            models.Index(fields=['quiz', 'order'], name='idx_question_quiz_order'),
        ]
    
    def __str__(self):
        return f"Q{self.order}: {self.question_text[:50]}..."
    
    def get_correct_answer_text(self):
        """Get the text of correct answer"""
        try:
            return self.options[self.correct_answer]
        except (IndexError, TypeError):
            return "Không xác định"


class UserQuizAttempt(TimeStampedModel):
    """User's attempt at a quiz (Lưu kết quả làm bài)"""
    
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
    
    
    answers = models.JSONField(default=dict, blank=True) 
    
    
    details = models.JSONField(null=True, blank=True)
    
  
    total_questions = models.IntegerField(default=0)
    correct_answers = models.IntegerField(default=0)
    score = models.DecimalField(max_digits=5, decimal_places=2, default=0.00) # Điểm hệ 10 hoặc 100
    
  
    completed_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        db_table = 'user_quiz_attempts'
        ordering = ['-created_at']
    
        indexes = [
            models.Index(fields=['user', 'quiz', '-created_at'], name='idx_attempt_user_quiz'),
        ]
    
    def __str__(self):
        return f"{self.user.username} - {self.quiz.title} - {self.score} điểm"