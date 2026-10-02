from django.contrib import admin
from .models import Quiz, Question, UserQuizAttempt, ReviewCard


class QuestionInline(admin.StackedInline):
    model = Question
    extra = 0
    fields = ['order', 'question_text', 'options', 'correct_answer', 'explanation']
    readonly_fields = ['order']
    show_change_link = True


@admin.register(Quiz)
class QuizAdmin(admin.ModelAdmin):
    list_display = ['id', 'title', 'user', 'num_questions', 'difficulty', 'created_at']
    list_filter = ['difficulty', 'created_at']
    search_fields = ['title', 'user__username', 'user__email']
    raw_id_fields = ['user', 'document']
    readonly_fields = ['created_at', 'updated_at']
    inlines = [QuestionInline]
    list_per_page = 25


@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = ['id', 'quiz', 'order', 'short_question_text', 'correct_answer']
    list_filter = ['quiz__difficulty']
    search_fields = ['question_text', 'quiz__title']
    raw_id_fields = ['quiz']
    list_per_page = 30

    @admin.display(description="Nội dung câu hỏi")
    def short_question_text(self, obj):
        if len(obj.question_text) > 80:
            return f"{obj.question_text[:80]}..."
        return obj.question_text


@admin.register(UserQuizAttempt)
class UserQuizAttemptAdmin(admin.ModelAdmin):
    list_display = [
        'id', 
        'user', 
        'display_quiz_name', 
        'score', 
        'correct_answers', 
        'total_questions', 
        'time_spent_display',
        'completed_at'
    ]
    list_filter = ['completed_at']
    search_fields = ['user__username', 'user__email', 'quiz_title', 'quiz__title']
    raw_id_fields = ['user', 'quiz']
    readonly_fields = ['created_at', 'updated_at', 'completed_at', 'answers', 'details']
    list_per_page = 25

    @admin.display(description="Tên đề thi")
    def display_quiz_name(self, obj):
        return obj.display_title

    @admin.display(description="Thời gian làm")
    def time_spent_display(self, obj):
        return obj.formatted_time_spent


@admin.register(ReviewCard)
class ReviewCardAdmin(admin.ModelAdmin):
    list_display = [
        'id', 
        'user', 
        'review_mode', 
        'box_level', 
        'next_review_at', 
        'review_count',
        'is_mastered'
    ]
    list_filter = ['box_level', 'review_mode', 'is_mastered']
    search_fields = ['user__username', 'question__question_text']
    raw_id_fields = ['user', 'question']
    readonly_fields = ['created_at', 'updated_at']
    list_per_page = 30
