"""
Main business logic service for quiz management
"""
from django.core.exceptions import ValidationError
from django.db import transaction
from ..models import Quiz, Question
from .ai_generator import GeminiQuizGenerator
import logging

logger = logging.getLogger(__name__)

class QuizService:
    """Main business logic for quiz operations"""
    
    def __init__(self):
        self.ai_generator = GeminiQuizGenerator()

    @staticmethod
    def detect_subject_and_tags(filename: str, text: str) -> tuple[str, str]:
        """Tự động phân loại môn học và sinh tags dựa trên từ khóa"""
        name_lower = (filename + " " + (text[:1000] if text else "")).lower()
        if any(w in name_lower for w in ['lịch sử', 'chiến dịch', 'cách mạng', 'kháng chiến', 'thế chiến']):
            return 'Lịch Sử', 'lịch sử, kháng chiến, sự kiện'
        elif any(w in name_lower for w in ['toán', 'đạo hàm', 'tích phân', 'hình học', 'ma trận', 'đại số']):
            return 'Toán Học', 'toán học, công thức, bài tập'
        elif any(w in name_lower for w in ['vật lý', 'dao động', 'sóng cơ', 'quang học', 'điện xoay chiều']):
            return 'Vật Lý', 'vật lý, thí nghiệm, định luật'
        elif any(w in name_lower for w in ['hóa học', 'nguyên tử', 'phản ứng', 'axit', 'hữu cơ', 'vô cơ']):
            return 'Hóa Học', 'hóa học, phản ứng, liên kết'
        elif any(w in name_lower for w in ['tiếng anh', 'english', 'grammar', 'vocabulary', 'tense', 'reading']):
            return 'Tiếng Anh', 'tiếng anh, ngữ pháp, từ vựng'
        elif any(w in name_lower for w in ['sinh học', 'di truyền', 'tế bào', 'adn', 'sinh thái']):
            return 'Sinh Học', 'sinh học, tiến hóa, sinh thái'
        elif any(w in name_lower for w in ['python', 'java', 'lập trình', 'cơ sở dữ liệu', 'thuật toán', 'sql']):
            return 'Công Nghệ Thông Tin', 'công nghệ, lập trình, phần mềm'
        return 'Kiến Thức Chung', 'ôn tập, trắc nghiệm, tổng hợp'
    
    def create_quiz_from_document(
        self,
        document,
        user,
        num_questions: int = 10,
        difficulty: str = "medium"
    ) -> Quiz:
        """
        Create quiz from document using AI
        
        Args:
            document: Document instance
            user: User instance
            num_questions: Number of questions (1-40)
            difficulty: easy/medium/hard
            
        Returns:
            Created Quiz instance
        """
        # Validate document has extracted text
        if not document.extracted_text:
            raise ValidationError("Tài liệu chưa có nội dung được trích xuất!")
        
        # Validate inputs
        if num_questions < 1 or num_questions > 40:
            raise ValidationError("Số câu hỏi phải từ 1 đến 40")
        
        logger.info(f"Creating quiz from document: {document.filename}")
        
        try:
           
            questions_data = self.ai_generator.generate_questions(
                text_content=document.extracted_text,
                num_questions=num_questions,
                difficulty=difficulty
            )
            
            # Phân loại môn học và gắn thẻ chuyên môn tự động
            subject, tags = self.detect_subject_and_tags(document.filename, document.extracted_text)

            # Sử dụng transaction để đảm bảo tính toàn vẹn dữ liệu
            with transaction.atomic():
                # Create Quiz
                quiz = Quiz.objects.create(
                    document=document,
                    user=user,
                    title=f"Quiz: {document.filename}",
                    num_questions=len(questions_data),
                    difficulty=difficulty,
                    subject=subject,
                    tags=tags
                )
                
            
                questions_to_create = []
                for idx, q_data in enumerate(questions_data):
                    questions_to_create.append(
                        Question(
                            quiz=quiz,
                            question_text=q_data['question'],
                            options=q_data['options'],
                            correct_answer=q_data['correct_answer'],
                            explanation=q_data.get('explanation', ''),
                            order=idx + 1
                        )
                    )
                
        
                Question.objects.bulk_create(questions_to_create)
                
            logger.info(f"Quiz created successfully: ID={quiz.id}, Questions={len(questions_data)}")
            return quiz
            
        except ValidationError:
            raise
        except Exception as e:
            logger.error(f"Error creating quiz: {str(e)}")
            raise Exception(f"Lỗi khi tạo quiz: {str(e)}")
    
    def get_user_quizzes(self, user):
        """Get all quizzes created by user"""
        return Quiz.objects.filter(user=user).select_related('document').order_by('-created_at')
    
    def get_quiz_with_questions(self, quiz_id: int, user):
        """Get quiz with all questions"""
        try:
            return Quiz.objects.prefetch_related('questions').get(
                id=quiz_id,
                user=user
            )
        except Quiz.DoesNotExist:
            raise ValidationError("Quiz không tồn tại hoặc bạn không có quyền truy cập!")
    
    def delete_quiz(self, quiz_id: int, user) -> bool:
        """Delete quiz"""
        try:
            quiz = Quiz.objects.get(id=quiz_id, user=user)
            quiz.delete()
            logger.info(f"Quiz deleted: ID={quiz_id}")
            return True
        except Quiz.DoesNotExist:
            raise ValidationError("Quiz không tồn tại hoặc bạn không có quyền xóa!")