# apps/quizzes/views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from .models import Quiz
from apps.documents.models import Document
from .services.quiz_service import QuizService        # Đã bỏ import GeminiQuizGenerator vì Service lo hết rồi

# ==========================================
# PHASE 4: QUIZ GENERATION & MANAGEMENT
# ==========================================

def quiz_list_view(request):
    """Hiển thị danh sách các bài Quiz đã tạo"""
    quizzes = Quiz.objects.all().order_by('-created_at')
    return render(request, 'quizzes/quiz_list.html', {'quizzes': quizzes})

def quiz_create_view(request, document_id):
    """Xử lý form tạo Quiz mới từ Document bằng AI"""
    document = get_object_or_404(Document, id=document_id)
    
    if request.method == 'POST':
        num_questions = int(request.POST.get('num_questions', 5))
        difficulty = request.POST.get('difficulty', 'medium')
        
        try:
            # Gọi Service thực hiện toàn bộ quy trình: Lấy Text -> Gọi AI -> Lưu Database
            quiz_service = QuizService()
            quiz = quiz_service.create_quiz_from_document(
                document=document,
                user=request.user,
                num_questions=num_questions,
                difficulty=difficulty
            )
            
            messages.success(request, f"Đã tạo thành công bộ câu hỏi '{quiz.title}'!")
            return redirect('quizzes:list')
            
        except Exception as e:
            messages.error(request, f"Có lỗi xảy ra: {str(e)}")
            return redirect('quizzes:create', document_id=document_id)

    return render(request, 'quizzes/create.html', {'document': document})

# Mở file apps/quizzes/views.py và sửa lại hàm này:

def quiz_detail_view(request, pk):
    """Xem chi tiết bộ đề đã tạo (Preview)"""
    quiz = get_object_or_404(Quiz, pk=pk)
    
    # Đã sửa: Xóa prefetch_related và thêm order_by để xếp đúng thứ tự
    questions = quiz.questions.all().order_by('order')
    
    context = {
        'quiz': quiz,
        'questions': questions,
    }
    return render(request, 'quizzes/detail.html', context)

def quiz_delete_view(request, pk):
    """Xóa bộ đề (Bảo mật bằng method POST)"""
    quiz = get_object_or_404(Quiz, pk=pk)
    
    # Bảo mật: Chỉ người tạo mới được xóa. 
    # Nếu đang test chưa có phần đăng nhập, bạn có thể comment 2 dòng if này lại
    if getattr(request.user, 'is_authenticated', False) and request.user != quiz.creator:
        messages.error(request, "Bạn không có quyền xóa bộ đề này.")
        return redirect('quizzes:list')

    if request.method == 'POST':
        quiz.delete()
        messages.success(request, f"Đã xóa thành công bộ đề: {quiz.title}")
        return redirect('quizzes:list')
    
    return render(request, 'quizzes/quiz_confirm_delete.html', {'quiz': quiz})


# ==========================================
# PHASE 5: EXAM & GRADING (DUMMY VIEWS)
# ==========================================
# Ghi chú: Các hàm này hiện tại chỉ làm nhiệm vụ "giữ chỗ" để Server không báo lỗi.

def quiz_take_view(request, pk):
    """Giao diện làm bài thi (Sẽ code logic xáo trộn câu hỏi vào ngày mai)"""
    quiz = get_object_or_404(Quiz, pk=pk)
    return render(request, 'quizzes/quiz_take.html', {'quiz': quiz})

def quiz_result_view(request, attempt_id):
    """Giao diện xem kết quả (Sẽ code logic chấm điểm vào ngày mai)"""
    # attempt = get_object_or_404(UserQuizAttempt, id=attempt_id)
    return render(request, 'quizzes/quiz_result.html', {'attempt_id': attempt_id})