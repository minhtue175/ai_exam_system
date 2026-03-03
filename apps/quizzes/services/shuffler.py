"""
Thuật toán shuffle câu hỏi và đáp án
"""
import random
from typing import List, Dict


class QuestionShuffler:
    """Shuffle questions and options without duplicates"""
    
    @staticmethod
    def shuffle_questions(questions: List, seed: int = None) -> List:
        """
        Shuffle question order
        
        Args:
            questions: List of Question objects
            seed: Random seed for reproducibility
            
        Returns:
            Shuffled list
        """
        if seed:
            random.seed(seed)
        
        shuffled = list(questions)
        random.shuffle(shuffled)
        return shuffled
    
    @staticmethod
    def shuffle_options(question_dict: Dict) -> Dict:
        """
        Shuffle options while tracking correct answer
        
        Args:
            question_dict: {
                'question': str,
                'options': [str, str, str, str],
                'correct_answer': int
            }
            
        Returns:
            Question dict with shuffled options
        """
        options = question_dict['options'].copy()
        correct_index = question_dict['correct_answer']
        correct_option = options[correct_index]
        
        # Shuffle
        random.shuffle(options)
        
        # Find new position of correct answer
        new_correct_index = options.index(correct_option)
        
        return {
            **question_dict,
            'options': options,
            'correct_answer': new_correct_index
        }
    
    @classmethod
    def shuffle_quiz(cls, questions: List[Dict], seed: int = None) -> List[Dict]:
        """
        Shuffle both questions and their options
        
        Args:
            questions: List of question dicts
            seed: Random seed
            
        Returns:
            Fully shuffled quiz
        """
        if seed:
            random.seed(seed)
        
        # Shuffle question order
        shuffled_questions = cls.shuffle_questions(questions, seed)
        
        # Shuffle options within each question
        result = [cls.shuffle_options(q) for q in shuffled_questions]
        
        return result