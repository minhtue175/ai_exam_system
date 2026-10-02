from django.db import models
from django.conf import settings
from apps.core.models import TimeStampedModel

from django.contrib.postgres.indexes import GinIndex, OpClass

class Quiz(TimeStampedModel):
    """Quiz generated from document"""
    
    DIFFICULTY_CHOICES = [
        ('remember', '1. Nhớ (Remember) - Nhắc lại kiến thức, định nghĩa'),
        ('understand', '2. Hiểu (Understand) - Giải thích ý nghĩa, so sánh'),
        ('apply', '3. Áp dụng (Apply) - Vận dụng vào thực tế, tính toán'),
        ('analyze', '4. Phân tích (Analyze) - Chia nhỏ vấn đề, quan hệ nhân quả'),
        ('evaluate', '5. Đánh giá (Evaluate) - Nhận xét, phán đoán, tiêu chí'),
        ('create', '6. Sáng tạo (Create) - Tổng hợp, đề xuất giải pháp mới'),
        ('basic', 'Cơ Bản (Tổng hợp Nhớ & Hiểu)'),
        ('advanced', 'Nâng Cao (Tổng hợp Áp dụng & Phân tích)'),
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
    duration_minutes = models.IntegerField(
        default=15,
        help_text="Thời gian làm bài tính theo phút (0 = không giới hạn)"
    )
    
    class Meta:
        db_table = 'quizzes'
        ordering = ['-created_at']
        verbose_name_plural = 'Quizzes'
        # THÊM INDEX TẠI ĐÂY
        indexes = [
            models.Index(fields=['user', '-created_at'], name='idx_quiz_user_created'),
            GinIndex(OpClass('title', name='gin_trgm_ops'), name='idx_quiz_title_trgm'),
        ]
    
    def __str__(self):
        return f"{self.title} ({self.num_questions} câu)"

    def get_difficulty_display_badge(self):
        """Trả về class badge Bootstrap và nhãn hiển thị"""
        badges = {
            'remember': ('primary', '1. Nhớ'),
            'understand': ('info', '2. Hiểu'),
            'apply': ('success', '3. Áp dụng'),
            'analyze': ('warning text-dark', '4. Phân tích'),
            'evaluate': ('danger', '5. Đánh giá'),
            'create': ('dark', '6. Sáng tạo'),
            'basic': ('success', 'Cơ Bản'),
            'advanced': ('warning text-dark', 'Nâng Cao'),
        }
        return badges.get(self.difficulty, ('secondary', self.get_difficulty_display()))


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
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='attempts'
    )
    quiz_title = models.CharField(
        max_length=255,
        default='',
        blank=True,
        help_text="Lưu cố định tên đề thi lúc làm bài, chống mất dữ liệu khi đề gốc bị xóa"
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
    time_spent_seconds = models.IntegerField(default=0, help_text="Thời gian hoàn thành tính bằng giây")
    
  
    completed_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        db_table = 'user_quiz_attempts'
        ordering = ['-created_at']
    
        indexes = [
            models.Index(fields=['user', 'quiz', '-created_at'], name='idx_attempt_user_quiz'),
        ]
    
    def __str__(self):
        title = self.quiz.title if self.quiz else (self.quiz_title or "Đề đã xóa")
        return f"{self.user.username} - {title} - {self.score} điểm"

    @property
    def display_title(self):
        """Trả về tên đề thi hiển thị, có gắn cờ nếu đề đã bị xóa"""
        if self.quiz:
            return self.quiz.title
        if self.quiz_title:
            return f"{self.quiz_title} (Đã xóa)"
        return "Đề thi (Đã xóa)"


    @property
    def formatted_time_spent(self):
        """Định dạng thời gian làm bài dạng 'X phút Y giây' hoặc 'Y giây'"""
        if not self.time_spent_seconds or self.time_spent_seconds <= 0:
            return "Dưới 1 phút"
        mins, secs = divmod(self.time_spent_seconds, 60)
        if mins > 0:
            return f"{mins} phút {secs} giây" if secs > 0 else f"{mins} phút"
        return f"{secs} giây"



class ReviewCard(TimeStampedModel):
    """
    Thuật toán Spaced Repetition (Leitner System) Đa Chế Độ:
    1. Chế độ Ngắn Hạn (Cấp tốc ôn thi < 1 tuần, tính bằng giờ):
       - Ngăn 1: Sau 1 giờ (hoặc 2h, 4h, 6h tùy chọn)
       - Ngăn 2: Sau 6 giờ
       - Ngăn 3: Sau 24 giờ (1 ngày)
       - Ngăn 4: Sau 72 giờ (3 ngày)
       - Ngăn 5: Sau 144 giờ (6 ngày) -> Thành thạo ✅
    2. Chế độ Dài Hạn (Chu kỳ chuẩn > 1 tuần - 1 tháng, học ngoại ngữ/chứng chỉ):
       - Ngăn 1: Sau 1 ngày (24 giờ)
       - Ngăn 2: Sau 3 ngày (72 giờ)
       - Ngăn 3: Sau 7 ngày (1 tuần)
       - Ngăn 4: Sau 14 ngày (2 tuần)
       - Ngăn 5: Sau 30 ngày (1 tháng) -> Thành thạo ✅
    """
    REVIEW_MODE_CHOICES = [
        ('short_term', 'Ngắn hạn (< 1 tuần, tính bằng giờ)'),
        ('long_term', 'Dài hạn (1 tuần - 1 tháng)'),
    ]

    INTERVALS_HOURS = {
        'short_term': {
            1: 1,      # Ngăn 1: 1 giờ (có thể tùy chỉnh)
            2: 6,      # Ngăn 2: 6 giờ
            3: 24,     # Ngăn 3: 1 ngày (24 giờ)
            4: 72,     # Ngăn 4: 3 ngày (72 giờ)
            5: 144,    # Ngăn 5: 6 ngày (144 giờ) -> Thành thạo
        },
        'long_term': {
            1: 24,     # Ngăn 1: 1 ngày (24 giờ)
            2: 72,     # Ngăn 2: 3 ngày (72 giờ)
            3: 168,    # Ngăn 3: 7 ngày (1 tuần)
            4: 336,    # Ngăn 4: 14 ngày (2 tuần)
            5: 720,    # Ngăn 5: 30 ngày (1 tháng) -> Thành thạo
        }
    }
    MAX_BOX = 5

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='review_cards'
    )
    question = models.ForeignKey(
        Question,
        on_delete=models.CASCADE,
        related_name='review_cards'
    )
    review_mode = models.CharField(
        max_length=20,
        choices=REVIEW_MODE_CHOICES,
        default='short_term'
    )
    custom_first_interval_hours = models.IntegerField(
        default=1,
        help_text="Số giờ ôn lại cho Ngăn 1 ở chế độ ngắn hạn (VD: 1, 2, 4, 6 giờ)"
    )
    box_level = models.IntegerField(default=1)  # Leitner box 1-5
    next_review_at = models.DateTimeField(db_index=True)
    last_reviewed_at = models.DateTimeField(null=True, blank=True)
    review_count = models.IntegerField(default=0)
    is_mastered = models.BooleanField(default=False)

    class Meta:
        db_table = 'review_cards'
        unique_together = ('user', 'question')
        ordering = ['next_review_at', 'box_level']
        indexes = [
            models.Index(fields=['user', 'next_review_at'], name='idx_rev_user_next'),
            models.Index(fields=['user', 'box_level'], name='idx_rev_user_box'),
            models.Index(fields=['user', 'review_mode'], name='idx_rev_user_mode'),
        ]

    def __str__(self):
        return f"{self.user.username} - Q{self.question_id} (Hộp {self.box_level}, {self.review_mode})"

    def get_interval_hours(self) -> int:
        """Tính số giờ ôn tập cho ngăn hiện tại dựa trên chế độ"""
        mode = self.review_mode or 'short_term'
        intervals = self.INTERVALS_HOURS.get(mode, self.INTERVALS_HOURS['short_term'])
        
        if mode == 'short_term' and self.box_level == 1 and self.custom_first_interval_hours:
            return max(1, self.custom_first_interval_hours)
            
        return intervals.get(self.box_level, 1)

    def get_interval_display(self) -> str:
        """Mô tả chu kỳ thời gian thân thiện (Giờ / Ngày)"""
        hours = self.get_interval_hours()
        if hours < 24:
            return f"{hours} giờ"
        days = hours // 24
        return f"{days} ngày"

    def process_review(self, is_correct: bool, save: bool = True):
        """
        Cập nhật ngăn Leitner sau lượt ôn tập:
        - Đúng: Thăng cấp lên ngăn tiếp theo (tối đa ngăn 5 -> Đánh dấu Thành thạo)
        - Sai: Rớt ngay về ngăn 1
        """
        from django.utils import timezone
        from datetime import timedelta

        now = timezone.now()
        self.last_reviewed_at = now
        self.review_count += 1

        if is_correct:
            if self.box_level < self.MAX_BOX:
                self.box_level += 1
            if self.box_level >= self.MAX_BOX:
                self.is_mastered = True
        else:
            self.box_level = 1
            self.is_mastered = False

        hours = self.get_interval_hours()
        self.next_review_at = now + timedelta(hours=hours)
        if save:
            self.save()