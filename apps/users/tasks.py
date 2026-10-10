import logging
from celery import shared_task
from django.core.mail import send_mail
from django.conf import settings
from django.contrib.auth import get_user_model

logger = logging.getLogger(__name__)
User = get_user_model()


@shared_task(
    bind=True,
    queue='queue_high',
    max_retries=3,
    default_retry_delay=5,
    time_limit=30,
    soft_time_limit=20
)
def send_password_reset_email_task(self, user_id: int, reset_link: str, recipient_email: str):
    """
    Task chạy ngầm trên hàng đợi ưu tiên cao (queue_high):
    Gửi email chứa liên kết đặt lại mật khẩu với thời gian phản hồi tức thì (< 2s).
    """
    try:
        user = User.objects.get(id=user_id)
        subject = "[AI Exam System] Yêu cầu đặt lại mật khẩu của bạn"
        message = (
            f"Xin chào {user.username},\n\n"
            f"Hệ thống vừa nhận được yêu cầu đặt lại mật khẩu cho tài khoản liên kết với địa chỉ email này.\n"
            f"Vui lòng nhấn vào đường liên kết dưới đây để thiết lập mật khẩu mới (liên kết có hiệu lực trong 24 giờ):\n\n"
            f"{reset_link}\n\n"
            f"Nếu bạn không thực hiện yêu cầu này, vui lòng bỏ qua email. Mật khẩu hiện tại của bạn vẫn an toàn.\n\n"
            f"Trân trọng,\n"
            f"Đội ngũ AI Exam System"
        )
        
        send_mail(
            subject=subject,
            message=message,
            from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'no-reply@aiexam.local'),
            recipient_list=[recipient_email],
            fail_silently=False
        )
        logger.info(f"Đã gửi email khôi phục mật khẩu thành công tới: {recipient_email}")
        return True
    except Exception as exc:
        logger.error(f"Lỗi gửi email reset password tới {recipient_email}: {exc}")
        if self.request.retries < self.max_retries:
            raise self.retry(exc=exc, countdown=5 * (2 ** self.request.retries))
        raise exc


@shared_task(
    bind=True,
    queue='queue_high',
    max_retries=2,
    default_retry_delay=5,
    time_limit=30
)
def send_welcome_email_task(self, user_id: int):
    """
    Task gửi email chào mừng người dùng mới tham gia hệ thống (queue_high)
    """
    try:
        user = User.objects.get(id=user_id)
        subject = "[AI Exam System] Chào mừng bạn gia nhập nền tảng luyện thi AI!"
        message = (
            f"Xin chào {user.username},\n\n"
            f"Chúc mừng bạn đã tạo tài khoản thành công tại AI Exam System.\n"
            f"Bạn có thể bắt đầu tải lên tài liệu học tập để AI tự động sinh đề thi trắc nghiệm ngay bây giờ!\n\n"
            f"Trân trọng,\n"
            f"Đội ngũ AI Exam System"
        )
        send_mail(
            subject=subject,
            message=message,
            from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'no-reply@aiexam.local'),
            recipient_list=[user.email],
            fail_silently=True
        )
        return True
    except Exception as exc:
        logger.warning(f"Lỗi gửi email chào mừng cho user {user_id}: {exc}")
        return False
