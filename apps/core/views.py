from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.db.models import Q

# Import các Model từ các app khác nhau
from apps.documents.models import Document
from apps.quizzes.models import UserQuizAttempt, Quiz

def home_view(request):
    """Trang chủ dành cho khách chưa đăng nhập"""
    if request.user.is_authenticated:
        return redirect('core:dashboard')
    return render(request, 'core/home.html')

@login_required
def dashboard_view(request):
    """Dashboard trung tâm: Tìm kiếm và hiển thị Documents + Quiz Attempts"""
    
    # 1. Lấy từ khóa từ thanh Search (xử lý khoảng trắng thừa)
    search_query = request.GET.get('search', '').strip()
    
    # 2. Khởi tạo QuerySet cơ bản cho User hiện tại
    documents = Document.objects.filter(user=request.user)
    recent_attempts = UserQuizAttempt.objects.filter(user=request.user).select_related('quiz')
    
    # 3. LOGIC TÌM KIẾM SONG SONG
    if search_query:
        # Tìm trong tài liệu: Tên file hoặc nội dung bên trong file
        documents = documents.filter(
            Q(filename__icontains=search_query) |
            Q(extracted_text__icontains=search_query)
        )
        # Tìm trong lịch sử thi: Tên của bộ đề đã làm
        recent_attempts = recent_attempts.filter(
            Q(quiz__title__icontains=search_query)
        )
    
    # 4. Sắp xếp: Tài liệu mới nhất lên đầu, Bài thi mới nộp lên đầu
    documents = documents.order_by('-created_at')
    # Chỉ lấy 5 kết quả thi gần nhất để giao diện gọn gàng như mẫu
    recent_attempts = recent_attempts.order_by('-completed_at')[:5]

    context = {
        'documents': documents,
        'total_documents': documents.count(),
        'search_query': search_query,
        'recent_attempts': recent_attempts,
    }
    return render(request, 'core/dashboard.html', context)