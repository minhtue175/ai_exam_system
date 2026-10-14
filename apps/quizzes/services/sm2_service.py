"""
Thuật Toán Giãn Cách Thời Gian Chuẩn Quốc Tế SuperMemo SM-2 & Đường Cong Quên Lãng Ebbinghaus:
1. SuperMemo SM-2: Tính toán chu kỳ ôn tập tối ưu (Optimal Interval) dựa trên Ease Factor.
2. Ebbinghaus Forgetting Curve: Dự báo tỷ lệ duy trì trí nhớ R = e^(-t/S).
"""
import math
from typing import Dict, List, Tuple
from django.utils import timezone
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)


class SuperMemo2Service:
    """Service triển khai thuật toán SuperMemo SM-2 và mô hình hóa đường cong trí nhớ"""

    DEFAULT_EASE_FACTOR = 2.5
    MIN_EASE_FACTOR = 1.3

    @classmethod
    def calculate_sm2(
        cls,
        quality: int,
        repetitions: int,
        ease_factor: float,
        interval_days: int
    ) -> Tuple[int, float, int]:
        """
        Tính toán chu kỳ ôn tập tiếp theo theo thuật toán SuperMemo SM-2:
        Args:
            quality: Đánh giá chất lượng nhớ (0-5)
                     5: Hoàn hảo, phản xạ tức thì
                     4: Nhớ đúng sau một chút do dự
                     3: Nhớ đúng nhưng gặp khó khăn
                     2: Trả lời sai nhưng nhìn đáp án thì nhớ ra
                     1: Trả lời sai hoàn toàn
                     0: Mất trí nhớ hoàn toàn về câu hỏi
            repetitions: Số lần ôn tập thành công liên tiếp
            ease_factor: Hệ số độ dễ (mặc định 2.5)
            interval_days: Khoảng cách ngày của lần ôn trước
            
        Returns:
            (new_repetitions, new_ease_factor, next_interval_days)
        """
        # Giới hạn quality từ 0 đến 5
        q = max(0, min(5, quality))

        # 1. Tính toán Ease Factor mới
        # Công thức: EF' = EF + (0.1 - (5 - q) * (0.08 + (5 - q) * 0.02))
        new_ef = ease_factor + (0.1 - (5 - q) * (0.08 + (5 - q) * 0.02))
        if new_ef < cls.MIN_EASE_FACTOR:
            new_ef = cls.MIN_EASE_FACTOR

        # 2. Tính toán Repetitions và Interval
        if q < 3:
            # Trả lời sai: reset số lần nhớ thành công và ôn lại ngay vào ngày mai
            new_repetitions = 0
            next_interval = 1
        else:
            # Trả lời đúng: tăng bước tiến
            new_repetitions = repetitions + 1
            if new_repetitions == 1:
                next_interval = 1
            elif new_repetitions == 2:
                next_interval = 6
            else:
                next_interval = math.ceil(interval_days * new_ef)

        return new_repetitions, round(new_ef, 2), next_interval

    @classmethod
    def calculate_ebbinghaus_retention_curve(cls, stability_days: float = 7.0, days_range: int = 30) -> List[Dict]:
        """
        Mô hình hóa đường cong quên lãng Ebbinghaus theo công thức:
        R(t) = e^(-t / S) * 100%
        Trong đó:
            t: số ngày đã trôi qua kể từ lần ôn tập cuối
            S: Độ bền trí nhớ (Memory Stability - tính bằng ngày)
            R: Tỷ lệ kiến thức còn lưu giữ trong não bộ (%)
        """
        curve_data = []
        for day in range(0, days_range + 1):
            retention = math.exp(-day / max(1.0, stability_days)) * 100.0
            curve_data.append({
                'day': day,
                'retention_pct': round(retention, 1),
                'status': 'Tốt' if retention >= 70 else ('Cần ôn lại' if retention >= 40 else 'Nguy cơ quên cao')
            })
        return curve_data
