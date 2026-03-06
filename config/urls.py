from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static


urlpatterns = [
    path('admin/', admin.site.urls),
    
    path('', include('apps.core.urls')),
    
    path('users/', include('apps.users.urls')),
    
    path('documents/', include('apps.documents.urls')),
    
    path('quizzes/', include('apps.quizzes.urls')),
    
    path('exports/', include('apps.exports.urls')),
]


# Serve media files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)