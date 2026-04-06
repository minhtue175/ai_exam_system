from .base import *

# ===============================
# DEVELOPMENT SETTINGS
# ===============================

DEBUG = True

ALLOWED_HOSTS = ['127.0.0.1', 'localhost', '*']


# ===============================
# DATABASE FOR DEVELOPMENT
# ===============================

# DATABASES = {
#     'default': {
#         'ENGINE': 'django.db.backends.sqlite3',
#         'NAME': BASE_DIR / 'db.sqlite3',
#     }
# }


# ===============================
# DEVELOPMENT-SPECIFIC SETTINGS
# ===============================

# Enable detailed error pages
INTERNAL_IPS = ['127.0.0.1']

# Email backend (console for development)
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'