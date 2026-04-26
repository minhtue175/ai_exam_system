from django import template
import re

register = template.Library()

@register.filter
def clean_prefix(value):
    """Cạo sạch các tiền tố rác A. B. C. D. hoặc 1. 2. 3. 4. bị AI sinh dính vào text"""
    # Xóa các kiểu như "A. ", "B) ", "1- ", "C: " ở ngay đầu chuỗi
    cleaned = re.sub(r'^([A-D]|[1-4])[\.\)\-\:]\s+', '', str(value).strip(), flags=re.IGNORECASE)
    return cleaned

@register.filter
def to_char(value):
    """Biến đổi vòng lặp 0, 1, 2, 3 thành chữ cái A, B, C, D siêu mượt"""
    try:
        return chr(65 + int(value))
    except (ValueError, TypeError):
        return value