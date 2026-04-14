from .base import *

# ===============================
# DEVELOPMENT SETTINGS
# ===============================

DEBUG = True

ALLOWED_HOSTS = ['127.0.0.1', 'localhost', '*']







# Enable detailed error pages
INTERNAL_IPS = ['127.0.0.1']

# Email backend (console for development)
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'