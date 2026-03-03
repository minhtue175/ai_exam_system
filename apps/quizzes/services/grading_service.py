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
    def grade_quiz(
        quiz: Quiz,
        user_answers: Dict[int, int]
    ) -> Dict:
        """
        Grade user's quiz attempt
        
        Args:
            quiz: Quiz instance
            user_answers: {question_id: selected_option_index}
            
        Returns:
            {
                'total_questions': int,
                'correct_answers': int,
                'score': float,
                'results': [...]
            }
        """
        questions = quiz.questions.all()
        total = len(questions)
        correct = 0
        results = []
        
        for question in questions:
            user_answer = user_answers.get(question.id, -1)
            is_correct = (user_answer == question.correct_answer)
            
            if is_correct:
                correct += 1
            
            results.append({
                'question_id': question.id,
                'question_text': question.question_text,
                'options': question.options,
                'correct_answer': question.correct_answer,
                'user_answer': user_answer,
                'is_correct': is_correct,
                'explanation': question.explanation
            })
        
        score = (correct / total * 100) if total > 0 else 0
        
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
        """
        Save quiz attempt to database
        
        Args:
            quiz: Quiz instance
            user: User instance
            user_answers: User's answers
            grading_result: Result from grade_quiz()
            
        Returns:
            UserQuizAttempt instance
        """
        attempt = UserQuizAttempt.objects.create(
            quiz=quiz,
            user=user,
            answers=user_answers,
            score=grading_result['score'],
            completed_at=timezone.now()
        )
        
        logger.info(f"Quiz attempt saved: User={user.username}, Score={attempt.score}%")
        
        return attempt
    
    @staticmethod
    def get_user_attempts(user, quiz=None):
        """Get all attempts by user"""
        attempts = UserQuizAttempt.objects.filter(user=user)
        
        if quiz:
            attempts = attempts.filter(quiz=quiz)
        
        return attempts.select_related('quiz', 'quiz__document').order_by('-created_at')