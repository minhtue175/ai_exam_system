from django.urls import path
from . import views

app_name = 'documents'

urlpatterns = [
    path('upload/', views.upload_view, name='upload'),
    path('list/', views.document_list_view, name='list'),
    path('<int:pk>/', views.document_detail_view, name='detail'),
    path('<int:pk>/download/', views.document_download_view, name='download'),
    path('<int:pk>/delete/', views.document_delete_view, name='delete'),
    path('<int:pk>/extract/', views.extract_text_view, name='extract'),
]