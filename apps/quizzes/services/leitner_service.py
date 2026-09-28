"""
Thuật toán Spaced Repetition (Hệ thống hộp Leitner Đa Chế Độ):
1. Chế độ Ngắn Hạn (Cấp tốc ôn thi < 1 tuần, tính bằng giờ):
   - Ngăn 1: 1 giờ (hoặc 2h, 4h, 6h, 12h tùy chọn)
   - Ngăn 2: 6 giờ
   - Ngăn 3: 24 giờ (1 ngày)
   - Ngăn 4: 72 giờ (3 ngày)
   - Ngăn 5: 144 giờ (6 ngày) -> Thành thạo ✅
2. Chế độ Dài Hạn (Chu kỳ chuẩn > 1 tuần đến 1 tháng, ngoại ngữ/chứng chỉ):
   - Ngăn 1: 1 ngày (24h)
   - Ngăn 2: 3 ngày (72h)
   - Ngăn 3: 7 ngày (1 tuần)
   - Ngăn 4: 14 ngày (2 tuần)
   - Ngăn 5: 30 ngày (1 tháng) -> Thành thạo ✅
"""
from typing import Dict, List, Optional
from datetime import timedelta
from django.utils import timezone
from django.db.models import Count, Q
from ..models import ReviewCard, Question
import logging

logger = logging.getLogger(__name__)


