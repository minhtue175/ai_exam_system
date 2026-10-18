"""
Audit & Security Middleware:
1. Ghi nhận thời gian xử lý (Request Latency Tracking) và gắn header X-Response-Time.
2. Phát hiện các yêu cầu đáng ngờ (Path Traversal, SQL Injection, Malicious Script Injection).
3. Ghi log truy vết phục vụ giám sát vận hành và an ninh hệ thống.
"""
import time
import logging
import re
from django.utils.deprecation import MiddlewareMixin
from apps.core.security import get_client_ip

logger = logging.getLogger("security.audit")


class AuditLogMiddleware(MiddlewareMixin):
    """Middleware ghi nhật ký kiểm toán và bảo vệ an ninh HTTP Request"""

    # Danh sách các mẫu regex nhận diện tấn công phổ biến
    SUSPICIOUS_PATTERNS = [
        r'(\.\./|\.\.\\)',                          # Path traversal
        r'(union\s+select|select\s+.*\s+from)',    # SQLi pattern
        r'(<script|javascript:|onload=|onerror=)',  # XSS pattern
        r'(;\s*drop\s+table|;\s*truncate)',        # Destructive SQL
        r'(\${jndi:|\/etc\/passwd|\/windows\/win.ini)', # RCE & LFI
    ]
    COMPILED_PATTERNS = [re.compile(p, re.IGNORECASE) for p in SUSPICIOUS_PATTERNS]

    def process_request(self, request):
        request._start_time = time.time()
        
        # Kiểm tra nội dung URL và Query string
        raw_uri = request.get_full_path()
        for pattern in self.COMPILED_PATTERNS:
            if pattern.search(raw_uri):
                ip = get_client_ip(request)
                user_str = request.user.username if request.user.is_authenticated else 'Anonymous'
                logger.warning(
                    f"🚨 [CẢNH BÁO BẢO MẬT] Phát hiện request đáng ngờ từ IP {ip} (User: {user_str}) - URI: {raw_uri}"
                )
                break

    def process_response(self, request, response):
        start_time = getattr(request, '_start_time', None)
        if start_time:
            latency_ms = round((time.time() - start_time) * 1000, 2)
            response['X-Response-Time'] = f"{latency_ms}ms"

            # Cảnh báo nếu endpoint phản hồi quá chậm (> 1.5 giây)
            if latency_ms > 1500 and not request.path.startswith('/static/'):
                ip = get_client_ip(request)
                logger.info(f"⏱️ [SLO Warning] Request chậm ({latency_ms}ms) tới {request.method} {request.path} (IP: {ip})")

        return response
