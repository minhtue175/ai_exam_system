"""
Dịch vụ Sinh Chứng Chỉ Hoàn Thành Bài Thi (Certificate of Completion Generator):
Tạo file PDF chứng chỉ khổ ngang (A4 Landscape) với hoa văn trang nhã,
mã định danh chứng chỉ và chữ ký xác thực số.
"""
import io
import hashlib
from django.template.loader import render_to_string
from weasyprint import HTML
from apps.quizzes.models import UserQuizAttempt
import logging

logger = logging.getLogger(__name__)


class CertificateService:
    """Sinh chứng chỉ hoàn thành bài thi chuẩn chuyên nghiệp"""

    @classmethod
    def generate_certificate_code(cls, attempt: UserQuizAttempt) -> str:
        """Tạo mã xác thực chứng chỉ độc nhất dựa trên attempt ID và completed_at"""
        raw_str = f"CERT_{attempt.id}_{attempt.user.id}_{attempt.completed_at.timestamp()}"
        code_hash = hashlib.sha256(raw_str.encode('utf-8')).hexdigest()[:8].upper()
        return f"FLUESY-CERT-{attempt.id:04d}-{code_hash}"

    @classmethod
    def generate_certificate_pdf(cls, attempt: UserQuizAttempt) -> io.BytesIO:
        """Sinh file PDF chứng chỉ hoàn thành bài thi"""
        cert_code = cls.generate_certificate_code(attempt)

        context = {
            'attempt': attempt,
            'user': attempt.user,
            'cert_code': cert_code,
            'issue_date': attempt.completed_at.strftime("%d/%m/%Y"),
            'score': attempt.score,
            'quiz_title': attempt.display_title,
            'student_name': attempt.user.get_full_name() or attempt.user.username,
        }

        html_string = render_to_string('exports/certificate_template.html', context)
        buffer = io.BytesIO()
        HTML(string=html_string).write_pdf(buffer)
        buffer.seek(0)
        return buffer
