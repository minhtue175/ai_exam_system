import os
from celery import Celery

# 1. Trỏ Celery vào file setting đang dùng (mặc định là development khi code local)
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.development')

# 2. Khởi tạo app Celery
app = Celery('fluesy_exam')

# 3. Yêu cầu Celery đọc cấu hình từ file settings.py (những biến bắt đầu bằng CELERY_)
app.config_from_object('django.conf:settings', namespace='CELERY')

# 4. Tự động tìm kiếm các "Task" trong tất cả các app (quizzes, exports...)
app.autodiscover_tasks()