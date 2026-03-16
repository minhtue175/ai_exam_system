from django.urls import path
from . import views

app_name = 'quizzes'

urlpatterns = [
    path('', views.quiz_list_view, name='list'),
    path('create/<int:document_id>/', views.quiz_create_view, name='create'),
    path('<int:pk>/', views.quiz_detail_view, name='detail'),
    path('<int:pk>/take/', views.quiz_take_view, name='take'),
    path('<int:pk>/delete/', views.quiz_delete_view, name='delete'),
    path('result/<int:attempt_id>/', views.quiz_result_view, name='result'),
    path('result/<int:attempt_id>/pdf/', views.export_pdf_view, name='export_pdf'),
]