class LeitnerService:
    """Service điều phối thuật toán Spaced Repetition Leitner Đa Chế Độ"""

    BOX_DESCRIPTIONS = {
        'short_term': {
            1: "Sau {first_h} giờ (Ôn lại cấp tốc trong ngày)",
            2: "Sau 6 giờ (Củng cố giữa ngày)",
            3: "Sau 1 ngày / 24h (Kiểm tra lại hôm sau)",
            4: "Sau 3 ngày (Ghi nhớ ổn định trước thi)",
            5: "Sau 6 ngày (Hoàn toàn thành thạo ✅)",
        },
        'long_term': {
            1: "Sau 1 ngày (Ghi nhớ sơ bộ ban đầu)",
            2: "Sau 3 ngày (Bắt đầu chuyển vào trí nhớ dài hạn)",
            3: "Sau 7 ngày / 1 tuần (Củng cố chu kỳ tuần)",
            4: "Sau 14 ngày / 2 tuần (Trí nhớ dài hạn vững)",
            5: "Sau 30 ngày / 1 tháng (Hoàn toàn thành thạo ✅)",
        }
    }

    @classmethod
    def update_cards_from_attempt(
        cls,
        user,
        results: List[Dict],
        mode: str = 'short_term',
        custom_first_hours: int = 1
    ) -> None:
        """
        Tự động nạp hoặc cập nhật các câu hỏi sau khi user nộp bài thi
        """
        now = timezone.now()
        for res in results:
            question_id = res.get('question_id')
            is_correct = res.get('is_correct', False)

            if not question_id:
                continue

            try:
                card, created = ReviewCard.objects.get_or_create(
                    user=user,
                    question_id=question_id,
                    defaults={
                        'review_mode': mode,
                        'custom_first_interval_hours': custom_first_hours,
                        'box_level': 1,
                        'next_review_at': now + timedelta(hours=custom_first_hours if mode == 'short_term' else 24),
                        'last_reviewed_at': now,
                        'review_count': 1,
                        'is_mastered': False,
                    }
                )

                if not created:
                    card.review_mode = mode
                    card.custom_first_interval_hours = custom_first_hours
                    card.process_review(is_correct=is_correct)
                else:
                    if is_correct:
                        # Đúng ngay lần đầu: thăng cấp lên ngăn 2
                        card.box_level = 2
                        h = card.get_interval_hours()
                        card.next_review_at = now + timedelta(hours=h)
                        card.save()

            except Exception as e:
                logger.warning(f"Lỗi cập nhật ReviewCard cho user {user.id}, question {question_id}: {e}")

    @classmethod
    def get_dashboard_stats(cls, user, mode: str = 'short_term') -> Dict:
        """
        Thống kê phân bổ các câu hỏi trong 5 ngăn Leitner của user theo chế độ đã chọn
        """
        now = timezone.now()
        cards = ReviewCard.objects.filter(user=user)

        # Lấy chế độ active thực tế từ thẻ gần nhất nếu chưa chỉ định rõ
        if not mode and cards.exists():
            mode = cards.first().review_mode or 'short_term'
        elif not mode:
            mode = 'short_term'

        # Đếm số lượng trong từng ngăn (tính cho chế độ hiện tại)
        mode_cards = cards.filter(review_mode=mode)
        box_counts = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
        counts_query = mode_cards.values('box_level').annotate(total=Count('id'))
        for item in counts_query:
            lvl = item['box_level']
            if lvl in box_counts:
                box_counts[lvl] = item['total']

        total_cards = sum(box_counts.values())
        due_cards_count = mode_cards.filter(next_review_at__lte=now).count()
        mastered_count = box_counts[5]

        mastery_rate = round((mastered_count / total_cards * 100), 1) if total_cards > 0 else 0

        # Lấy giờ custom ngăn 1
        first_card = mode_cards.first()
        custom_h = first_card.custom_first_interval_hours if first_card else 1

        # Mô tả chu kỳ 5 ngăn
        desc_template = cls.BOX_DESCRIPTIONS.get(mode, cls.BOX_DESCRIPTIONS['short_term'])
        box_descriptions = {
            1: desc_template[1].format(first_h=custom_h),
            2: desc_template[2],
            3: desc_template[3],
            4: desc_template[4],
            5: desc_template[5],
        }

        # Khoảng cách giờ/ngày hiển thị trên badge ngăn
        if mode == 'short_term':
            box_intervals = {
                1: f"{custom_h} giờ",
                2: "6 giờ",
                3: "1 ngày",
                4: "3 ngày",
                5: "6 ngày",
            }
        else:
            box_intervals = {
                1: "1 ngày",
                2: "3 ngày",
                3: "7 ngày (1 tuần)",
                4: "14 ngày (2 tuần)",
                5: "30 ngày (1 tháng)",
            }

        return {
            'mode': mode,
            'custom_first_hours': custom_h,
            'total_cards': total_cards,
            'box_counts': box_counts,
            'box_intervals': box_intervals,
            'box_descriptions': box_descriptions,
            'due_cards_count': due_cards_count,
            'mastered_count': mastered_count,
            'mastery_rate': mastery_rate,
        }

    @classmethod
    def get_due_cards(cls, user, mode: str = 'short_term', limit: int = 20) -> List[ReviewCard]:
        """
        Lấy danh sách các thẻ câu hỏi đã đến hạn ôn tập
        """
        now = timezone.now()
        qs = ReviewCard.objects.filter(
            user=user,
            next_review_at__lte=now
        )
        if mode:
            qs = qs.filter(review_mode=mode)

        return list(
            qs.select_related('question', 'question__quiz')
            .order_by('box_level', 'next_review_at')[:limit]
        )

    @classmethod
    def switch_user_mode(
        cls,
        user,
        new_mode: str,
        custom_first_hours: int = 1
    ) -> int:
        """
        Chuyển đổi chế độ ôn tập cho toàn bộ thẻ của user và tính toán lại lịch ôn tập
        """
        now = timezone.now()
        cards = ReviewCard.objects.filter(user=user)
        updated_count = 0

        for card in cards:
            card.review_mode = new_mode
            if new_mode == 'short_term':
                card.custom_first_interval_hours = custom_first_hours
            
            hours = card.get_interval_hours()
            card.next_review_at = now + timedelta(hours=hours)
            card.save()
            updated_count += 1

        return updated_count

    @classmethod
    def answer_card(cls, user, card_id: int, selected_index: int) -> Dict:
        """
        Xử lý khi người dùng trả lời 1 thẻ ôn tập:
        - So sánh với correct_answer
        - Kích hoạt quy tắc Leitner theo chế độ tương ứng
        - Trả về kết quả chi tiết
        """
        card = ReviewCard.objects.select_related('question').get(id=card_id, user=user)
        question = card.question
        
        is_correct = (selected_index == question.correct_answer)
        old_box = card.box_level
        
        card.process_review(is_correct=is_correct)

        return {
            'is_correct': is_correct,
            'old_box': old_box,
            'new_box': card.box_level,
            'interval_display': card.get_interval_display(),
            'review_mode': card.review_mode,
            'is_mastered': card.is_mastered,
            'next_review_at': card.next_review_at,
            'correct_answer_index': question.correct_answer,
            'correct_answer_text': question.get_correct_answer_text(),
            'explanation': question.explanation or 'Chính xác theo tài liệu tham khảo.',
        }
