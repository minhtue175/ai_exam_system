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


class TokenBucket:
    """
    Thuật toán Token Bucket Rate Limiter (Bình Chứa Token Ảo):
    - capacity: Dung lượng tối đa của bình (mặc định 5 tokens = 5 lượt tạo đề AI).
    - refill_time_seconds: Thời gian để tự động hồi phục 1 token (mặc định 600s = 10 phút/token).
    - Giúp bảo vệ quota API Gemini, chống spam và phân phối lượt dùng bền vững cho người học.
    """

    @classmethod
    def get_status(
        cls,
        key: str,
        capacity: float = 5.0,
        refill_time_seconds: float = 600.0
    ) -> tuple[int, int]:
        """
        Lấy trạng thái hiện tại của bình mà không tiêu thụ token.
        Trả về: (tokens_available, wait_seconds_for_next_refill)
        """
        try:
            cache_key = f"token_bucket:{key}"
            data = cache.get(cache_key)
            now = time.time()

            if data is None:
                return int(capacity), 0

            tokens = float(data.get('tokens', capacity))
            last_updated = float(data.get('last_updated', now))

            # Tính toán lượng token tự động hồi dựa trên thời gian trôi qua
            elapsed = max(0.0, now - last_updated)
            refill_rate = 1.0 / refill_time_seconds
            current_tokens = min(capacity, tokens + elapsed * refill_rate)

            if current_tokens < capacity:
                wait_seconds = int((1.0 - (current_tokens % 1.0)) * refill_time_seconds)
            else:
                wait_seconds = 0

            return int(current_tokens), wait_seconds
        except Exception as e:
            logger.warning(f"Cache error in TokenBucket.get_status: {e}")
            return int(capacity), 0

    @classmethod
    def consume(
        cls,
        key: str,
        cost: float = 1.0,
        capacity: float = 5.0,
        refill_time_seconds: float = 600.0
    ) -> tuple[bool, int, int]:
        """
        Tiêu thụ token từ bình:
        Trả về: (is_allowed, remaining_tokens, wait_seconds_until_refill)
        """
        try:
            cache_key = f"token_bucket:{key}"
            data = cache.get(cache_key)
            now = time.time()

            if data is None:
                current_tokens = capacity
                last_updated = now
            else:
                tokens = float(data.get('tokens', capacity))
                last_updated = float(data.get('last_updated', now))
                elapsed = max(0.0, now - last_updated)
                refill_rate = 1.0 / refill_time_seconds
                current_tokens = min(capacity, tokens + elapsed * refill_rate)

            if current_tokens >= cost:
                new_tokens = current_tokens - cost
                cache_ttl = int(capacity * refill_time_seconds * 2)
                cache.set(cache_key, {
                    'tokens': new_tokens,
                    'last_updated': now
                }, timeout=cache_ttl)

                wait_seconds = int(refill_time_seconds) if new_tokens < capacity else 0
                return True, int(new_tokens), wait_seconds
            else:
                missing = cost - current_tokens
                wait_seconds = max(1, int(missing * refill_time_seconds))
                return False, int(current_tokens), wait_seconds
        except Exception as e:
            logger.warning(f"Cache error in TokenBucket.consume: {e}")
            # Fail-open an toàn nếu cache lỗi
            return True, int(capacity - cost), 0

    @classmethod
    def reset(cls, key: str) -> None:
        """Khôi phục bình đầy token (dùng cho test hoặc nạp quota)"""
        try:
            cache.delete(f"token_bucket:{key}")
        except Exception as e:
            logger.warning(f"Cache error in TokenBucket.reset: {e}")
