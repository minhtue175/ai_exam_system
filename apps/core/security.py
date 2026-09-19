"""
Tiện ích bảo mật và Rate Limiter chống Brute-force / Spam requests
"""
import time
from django.core.cache import cache
import logging

logger = logging.getLogger(__name__)


def get_client_ip(request) -> str:
    """Lấy địa chỉ IP thật của client qua header Proxy hoặc REMOTE_ADDR"""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0].strip()
    else:
        ip = request.META.get('REMOTE_ADDR', '127.0.0.1')
    return ip


class RateLimiter:
    """
    Rate Limiter dựa trên Django Cache (tương thích Redis / InMemory cache).
    Hỗ trợ đếm số lần thất bại, khóa tạm thời khi vượt ngưỡng.
    """

    @staticmethod
    def is_rate_limited(key: str, max_attempts: int = 5, lock_seconds: int = 300) -> tuple[bool, int]:
        """
        Kiểm tra xem key (IP hoặc username) có đang bị khóa hay không.
        Trả về: (is_limited, seconds_remaining)
        """
        try:
            lock_key = f"lock:{key}"
            locked_until = cache.get(lock_key)
            if locked_until:
                now = time.time()
                if locked_until > now:
                    return True, int(locked_until - now)
                else:
                    cache.delete(lock_key)
            return False, 0
        except Exception as e:
            logger.warning(f"Cache error in is_rate_limited: {e}")
            return False, 0

    @staticmethod
    def record_failure(key: str, max_attempts: int = 5, lock_seconds: int = 300) -> int:
        """
        Ghi nhận một lần thử thất bại. Nếu số lần vượt quá max_attempts, khóa tạm thời.
        Trả về: số lần đã thử sai.
        """
        try:
            attempt_key = f"attempts:{key}"
            attempts = cache.get(attempt_key, 0) + 1
            cache.set(attempt_key, attempts, timeout=lock_seconds)

            if attempts >= max_attempts:
                lock_key = f"lock:{key}"
                cache.set(lock_key, time.time() + lock_seconds, timeout=lock_seconds)
                logger.warning(f"Security: Key {key} has been temporarily locked for {lock_seconds}s after {attempts} failed attempts.")

            return attempts
        except Exception as e:
            logger.warning(f"Cache error in record_failure: {e}")
            return 1

    @staticmethod
    def reset(key: str) -> None:
        """Xóa số lần thử sai khi hành động thành công"""
        try:
            cache.delete(f"attempts:{key}")
            cache.delete(f"lock:{key}")
        except Exception as e:
            logger.warning(f"Cache error in reset: {e}")
