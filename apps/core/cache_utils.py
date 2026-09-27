"""
Thuật toán Cache-Aside (Lazy Loading Cache):
Quản lý cache thông minh cho Dashboard và Profile,
tự động invalidate khi dữ liệu thay đổi.

Flow:
    [Request] → Check Cache (Redis)
        ├── Cache HIT  → Trả kết quả ngay (0ms SQL)
        └── Cache MISS → Query DB → Lưu Cache (TTL) → Trả kết quả
"""
from django.core.cache import cache
import logging

logger = logging.getLogger(__name__)

# TTL constants (seconds)
DASHBOARD_CACHE_TTL = 120   # 2 phút — Dashboard truy cập thường xuyên, cần fresh data
PROFILE_CACHE_TTL = 300     # 5 phút — Profile ít thay đổi, cache lâu hơn


class CacheManager:
    """
    Cache-Aside Pattern Manager:
    - Check cache → HIT: trả ngay | MISS: query DB → lưu cache → trả kết quả
    - Invalidation tự động khi có write operation liên quan (upload, delete, nộp bài...)
    """

    # ========== KEY GENERATORS ==========
    @staticmethod
    def _dashboard_key(user_id: int) -> str:
        return f"dashboard:{user_id}"

    @staticmethod
    def _profile_key(user_id: int) -> str:
        return f"profile:{user_id}"

    # ========== DASHBOARD CACHE ==========
    @classmethod
    def get_dashboard_stats(cls, user_id: int) -> dict | None:
        """Lấy thống kê Dashboard từ cache (None = cache miss)"""
        try:
            return cache.get(cls._dashboard_key(user_id))
        except Exception as e:
            logger.warning(f"Cache read error (dashboard): {e}")
            return None

    @classmethod
    def set_dashboard_stats(cls, user_id: int, stats: dict) -> None:
        """Lưu thống kê Dashboard vào cache với TTL 2 phút"""
        try:
            cache.set(cls._dashboard_key(user_id), stats, timeout=DASHBOARD_CACHE_TTL)
        except Exception as e:
            logger.warning(f"Cache write error (dashboard): {e}")

    # ========== PROFILE CACHE ==========
    @classmethod
    def get_profile_stats(cls, user_id: int) -> dict | None:
        """Lấy thống kê Profile từ cache (None = cache miss)"""
        try:
            return cache.get(cls._profile_key(user_id))
        except Exception as e:
            logger.warning(f"Cache read error (profile): {e}")
            return None

    @classmethod
    def set_profile_stats(cls, user_id: int, stats: dict) -> None:
        """Lưu thống kê Profile vào cache với TTL 5 phút"""
        try:
            cache.set(cls._profile_key(user_id), stats, timeout=PROFILE_CACHE_TTL)
        except Exception as e:
            logger.warning(f"Cache write error (profile): {e}")

    # ========== INVALIDATION ==========
    @classmethod
    def invalidate_user_cache(cls, user_id: int) -> None:
        """
        Xóa toàn bộ cache liên quan đến user khi có thay đổi dữ liệu.
        Gọi khi: Upload/xóa document, nộp bài thi, xóa quiz...
        """
        try:
            cache.delete(cls._dashboard_key(user_id))
            cache.delete(cls._profile_key(user_id))
            logger.debug(f"Cache invalidated for user {user_id}")
        except Exception as e:
            logger.warning(f"Cache invalidation error: {e}")
