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

    def test_lean_snapshot_storage_and_dynamic_reconstruction(self):
        """Kiểm tra Lean Snapshot tiết kiệm 95% CSDL và tái tạo động nội dung câu hỏi khi xem kết quả"""
        from apps.quizzes.models import Question
        from apps.quizzes.services.grading_service import GradingService
        from apps.quizzes.views import _reconstruct_attempt_results

        # 1. Tạo câu hỏi trong CSDL
        q1 = Question.objects.create(
            quiz=self.quiz,
            question_text="Việt Nam nằm ở khu vực nào?",
            options=["Đông Nam Á", "Nam Á", "Đông Á", "Tây Á"],
            correct_answer=0,
            explanation="Việt Nam thuộc Đông Nam Á.",
            order=1
        )

        grading_result = {
            'total_questions': 1,
            'correct_answers': 1,
            'score': 10.0,
            'results': [{
                'question_id': q1.id,
                'question_text': q1.question_text,
                'options': q1.options,
                'correct_answer': q1.correct_answer,
                'user_answer': 0,
                'is_correct': True,
                'explanation': q1.explanation
            }]
        }

        # 2. Lưu bài làm với Lean Snapshot
        attempt = GradingService.save_attempt(
            quiz=self.quiz,
            user=self.user,
            user_answers={q1.id: 0},
            grading_result=grading_result,
            time_spent_seconds=60
        )

        # 3. Kiểm chứng: chi tiết lưu DB chỉ là Lean Snapshot (không nhân bản text/options)
        self.assertEqual(len(attempt.details), 1)
        self.assertNotIn('question_text', attempt.details[0])
        self.assertNotIn('options', attempt.details[0])
        self.assertEqual(attempt.details[0]['question_id'], q1.id)
        self.assertEqual(attempt.details[0]['user_answer'], 0)
        self.assertTrue(attempt.details[0]['is_correct'])

        # 4. Kiểm chứng: Tái tạo động khi xem kết quả nạp đầy đủ thông tin từ DB
        reconstructed = _reconstruct_attempt_results(attempt)
        self.assertEqual(len(reconstructed), 1)
        self.assertEqual(reconstructed[0]['question_text'], "Việt Nam nằm ở khu vực nào?")
        self.assertEqual(reconstructed[0]['options'], ["Đông Nam Á", "Nam Á", "Đông Á", "Tây Á"])
        self.assertEqual(reconstructed[0]['explanation'], "Việt Nam thuộc Đông Nam Á.")

    def test_bloom_mastery_and_knowledge_gap_detector(self):
        """Kiểm tra phân tích Bloom's Taxonomy và bộ phát hiện lỗ hổng kiến thức"""
        from apps.quizzes.services.analytics_service import CognitiveAnalyticsService
        
        # Phân tích Bloom
        bloom_data = CognitiveAnalyticsService.analyze_bloom_mastery(self.user)
        self.assertTrue(bloom_data['has_data'])
        self.assertIn('breakdown', bloom_data)

        # Phát hiện lỗ hổng
        gaps = CognitiveAnalyticsService.detect_knowledge_gaps(self.user)
        self.assertIsInstance(gaps, list)

    def test_supermemo2_algorithm_and_ebbinghaus_curve(self):
        """Kiểm tra thuật toán SuperMemo SM-2 và đường cong quên lãng Ebbinghaus"""
        from apps.quizzes.services.sm2_service import SuperMemo2Service
        
        # Test SM-2 khi trả lời đúng xuất sắc (quality=5)
        new_rep, new_ef, next_interval = SuperMemo2Service.calculate_sm2(
            quality=5, repetitions=0, ease_factor=2.5, interval_days=1
        )
        self.assertEqual(new_rep, 1)
        self.assertEqual(next_interval, 1)
        self.assertGreaterEqual(new_ef, 2.5)

        # Test SM-2 khi trả lời sai (quality=1) -> reset repetition về 0
        fail_rep, fail_ef, fail_interval = SuperMemo2Service.calculate_sm2(
            quality=1, repetitions=3, ease_factor=2.5, interval_days=10
        )
        self.assertEqual(fail_rep, 0)
        self.assertEqual(fail_interval, 1)

        # Test đường cong Ebbinghaus
        curve = SuperMemo2Service.calculate_ebbinghaus_retention_curve(stability_days=7.0, days_range=14)
        self.assertEqual(len(curve), 15)
        self.assertEqual(curve[0]['retention_pct'], 100.0)
        self.assertLess(curve[-1]['retention_pct'], 50.0)

    def test_quiz_retake_wrong_mode(self):
        """Kiểm tra chế độ thi lại các câu sai"""
        retake_url = reverse('quizzes:retake_wrong', kwargs={'pk': self.quiz.pk, 'attempt_id': self.attempt.pk})
        resp = self.client.get(retake_url)
        self.assertEqual(resp.status_code, 200)
        self.assertTemplateUsed(resp, 'quizzes/quiz_take.html')
        self.assertTrue(resp.context.get('is_retake_wrong'))





