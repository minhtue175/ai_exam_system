import tempfile
import os
from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.exceptions import ValidationError
from apps.documents.models import Document
from apps.documents.services.document_processor import DocumentProcessor

User = get_user_model()

class DocumentSecurityTests(TestCase):
    """Kiểm tra tính an toàn xử lý tài liệu, kiểm tra chữ ký file và chống IDOR"""

    def setUp(self):
        self.client = Client()
        self.user_a = User.objects.create_user(username='doc_owner', email='owner@example.com', password='Password123!')
        self.user_b = User.objects.create_user(username='doc_attacker', email='attacker@example.com', password='Password123!')
        
        # Tạo file tạm trên đĩa
        self.temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.pdf')
        self.temp_file.write(b'%PDF-1.4 fake content')
        self.temp_file.close()

        self.doc_a = Document.objects.create(
            user=self.user_a,
            filename='tailieu_a.pdf',
            file_path=self.temp_file.name,
            file_size=len(b'%PDF-1.4 fake content'),
            file_type='application/pdf',
            extracted_text='Nội dung tài liệu A',
            status='completed'
        )

    def tearDown(self):
        if os.path.exists(self.temp_file.name):
            try:
                os.remove(self.temp_file.name)
            except OSError:
                pass

    def test_magic_bytes_rejects_fake_pdf(self):
        """File đổi đuôi sang .pdf nhưng nội dung không phải PDF thật sẽ bị từ chối"""
        fake_pdf = SimpleUploadedFile(
            name='shell.pdf',
            content=b'<?php phpinfo(); ?>',
            content_type='application/pdf'
        )
        with self.assertRaises(ValidationError) as ctx:
            DocumentProcessor.validate_file(fake_pdf)
        self.assertIn('Nội dung file không đúng với định dạng', str(ctx.exception))

    def test_magic_bytes_accepts_valid_pdf(self):
        """File PDF có chữ ký %PDF- hợp lệ được chấp nhận"""
        valid_pdf = SimpleUploadedFile(
            name='valid_doc.pdf',
            content=b'%PDF-1.5 test document',
            content_type='application/pdf'
        )
        # Không bắn exception
        DocumentProcessor.validate_file(valid_pdf)

    def test_double_extension_rejected(self):
        """File chứa double extension nguy hiểm (như .php.pdf) bị từ chối"""
        dangerous_file = SimpleUploadedFile(
            name='exploit.php.pdf',
            content=b'%PDF-1.5 test',
            content_type='application/pdf'
        )
        with self.assertRaises(ValidationError) as ctx:
            DocumentProcessor.validate_file(dangerous_file)
        self.assertIn('nguy hiểm', str(ctx.exception))

    def test_document_download_idor_protection(self):
        """User B không thể tải tài liệu của User A"""
        self.client.login(username='doc_attacker', password='Password123!')
        url = reverse('documents:download', kwargs={'pk': self.doc_a.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)

    def test_extract_text_requires_post(self):
        """Gọi extract bằng GET sẽ bị từ chối 405 Method Not Allowed"""
        self.client.login(username='doc_owner', password='Password123!')
        url = reverse('documents:extract', kwargs={'pk': self.doc_a.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 405)
