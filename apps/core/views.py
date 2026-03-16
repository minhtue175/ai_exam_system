from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.db.models import Q

# Import các Model cần thiết
from apps.documents.models import Document
from apps.quizzes.models import UserQuizAttempt

def home_view(request):
    """Home page"""
    if request.user.is_authenticated:
        return redirect('core:dashboard')
    return render(request, 'core/home.html')

@login_required
def dashboard_view(request):
    """Dashboard - Hiển thị danh sách file và Lịch sử thi"""
    
    # 1. LẤY DANH SÁCH TÀI LIỆU
    documents = Document.objects.filter(user=request.user)
    
    # Tìm kiếm
    search_query = request.GET.get('search', '')
    if search_query:
        documents = documents.filter(
            Q(filename__icontains=search_query) |
            Q(extracted_text__icontains=search_query)
        )
    
    documents = documents.order_by('-created_at')

    # 2. LẤY LỊCH SỬ LÀM BÀI THI (5 bài gần nhất)
    recent_attempts = UserQuizAttempt.objects.filter(
        user=request.user
    ).select_related('quiz').order_by('-completed_at')[:5]
    
    context = {
        'documents': documents,
        'total_documents': documents.count(),
        'search_query': search_query,
        'recent_attempts': recent_attempts,  # Đưa dữ liệu điểm ra HTML
    }
    return render(request, 'core/dashboard.html', context)