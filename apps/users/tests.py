from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.core.cache import cache
from apps.core.security import RateLimiter

User = get_user_model()

class UserSecurityTests(TestCase):
    """Kiểm tra tính an toàn đăng ký, đăng nhập và rate limit"""

    def setUp(self):
        cache.clear()
        self.client = Client()
        self.existing_user = User.objects.create_user(
            username='existinguser',
            email='test@example.com',
            password='TestPassword123!'
        )

    def test_duplicate_email_registration_fails_gracefully(self):
        """Đăng ký trùng email phải trả về lỗi form thân thiện, không làm crash hệ thống (lỗi 500)"""
        url = reverse('users:register')
        response = self.client.post(url, {
            'username': 'newuser',
            'email': 'test@example.com',
            'password1': 'NewPassword123!',
            'password2': 'NewPassword123!',
        })
        self.assertEqual(response.status_code, 200)
        form = response.context['form']
        self.assertTrue('email' in form.errors)
        self.assertIn('Email này đã được sử dụng', form.errors['email'][0])

    def test_brute_force_login_lockout(self):
        """Thử sai mật khẩu 5 lần liên tiếp sẽ kích hoạt cơ chế khóa tạm thời"""
        url = reverse('users:login')
        
        # Thử 5 lần sai mật khẩu
        for _ in range(5):
            self.client.post(url, {
                'username': 'existinguser',
                'password': 'WrongPassword999!'
            })
        
        # Lần thứ 6 phải bị chặn bởi rate limiter
        response = self.client.post(url, {
            'username': 'existinguser',
            'password': 'TestPassword123!'
        })
        self.assertEqual(response.status_code, 200)
        # Kiểm tra message khóa tạm thời
        messages = list(response.context['messages'])
        self.assertTrue(any('tạm khóa' in str(m) or 'quá nhiều lần' in str(m) for m in messages))
