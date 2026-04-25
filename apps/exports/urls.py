from django.urls import path
from . import views

app_name = 'exports'

urlpatterns = [
    path('word/<int:quiz_id>/', views.export_word_view, name='export_word'),
    path('pdf/<int:quiz_id>/', views.export_pdf_view, name='export_pdf'),
]