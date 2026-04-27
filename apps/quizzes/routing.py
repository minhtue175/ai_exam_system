from django.urls import path
from . import consumers

websocket_urlpatterns = [
    # Đường ống websocket sẽ chạy ở địa chỉ này
    path('ws/notifications/', consumers.NotificationConsumer.as_asgi()), 
]