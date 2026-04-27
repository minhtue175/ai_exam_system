from pathlib import Path
import os
from dotenv import load_dotenv 






load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent.parent




SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-key-change-in-production")

DEBUG = True

ALLOWED_HOSTS = ['*']




DJANGO_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
]

LOCAL_APPS = [
    'apps.core',
    'apps.users',
    'apps.documents',
    'apps.quizzes',
    'apps.exports',
]

THIRD_PARTY_APPS = [
    
]

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS




MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]




ROOT_URLCONF = 'config.urls'
WSGI_APPLICATION = 'config.wsgi.application'




TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]




AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]




LANGUAGE_CODE = 'vi'

TIME_ZONE = 'Asia/Ho_Chi_Minh'

USE_I18N = True
USE_TZ = True




STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_DIRS = [BASE_DIR / 'static']




MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'




AUTH_USER_MODEL = 'users.User'




LOGIN_URL = 'users:login'
LOGIN_REDIRECT_URL = 'core:dashboard'
LOGOUT_REDIRECT_URL = 'users:login'




DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY', '')

if not GEMINI_API_KEY and DEBUG:
    import warnings
    warnings.warn("GEMINI_API_KEY chưa được cấu hình trong file .env!")

# Cho phép upload tối đa 20MB 
DATA_UPLOAD_MAX_MEMORY_SIZE = 20971520
FILE_UPLOAD_MAX_MEMORY_SIZE = 20971520


DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'fluesy_db',         # Tên Database bạn đã tạo trong pgAdmin 4
        'USER': 'postgres',          # Tên tài khoản PostgreSQL (mặc định là postgres)
        'PASSWORD': 'moimoi011235813', # Mật khẩu lúc bạn cài PostgreSQL
        'HOST': 'localhost',
        'PORT': '5432',
    }
}

CELERY_BROKER_URL = 'redis://127.0.0.1:6379/0'
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'