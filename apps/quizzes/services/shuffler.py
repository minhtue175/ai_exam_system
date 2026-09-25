"""
Thuật toán Trộn Đề Có Ràng Buộc (Constrained Shuffling Algorithm)
Bảo đảm:
1. Tính tất định (Deterministic) theo Seed, cô lập luồng an toàn (Thread-safe).
2. Phân bố đều vị trí đáp án đúng (Uniform Distribution Constraint) ~ 25% cho mỗi đáp án A, B, C, D.
3. Chống dồn chuỗi đáp án (Anti-Streak Constraint): Không xuất hiện quá 2 câu liên tiếp cùng 1 đáp án.
"""
import random
from typing import List, Dict, Optional


class QuestionShuffler:
    """
    Trộn thứ tự câu hỏi và đáp án có ràng buộc sư phạm chuẩn hóa:
    - Loại bỏ hiện tượng đáp án đúng bị lệch về 1 chữ cái.
    - Triệt tiêu hiện tượng dồn 3-4 câu liên tục cùng đáp án.
    """

    @staticmethod
    def _create_rng(seed: Optional[int] = None) -> random.Random:
        """Tạo đối tượng sinh số ngẫu nhiên cô lập, tránh race-condition giữa các request"""
        return random.Random(seed)

    @classmethod
    def generate_balanced_answer_sequence(
        cls,
        total_questions: int,
        num_options: int = 4,
        rng: Optional[random.Random] = None
    ) -> List[int]:
        """
        Sinh chuỗi vị trí đáp án đúng cân bằng và chống dồn chuỗi:
        - Mỗi đáp án (0, 1, 2, 3) xuất hiện xấp xỉ N/4 lần (sai số tối đa 1 câu).
        - Không có bất kỳ chuỗi 3 câu liên tiếp nào có cùng vị trí đáp án.
        """
        if rng is None:
            rng = random.Random()

        if total_questions <= 0:
            return []

        # 1. Tạo tập hợp cơ sở phân bố đều
        base_count = total_questions // num_options
        remainder = total_questions % num_options

        pool: List[int] = []
        for opt in range(num_options):
            pool.extend([opt] * base_count)

        # Phân phối phần dư ngẫu nhiên cho các đáp án khác nhau
        if remainder > 0:
            extra_options = rng.sample(range(num_options), remainder)
            pool.extend(extra_options)

        # 2. Xáo trộn có ràng buộc Anti-Streak (Streak tối đa cho phép = 2)
        max_attempts = 100
        for _ in range(max_attempts):
            rng.shuffle(pool)
            valid = True
            streak = 1
            for i in range(1, len(pool)):
                if pool[i] == pool[i - 1]:
                    streak += 1
                    if streak > 2:
                        valid = False
                        break
                else:
                    streak = 1
            if valid:
                return pool

        # 3. Thuật toán cứu cánh (Heuristic swap) nếu sau 100 lần vẫn còn streak > 2
        for i in range(2, len(pool)):
            if pool[i] == pool[i - 1] == pool[i - 2]:
                for j in range(len(pool)):
                    if pool[j] != pool[i]:
                        # Kiểm tra xem đổi chỗ sang j có tạo streak mới không
                        left_ok = (j == 0 or pool[j - 1] != pool[i])
                        right_ok = (j == len(pool) - 1 or pool[j + 1] != pool[i])
                        if left_ok and right_ok:
                            pool[i], pool[j] = pool[j], pool[i]
                            break

        return pool

    @classmethod
    def shuffle_questions(cls, questions: List, seed: Optional[int] = None) -> List:
        """Xáo trộn thứ tự các câu hỏi trong đề thi"""
        rng = cls._create_rng(seed)
        shuffled = list(questions)
        rng.shuffle(shuffled)
        return shuffled

    @classmethod
    def shuffle_options(cls, question_dict: Dict, target_correct_idx: Optional[int] = None, rng: Optional[random.Random] = None) -> Dict:
        """
        Xáo trộn các phương án lựa chọn:
        - Nếu target_correct_idx được chỉ định: Ép đáp án đúng rơi vào vị trí này.
        - Các phương án nhiễu còn lại được trộn đều vào các vị trí trống.
        """
        if rng is None:
            rng = random.Random()

        options = list(question_dict.get('options', []))
        orig_correct_idx = question_dict.get('correct_answer', 0)
        
        # Phòng vệ nếu index đáp án gốc không hợp lệ
        if orig_correct_idx < 0 or orig_correct_idx >= len(options):
            orig_correct_idx = 0

        correct_option_text = options[orig_correct_idx]
        distractors = [opt for k, opt in enumerate(options) if k != orig_correct_idx]
        rng.shuffle(distractors)

        num_opts = len(options)
        if target_correct_idx is not None and 0 <= target_correct_idx < num_opts:
            final_correct_idx = target_correct_idx
        else:
            final_correct_idx = rng.randint(0, num_opts - 1) if num_opts > 0 else 0

        # Dựng lại mảng options mới
        new_options = [None] * num_opts
        new_options[final_correct_idx] = correct_option_text

        d_idx = 0
        for slot in range(num_opts):
            if new_options[slot] is None:
                new_options[slot] = distractors[d_idx]
                d_idx += 1

        result = dict(question_dict)
        result['options'] = new_options
        result['correct_answer'] = final_correct_idx
        return result

    @classmethod
    def shuffle_quiz(cls, questions: List[Dict], seed: Optional[int] = None) -> List[Dict]:
        """
        Thuật toán xáo trộn toàn diện đề thi (Constrained Shuffling):
        1. Xáo thứ tự câu hỏi độc lập.
        2. Sinh chuỗi phân bổ đáp án đúng cân bằng A, B, C, D và chống dồn 3 câu liền kề.
        3. Áp dụng chuỗi mục tiêu lên từng câu hỏi.
        4. Bảo đảm 100% tái tạo chính xác khi chạy lại với cùng một seed (phục vụ chấm điểm).
        """
        rng = cls._create_rng(seed)

        # 1. Trộn thứ tự câu hỏi
        shuffled_questions = list(questions)
        rng.shuffle(shuffled_questions)

        total = len(shuffled_questions)
        if total == 0:
            return []

        # 2. Sinh chuỗi đáp án đúng cân bằng và chống streak
        target_indices = cls.generate_balanced_answer_sequence(total_questions=total, num_options=4, rng=rng)

        # 3. Trộn đáp án từng câu theo chuỗi đã định hình
        result = []
        for idx, q in enumerate(shuffled_questions):
            target_idx = target_indices[idx] if idx < len(target_indices) else None
            shuffled_q = cls.shuffle_options(q, target_correct_idx=target_idx, rng=rng)
            result.append(shuffled_q)

        return result