"""
Prompt Injection Defense & Sanitizer (Bảo vệ Mô hình AI):
Phát hiện và khử độc các câu lệnh độc hại nhằm đánh lừa hoặc can thiệp vào chỉ thị hệ thống của LLM (Gemini).
"""
import re
import logging
from typing import Tuple

logger = logging.getLogger("security.prompt_guard")


class PromptGuard:
    """Bộ lọc bảo vệ chống Prompt Injection và Jailbreak trong tài liệu học tập"""

    # Danh sách các mẫu lệnh injection tiếng Anh và tiếng Việt nguy hiểm
    INJECTION_PATTERNS = [
        r'(?i)ignore\s+(all\s+)?(previous|above|prior)\s+(instructions|prompts|rules)',
        r'(?i)disregard\s+(all\s+)?(previous|above|prior)\s+(instructions|prompts)',
        r'(?i)you\s+are\s+now\s+(in\s+developer\s+mode|dan|an\s+unrestricted\s+ai)',
        r'(?i)system\s+prompt\s*:\s*(reveal|override|bypass)',
        r'(?i)print\s+(the\s+)?(system\s+prompt|internal\s+instructions)',
        r'(?i)bỏ\s+qua\s+(toàn\s+bộ\s+)?(các\s+)?(hướng\s+dẫn|chỉ\s+thị|quy\s+tắc)\s+(trước|trên)',
        r'(?i)hãy\s+quên\s+(tất\s+cả\s+)?(chỉ\s+thị|vai\s+trò)\s+cũ',
        r'(?i)bây\s+giờ\s+bạn\s+là\s+(hacker|dan|chế\s+độ\s+nhà\s+phát\s+triển)',
    ]

    COMPILED_PATTERNS = [re.compile(p) for p in INJECTION_PATTERNS]

    @classmethod
    def sanitize(cls, text: str) -> Tuple[str, bool]:
        """
        Khử độc văn bản đầu vào:
        - Quét và thay thế các câu lệnh injection bằng nhãn an toàn.
        - Trả về: (sanitized_text, has_injection_detected)
        """
        if not text:
            return text, False

        sanitized_text = text
        detected = False

        for pattern in cls.COMPILED_PATTERNS:
            matches = pattern.findall(sanitized_text)
            if matches:
                detected = True
                logger.warning(f"🛡️ [PromptGuard] Đã phát hiện và vô hiệu hóa Prompt Injection: '{pattern.pattern}'")
                # Thay thế chuỗi độc hại bằng văn bản cảnh báo vô hại
                sanitized_text = pattern.sub('[Nội dung bị chặn bởi PromptGuard]', sanitized_text)

        return sanitized_text, detected
