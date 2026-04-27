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
       
        document = Document.objects.get(id=document_id)
        user = User.objects.get(id=user_id)
        
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
                'message': f"Ting ting! Đề thi '{quiz.title}' đã được hoàn thành. Chúc bạn làm bài tốt!"
            }
        )
    
        
        return quiz.id
        
    except Exception as e:
        logger.error(f"Lỗi khi chạy Celery Task tạo Quiz (Doc ID {document_id}): {str(e)}")
        raise e