"""
Service để chấm điểm quiz
"""
from typing import Dict, List
from ..models import Quiz, UserQuizAttempt
from django.utils import timezone
import logging

logger = logging.getLogger(__name__)

class GradingService:
    """Grade quiz attempts and calculate scores"""
    
    @staticmethod
    def grade_shuffled_quiz(
        shuffled_questions: List[Dict],
        user_answers: Dict[int, int]
    ) -> Dict:
        """
        Grade user's quiz attempt based on SHUFFLED questions
        """
        total = len(shuffled_questions)
        correct = 0
        results = []
        
        for q in shuffled_questions:
            q_id = q['id']
            user_answer = user_answers.get(q_id, -1)
            
           
            is_correct = (user_answer == q['correct_answer'])
            
            if is_correct:
                correct += 1
            
            results.append({
                'question_id': q_id,
                'question_text': q['question_text'],
                'options': q['options'],
                'correct_answer': q['correct_answer'],
                'user_answer': user_answer,
                'is_correct': is_correct,
                'explanation': q.get('explanation', '')
            })
        

        score = (correct / total * 10) if total > 0 else 0
        
        return {
            'total_questions': total,
            'correct_answers': correct,
            'score': round(score, 2),
            'results': results
        }
    
    @staticmethod
    def save_attempt(
        quiz: Quiz,
        user,
        user_answers: Dict[int, int],
        grading_result: Dict
    ) -> UserQuizAttempt:
        """Save quiz attempt to database"""
        attempt = UserQuizAttempt.objects.create(
            quiz=quiz,
            user=user,
            answers=user_answers,
            
            total_questions=grading_result['total_questions'],
            correct_answers=grading_result['correct_answers'],
            details=grading_result['results'], # Đẩy cục JSON vào DB
            score=grading_result['score'],
            completed_at=timezone.now()
        )
        
        logger.info(f"Quiz attempt saved: User={user.username}, Score={attempt.score}")
        
        return attempt
    
    @staticmethod
    def get_user_attempts(user, quiz=None):
        """Get all attempts by user"""
        attempts = UserQuizAttempt.objects.filter(user=user)
        
        if quiz:
            attempts = attempts.filter(quiz=quiz)
        
        return attempts.select_related('quiz', 'quiz__document').order_by('-created_at')