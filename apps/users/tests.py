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

    def test_forgot_password_and_reset_confirm_flow(self):
        """Kiểm tra toàn bộ quy trình quên mật khẩu và đặt lại mật khẩu mới"""
        from django.contrib.auth.tokens import default_token_generator
        from django.utils.http import urlsafe_base64_encode
        from django.utils.encoding import force_bytes

        # 1. Gửi yêu cầu quên mật khẩu
        forgot_url = reverse('users:forgot_password')
        resp = self.client.post(forgot_url, {'email': 'test@example.com'})
        self.assertEqual(resp.status_code, 302)  # Redirect về login kèm flash message

        # 2. Tạo link confirm hợp lệ
        uidb64 = urlsafe_base64_encode(force_bytes(self.existing_user.pk))
        token = default_token_generator.make_token(self.existing_user)
        confirm_url = reverse('users:reset_password_confirm', kwargs={'uidb64': uidb64, 'token': token})

        # 3. GET trang confirm
        resp_get = self.client.get(confirm_url)
        self.assertEqual(resp_get.status_code, 200)

        # 4. POST đặt mật khẩu mới
        resp_post = self.client.post(confirm_url, {
            'new_password1': 'NewBrandPassword888!',
            'new_password2': 'NewBrandPassword888!'
        })
        self.assertEqual(resp_post.status_code, 302)

        # 5. Đăng nhập thử với mật khẩu mới
        login_resp = self.client.post(reverse('users:login'), {
            'username': 'existinguser',
            'password': 'NewBrandPassword888!'
        })
        self.assertEqual(login_resp.status_code, 302)

    def test_google_login_account_linking_and_unusable_password(self):
        """Kiểm tra Google OAuth: Tạo tài khoản mới với unusable password, và Account Linking với tài khoản cũ"""
        # Case 1: Tạo tài khoản mới qua Google
        resp = self.client.post(
            reverse('users:google_login'),
            data='{"email": "newbie@gmail.com", "name": "Newbie Google", "google_id": "12345"}',
            content_type='application/json'
        )
        self.assertEqual(resp.status_code, 200)
        self.assertJSONEqual(resp.content, {'status': 'success', 'redirect_url': reverse('core:dashboard')})

        google_user = User.objects.get(email='newbie@gmail.com')
        self.assertFalse(google_user.has_usable_password())

        # Thử đăng nhập form thường bằng password ngẫu nhiên -> phải hiện cảnh báo tài khoản Google
        self.client.logout()
        login_resp = self.client.post(reverse('users:login'), {
            'username': 'newbie',
            'password': 'SomeRandomPassword!'
        })
        self.assertEqual(login_resp.status_code, 200)
        msgs = list(login_resp.context['messages'])
        self.assertTrue(any('Google' in str(m) for m in msgs))

        # Case 2: Đăng nhập Google với email đã tồn tại (Account Linking)
        resp_link = self.client.post(
            reverse('users:google_login'),
            data='{"email": "test@example.com", "name": "Existing User", "google_id": "67890"}',
            content_type='application/json'
        )
        self.assertEqual(resp_link.status_code, 200)
        self.assertEqual(int(self.client.session['_auth_user_id']), self.existing_user.id)

