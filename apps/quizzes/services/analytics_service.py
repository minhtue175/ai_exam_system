"""
Dịch vụ Phân Tích Nhận Thức & Phát Hiện Lỗ Hổng Kiến Thức (Cognitive Learning Analytics):
1. Bloom's Taxonomy Cognitive Mastery: Phân tích năng lực theo 6 cấp độ tư duy.
2. Knowledge Gap Detector: Nhận diện các khái niệm/chủ đề học viên thường xuyên làm sai.
"""
from typing import Dict, List, Any
from collections import defaultdict
from django.db.models import Avg, Count
from django.utils import timezone
from datetime import timedelta
import logging

from apps.quizzes.models import UserQuizAttempt, Question, Quiz

logger = logging.getLogger(__name__)


class CognitiveAnalyticsService:
    """Service phân tích học tập dựa trên Thang tư duy Bloom và Lỗ hổng kiến thức"""

    BLOOM_LABELS = {
        'remember': 'Nhớ (Remember)',
        'understand': 'Hiểu (Understand)',
        'apply': 'Vận Dụng (Apply)',
        'analyze': 'Phân Tích (Analyze)',
        'evaluate': 'Đánh Giá (Evaluate)',
        'create': 'Sáng Tạo (Create)',
        'basic': 'Cơ Bản (Nhớ - Hiểu)',
        'advanced': 'Nâng Cao (Vận Dụng - Phân Tích)',
        'medium': 'Thông Hiểu',
        'hard': 'Vận Dụng Cao'
    }

    @classmethod
    def analyze_bloom_mastery(cls, user) -> Dict[str, Any]:
        """
        Phân tích tỷ lệ làm đúng theo từng cấp độ Bloom's Taxonomy của học viên.
        Trả về:
        - bloom_stats: {level: {total, correct, accuracy_pct, label}}
        - strongest_level: Cấp độ mạnh nhất
        - weakest_level: Cấp độ yếu nhất cần cải thiện
        """
        attempts = UserQuizAttempt.objects.filter(user=user).select_related('quiz')
        
        bloom_stats = defaultdict(lambda: {'total': 0, 'correct': 0, 'accuracy_pct': 0.0})

        for attempt in attempts:
            diff = (attempt.quiz.difficulty if attempt.quiz else 'remember') or 'remember'
            diff_clean = diff.lower()
            
            # Đếm số câu
            total_q = attempt.total_questions or 0
            correct_q = attempt.correct_answers or 0

            bloom_stats[diff_clean]['total'] += total_q
            bloom_stats[diff_clean]['correct'] += correct_q

        # Tính toán phần trăm
        result_breakdown = {}
        for level, data in bloom_stats.items():
            tot = data['total']
            corr = data['correct']
            pct = round((corr / tot * 100), 1) if tot > 0 else 0.0
            label = cls.BLOOM_LABELS.get(level, level.capitalize())
            result_breakdown[level] = {
                'label': label,
                'total': tot,
                'correct': corr,
                'accuracy_pct': pct
            }

        # Tìm điểm mạnh và điểm yếu
        sorted_levels = sorted(
            [item for item in result_breakdown.items() if item[1]['total'] >= 5],
            key=lambda x: x[1]['accuracy_pct'],
            reverse=True
        )

        strongest = sorted_levels[0][1]['label'] if sorted_levels else "Đang tích lũy dữ liệu"
        weakest = sorted_levels[-1][1]['label'] if sorted_levels and len(sorted_levels) > 1 else "Đang tích lũy dữ liệu"

        return {
            'breakdown': result_breakdown,
            'strongest': strongest,
            'weakest': weakest,
            'has_data': len(result_breakdown) > 0
        }

    @classmethod
    def detect_knowledge_gaps(cls, user, limit: int = 5) -> List[Dict[str, Any]]:
        """
        Thuật toán phát hiện lỗ hổng kiến thức (Knowledge Gap Detector):
        Quét qua các câu hỏi làm sai trong các lần thi gần nhất,
        trích xuất các chủ đề/câu hỏi có tỷ lệ sai cao để đề xuất lộ trình ôn tập bổ sung.
        """
        attempts = UserQuizAttempt.objects.filter(user=user).order_by('-completed_at')[:10]
        
        wrong_questions_counter = defaultdict(lambda: {'count': 0, 'question_obj': None})

        # Tập hợp các ID câu hỏi làm sai
        wrong_ids = []
        for attempt in attempts:
            details = attempt.details or []
            for item in details:
                if not item.get('is_correct', False) and item.get('question_id'):
                    qid = item['question_id']
                    wrong_ids.append(qid)
                    wrong_questions_counter[qid]['count'] += 1

        if not wrong_ids:
            return []

        # Truy vấn thông tin các câu hỏi bị sai nhiều
        questions = Question.objects.filter(id__in=wrong_questions_counter.keys()).select_related('quiz')
        for q in questions:
            wrong_questions_counter[q.id]['question_obj'] = q

        # Sắp xếp các câu sai nhiều nhất
        sorted_gaps = sorted(
            [item for item in wrong_questions_counter.values() if item['question_obj']],
            key=lambda x: x['count'],
            reverse=True
        )

        gaps = []
        for item in sorted_gaps[:limit]:
            q = item['question_obj']
            gaps.append({
                'question_id': q.id,
                'question_text': q.question_text,
                'quiz_title': q.quiz.title if q.quiz else 'Đề tự do',
                'explanation': q.explanation,
                'fail_count': item['count'],
                'recommendation': f"Ôn tập lại khái niệm này trong tài liệu '{q.quiz.document.filename if q.quiz and q.quiz.document else 'gốc'}'"
            })

        return gaps
