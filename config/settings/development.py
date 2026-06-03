from .base import *



DEBUG = True

ALLOWED_HOSTS = ['127.0.0.1', 'localhost', '26.200.22.37','*']








# Enable detailed error pages
INTERNAL_IPS = ['127.0.0.1']

# Email backend (console for development)
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'