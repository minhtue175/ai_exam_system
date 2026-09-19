from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.urls import reverse
from apps.quizzes.models import Quiz, Question

User = get_user_model()

class ExportSecurityTests(TestCase):
    """Kiểm tra bảo mật kiểm soát truy cập và chống IDOR cho phân hệ Exports"""
    
    def setUp(self):
        self.client = Client()
        self.user_a = User.objects.create_user(username='usera', email='usera@example.com', password='Password123!')
        self.user_b = User.objects.create_user(username='userb', email='userb@example.com', password='Password123!')
        
        self.quiz_a = Quiz.objects.create(
            user=self.user_a,
            title='Đề thi mẫu User A',
            num_questions=1,
            difficulty='basic'
        )
        Question.objects.create(
            quiz=self.quiz_a,
            question_text='Câu hỏi 1?',
            options=['A', 'B', 'C', 'D'],
            correct_answer=0,
            explanation='Giải thích',
            order=1
        )

    def test_unauthenticated_export_denied(self):
        """Khách chưa đăng nhập không thể tải đề thi hoặc đáp án"""
        url_word = reverse('exports:export_word', kwargs={'quiz_id': self.quiz_a.id})
        url_pdf = reverse('exports:export_pdf', kwargs={'quiz_id': self.quiz_a.id})
        
        resp_word = self.client.get(url_word)
        self.assertEqual(resp_word.status_code, 302)
        self.assertIn('/users/login/', resp_word.url)
        
        resp_pdf = self.client.get(url_pdf)
        self.assertEqual(resp_pdf.status_code, 302)
        self.assertIn('/users/login/', resp_pdf.url)

    def test_idor_protection_user_b_cannot_export_user_a_quiz(self):
        """User B không thể tải đề thi của User A (chống IDOR)"""
        self.client.login(username='userb', password='Password123!')
        
        url_word = reverse('exports:export_word', kwargs={'quiz_id': self.quiz_a.id})
        url_pdf = reverse('exports:export_pdf', kwargs={'quiz_id': self.quiz_a.id})
        
        resp_word = self.client.get(url_word)
        self.assertEqual(resp_word.status_code, 404)
        
        resp_pdf = self.client.get(url_pdf)
        self.assertEqual(resp_pdf.status_code, 404)

    def test_owner_can_export_quiz(self):
        """User A tải đúng đề thi của chính mình thành công"""
        self.client.login(username='usera', password='Password123!')
        
        url_word = reverse('exports:export_word', kwargs={'quiz_id': self.quiz_a.id})
        resp_word = self.client.get(url_word)
        self.assertEqual(resp_word.status_code, 200)
        self.assertIn('attachment', resp_word['Content-Disposition'])
