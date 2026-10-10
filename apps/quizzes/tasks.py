import logging
from celery import shared_task
from celery.exceptions import SoftTimeLimitExceeded
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from apps.documents.models import Document
from .services.quiz_service import QuizService

logger = logging.getLogger(__name__)
User = get_user_model()


def _send_failure_notification(user_id, error_message):
    """Gửi thông báo lỗi tới người dùng qua WebSocket"""
    try:
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            f"user_{user_id}",
            {
                'type': 'send_notification',
                'notification_type': 'error',
                'title': 'Không thể tạo đề thi ⚠️',
                'message': f"Đã xảy ra sự cố: {error_message[:120]}. Vui lòng thử lại sau.",
                'quiz_id': None,
                'url': None
            }
        )
    except Exception as notify_err:
        logger.warning(f"Không thể gửi thông báo lỗi qua WebSocket tới user_{user_id}: {notify_err}")


@shared_task(
    bind=True,
    queue='queue_ai',
    max_retries=2,
    default_retry_delay=10,
    time_limit=300,        # Giới hạn cứng: 5 phút
    soft_time_limit=240,   # Giới hạn mềm: 4 phút
)
def generate_quiz_task(self, document_id, user_id, num_questions, difficulty):
    """
    Task chạy ngầm: Dùng AI tạo đề thi từ Document với cơ chế Timeout và Retry an toàn
    """
    try:
        user = User.objects.get(id=user_id)
        document = Document.objects.get(id=document_id, user=user)
        
        logger.info(
            f"Bắt đầu tạo ngầm Quiz (lần thử {self.request.retries + 1}) "
            f"cho Document {document_id} - User {user.username}"
        )
        
        quiz_service = QuizService()
        quiz = quiz_service.create_quiz_from_document(
            document=document,
            user=user,
            num_questions=num_questions,
            difficulty=difficulty
        )
        
        logger.info(f"Tạo Quiz thành công! ID: {quiz.id}")
        
        # Gửi thông báo thành công qua WebSocket
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            f"user_{user.id}",
            {
                'type': 'send_notification',
                'notification_type': 'success',
                'title': 'Đề thi đã sẵn sàng! 🎉',
                'message': f"Đề thi '{quiz.title}' ({quiz.num_questions} câu) đã được AI hoàn thành!",
                'quiz_id': quiz.id,
                'url': f"/quizzes/{quiz.id}/"
            }
        )
        return quiz.id

    except SoftTimeLimitExceeded:
        err_msg = "Thời gian xử lý của AI vượt quá 4 phút. Vui lòng thử lại với tài liệu ngắn hơn hoặc ít câu hỏi hơn."
        logger.error(f"Task sinh đề bị quá thời gian (Doc ID {document_id}): {err_msg}")
        _send_failure_notification(user_id, err_msg)
        raise

    except ValidationError as e:
        err_msg = str(e)
        logger.warning(f"Lỗi kiểm tra dữ liệu khi tạo đề (Doc ID {document_id}): {err_msg}")
        _send_failure_notification(user_id, err_msg)
        raise

    except Exception as e:
        error_msg = str(e)
        logger.error(f"Lỗi khi chạy Celery Task tạo Quiz (Doc ID {document_id}, retry={self.request.retries}): {error_msg}")
        
        # Nếu còn lượt retry và không phải lỗi cấm retry
        if self.request.retries < self.max_retries:
            countdown = 10 * (2 ** self.request.retries)
            logger.info(f"Sẽ thử lại task tạo Quiz sau {countdown}s...")
            raise self.retry(exc=e, countdown=countdown)
        
        # Hết lượt retry -> gửi thông báo thất bại tới user
        _send_failure_notification(user_id, f"AI không thể hoàn thành đề thi sau nhiều lần thử: {error_msg}")
        raise e