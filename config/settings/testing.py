from .base import *

# Dùng InMemory Cache cho test runner để độc lập hoàn toàn với Redis server
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'test-cache',
    }
}
