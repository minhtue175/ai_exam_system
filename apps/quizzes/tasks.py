from celery import shared_task
from django.contrib.auth import get_user_model
from apps.documents.models import Document
from .services.quiz_service import QuizService
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync


import logging

logger = logging.getLogger(__name__)
User = get_user_model()

@shared_task
def generate_quiz_task(document_id, user_id, num_questions, difficulty):
    """
    Task chạy ngầm: Dùng AI tạo đề thi từ Document
    """
    try:
       
        user = User.objects.get(id=user_id)
        document = Document.objects.get(id=document_id, user=user)
        
        logger.info(f"Bắt đầu tạo ngầm Quiz cho Document {document_id} - User {user.username}")
        
     
        quiz_service = QuizService()
        quiz = quiz_service.create_quiz_from_document(
            document=document,
            user=user,
            num_questions=num_questions,
            difficulty=difficulty
        )
        
        logger.info(f"Tạo Quiz thành công! ID: {quiz.id}")
        
    
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            f"user_{user.id}", # Tên nhóm trùng với ID của user đang tạo đề
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
        
    except Exception as e:
        error_msg = str(e)
        logger.error(f"Lỗi khi chạy Celery Task tạo Quiz (Doc ID {document_id}): {error_msg}")
        try:
            channel_layer = get_channel_layer()
            async_to_sync(channel_layer.group_send)(
                f"user_{user_id}",
                {
                    'type': 'send_notification',
                    'notification_type': 'error',
                    'title': 'Không thể tạo đề thi ⚠️',
                    'message': f"Đã xảy ra sự cố khi sinh đề bằng AI: {error_msg[:120]}. Vui lòng kiểm tra lại tài liệu hoặc thử lại.",
                    'quiz_id': None,
                    'url': None
                }
            )
        except Exception as notify_err:
            logger.warning(f"Không thể gửi thông báo lỗi qua WebSocket tới user_{user_id}: {notify_err}")
        raise e