from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
# THÊM DÒNG NÀY:
from django.contrib.auth import views as auth_views 

urlpatterns = [
    path('admin/', admin.site.urls),
    
    path('', include('apps.core.urls')),
    
    path('users/', include('apps.users.urls')),
    
    path('documents/', include('apps.documents.urls')),
    
    path('quizzes/', include('apps.quizzes.urls')),
    
    path('exports/', include('apps.exports.urls')),

    path('logout/', auth_views.LogoutView.as_view(), name='logout'),

    # Password Reset Flow
    path('password-reset/', auth_views.PasswordResetView.as_view(
        template_name='users/password_reset.html',
        email_template_name='users/password_reset_email.html',
        subject_template_name='users/password_reset_subject.txt',
        success_url='/password-reset/done/',
    ), name='password_reset'),
    path('password-reset/done/', auth_views.PasswordResetDoneView.as_view(
        template_name='users/password_reset_done.html',
    ), name='password_reset_done'),
    path('password-reset-confirm/<uidb64>/<token>/', auth_views.PasswordResetConfirmView.as_view(
        template_name='users/password_reset_confirm.html',
        success_url='/password-reset-complete/',
    ), name='password_reset_confirm'),
    path('password-reset-complete/', auth_views.PasswordResetCompleteView.as_view(
        template_name='users/password_reset_complete.html',
    ), name='password_reset_complete'),
]



if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)