from decimal import Decimal
from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.urls import reverse
from apps.documents.models import Document
from apps.quizzes.models import Quiz, UserQuizAttempt

User = get_user_model()

class QuizAttemptPreservationTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='teststudent',
            email='teststudent@example.com',
            password='Password123!'
        )
        self.client = Client()
        self.client.login(username='teststudent', password='Password123!')

        self.doc = Document.objects.create(
            user=self.user,
            filename='test_document.pdf',
            file_size=1024,
            file_type='application/pdf',
            status='completed'
        )

        self.quiz = Quiz.objects.create(
            user=self.user,
            document=self.doc,
            title='Đề thi thử Lịch Sử 12',
            num_questions=10,
            difficulty='basic'
        )

        self.attempt = UserQuizAttempt.objects.create(
            quiz=self.quiz,
            quiz_title=self.quiz.title,
            user=self.user,
            total_questions=10,
            correct_answers=8,
            score=Decimal('8.00'),
            time_spent_seconds=120,
            details=[
                {
                    'question_id': 1,
                    'question_text': 'Câu 1?',
                    'options': ['A', 'B', 'C', 'D'],
                    'user_answer': 0,
                    'correct_answer': 0,
                    'is_correct': True,
                    'explanation': 'Giải thích câu 1'
                }
            ]
        )

    def test_quiz_delete_preserves_attempt_and_title(self):
        """Xóa Quiz không xóa UserQuizAttempt (on_delete=SET_NULL), giữ nguyên quiz_title và display_title."""
        quiz_id = self.quiz.id
        quiz_title = self.quiz.title
        attempt_id = self.attempt.id

        # Xóa đề thi
        self.quiz.delete()

        # Attempt vẫn tồn tại trong DB
        self.assertTrue(UserQuizAttempt.objects.filter(id=attempt_id).exists())
        
        attempt_refreshed = UserQuizAttempt.objects.get(id=attempt_id)
        self.assertIsNone(attempt_refreshed.quiz)
        self.assertEqual(attempt_refreshed.quiz_title, quiz_title)
        self.assertEqual(attempt_refreshed.display_title, f"{quiz_title} (Đã xóa)")

    def test_quiz_result_view_works_when_quiz_is_deleted(self):
        """Trang xem lại kết quả thi hoạt động bình thường kể cả khi đề thi gốc đã bị xóa."""
        self.quiz.delete()

        response = self.client.get(reverse('quizzes:result', args=[self.attempt.id]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Đề thi thử Lịch Sử 12')
        self.assertContains(response, 'Đã xóa đề')
        # Đảm bảo không render nút thi lại khi đề đã bị xóa
        self.assertNotContains(response, 'Thi lại')

    def test_quiz_detail_view_shows_attempts_and_best_score(self):
        """Trang chi tiết đề thi hiển thị danh sách lịch sử làm bài và điểm cao nhất."""
        # Tạo thêm lần thi thứ 2 với điểm cao hơn
        UserQuizAttempt.objects.create(
            quiz=self.quiz,
            quiz_title=self.quiz.title,
            user=self.user,
            total_questions=10,
            correct_answers=10,
            score=Decimal('10.00'),
            time_spent_seconds=95
        )

        response = self.client.get(reverse('quizzes:detail', args=[self.quiz.id]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['attempts_count'], 2)
        self.assertEqual(response.context['best_score'], Decimal('10.00'))
        self.assertContains(response, 'Lịch Sử Làm Bài')
        self.assertContains(response, '2 lần thi')
        self.assertContains(response, 'Kỷ lục')
        self.assertIn('10', response.content.decode('utf-8'))

    def test_admin_registration(self):
        """Kiểm tra các model Quiz, Question, UserQuizAttempt, ReviewCard đã được đăng ký vào Django Admin."""
        from django.contrib import admin
        from apps.quizzes.models import Question, ReviewCard
        
        self.assertIn(Quiz, admin.site._registry)
        self.assertIn(Question, admin.site._registry)
        self.assertIn(UserQuizAttempt, admin.site._registry)
        self.assertIn(ReviewCard, admin.site._registry)

    def test_celery_task_timeout_and_retry_config(self):
        """Kiểm tra Celery task generate_quiz_task có đủ time_limit, soft_time_limit và max_retries."""
        from apps.quizzes.tasks import generate_quiz_task
        
        self.assertEqual(generate_quiz_task.time_limit, 300)
        self.assertEqual(generate_quiz_task.soft_time_limit, 240)
        self.assertEqual(generate_quiz_task.max_retries, 2)

    def test_gemini_key_pool_rotation(self):
        """Kiểm tra cơ chế xoay vòng và cooldown của GeminiKeyPool khi gặp lỗi quota 429."""
        from apps.quizzes.services.ai_generator import GeminiKeyPool
        keys = ['FAKE_KEY_1', 'FAKE_KEY_2', 'FAKE_KEY_3']
        pool = GeminiKeyPool(keys)
        
        self.assertEqual(len(pool.keys), 3)
        client, first_key = pool.get_healthy_client()
        self.assertIn(first_key, keys)
        
        # Đánh dấu first_key bị hết quota (429)
        pool.mark_key_exhausted(first_key, cooldown_seconds=60)
        self.assertIn(first_key, pool.cooldowns)
        
        # Lần lấy tiếp theo phải trả về key khác
        client2, second_key = pool.get_healthy_client()
        self.assertNotEqual(second_key, first_key)
        self.assertIn(second_key, ['FAKE_KEY_2', 'FAKE_KEY_3'])

    def test_ai_semantic_and_prompt_caching(self):
        """Kiểm tra hoạt động lưu và đọc bộ nhớ đệm AI Semantic Caching và TextRank Summary."""
        from apps.core.cache_utils import CacheManager
        
        sample_hash = "abc12345hash"
        sample_summary = ["Khái niệm 1", "Khái niệm 2"]
        sample_quiz = [
            {'question': 'Câu hỏi mẫu?', 'options': ['A', 'B', 'C', 'D'], 'correct_answer': 0}
        ]

        # 1. Test Summary Cache
        CacheManager.set_ai_summary(sample_hash, sample_summary)
        cached_sum = CacheManager.get_ai_summary(sample_hash)
        self.assertEqual(cached_sum, sample_summary)

        # 2. Test Quiz Prompt Cache
        CacheManager.set_ai_quiz(sample_hash, 10, 'remember', sample_quiz)
        cached_q = CacheManager.get_ai_quiz(sample_hash, 10, 'remember')
        self.assertEqual(cached_q, sample_quiz)



