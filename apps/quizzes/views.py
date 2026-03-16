# apps/quizzes/views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from .models import Quiz
from apps.documents.models import Document
from .services.quiz_service import QuizService     
from django.utils import timezone
from .models import Quiz, UserQuizAttempt
from django.http import HttpResponse
from django.template.loader import render_to_string
import weasyprint

# Đã bỏ import GeminiQuizGenerator vì Service lo hết rồi

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

# Mở apps/quizzes/views.py tìm và sửa hàm này:

def quiz_delete_view(request, pk):
    """Xóa bộ đề"""
    quiz = get_object_or_404(Quiz, pk=pk)
    
    # Đã sửa: quiz.creator thành quiz.user
    if request.user != quiz.user:
        messages.error(request, "Bạn không có quyền xóa bộ đề này.")
        return redirect('quizzes:list')

    if request.method == 'POST':
        quiz.delete()
        messages.success(request, "Đã xóa bộ đề thành công!")
        return redirect('quizzes:list')

    return redirect('quizzes:detail', pk=pk)


# ==========================================
# PHASE 5: EXAM & GRADING
# ==========================================


def quiz_take_view(request, pk):
    """Giao diện làm bài thi và xử lý chấm điểm"""
    quiz = get_object_or_404(Quiz, pk=pk)
    
    # 1. XỬ LÝ KHI NGƯỜI DÙNG BẤM "NỘP BÀI" (POST)
    if request.method == 'POST':
        correct_answers = 0
        total_questions = quiz.num_questions
        user_answers = {}  # Lưu id_câu_hỏi: đáp_án_chọn
        
        # Duyệt qua toàn bộ câu hỏi để chấm điểm
        questions = quiz.questions.all()
        for q in questions:
            # Lấy đáp án user chọn từ form (name là question_1, question_2...)
            selected_idx = request.POST.get(f'question_{q.id}')
            
            if selected_idx is not None:
                selected_idx = int(selected_idx)
                user_answers[str(q.id)] = selected_idx
                
                # So sánh với đáp án đúng của AI
                if selected_idx == q.correct_answer:
                    correct_answers += 1
                    
        # Tính điểm hệ 10
        score = (correct_answers / total_questions) * 10 if total_questions > 0 else 0
        
        # Lưu lịch sử làm bài vào Database (Model chúng ta vừa tạo)
        attempt = UserQuizAttempt.objects.create(
            quiz=quiz,
            user=request.user,
            answers=user_answers,
            total_questions=total_questions,
            correct_answers=correct_answers,
            score=score,
            completed_at=timezone.now()
        )
        
        messages.success(request, "Đã nộp bài thành công! Xem kết quả chi tiết bên dưới.")
        return redirect('quizzes:result', attempt_id=attempt.id)

    # 2. XỬ LÝ KHI NGƯỜI DÙNG VÀO TRANG (GET)
    # Roadmap: Làm bài thi (shuffle câu hỏi). Lệnh order_by('?') sẽ trộn ngẫu nhiên câu hỏi.
    questions = quiz.questions.all().order_by('?')
    
    return render(request, 'quizzes/quiz_take.html', {
        'quiz': quiz,
        'questions': questions
    })

def quiz_result_view(request, attempt_id):
    """Hiển thị kết quả, chấm câu đúng/sai và hiện giải thích"""
    # Lấy bài làm ra (Bảo mật: Chỉ cho phép người làm bài xem lại kết quả của mình)
    attempt = get_object_or_404(UserQuizAttempt, id=attempt_id, user=request.user)
    
    # Lấy lại danh sách câu hỏi theo đúng thứ tự ban đầu để hiển thị
    questions = attempt.quiz.questions.all().order_by('order')
    
    # Đóng gói dữ liệu để truyền ra Template HTML xử lý cho dễ
    results_data = []
    for q in questions:
        user_choice = attempt.answers.get(str(q.id))
        results_data.append({
            'question': q,
            'user_choice': user_choice,
            'is_correct': user_choice == q.correct_answer
        })
        
    return render(request, 'quizzes/quiz_result.html', {
        'attempt': attempt,
        'results_data': results_data
    })
    
    
    # ==========================================
# PHASE 6: XUẤT PDF
# ==========================================
def export_pdf_view(request, attempt_id):
    """Xuất kết quả bài làm ra file PDF"""
    attempt = get_object_or_404(UserQuizAttempt, id=attempt_id, user=request.user)
    questions = attempt.quiz.questions.all().order_by('order')
    
    results_data = []
    for q in questions:
        user_choice = attempt.answers.get(str(q.id))
        results_data.append({
            'question': q,
            'user_choice': user_choice,
            'is_correct': user_choice == q.correct_answer
        })
        
    # Render dữ liệu ra HTML
    html_string = render_to_string('quizzes/pdf_template.html', {
        'attempt': attempt,
        'results_data': results_data,
    })
    
    # Dùng WeasyPrint tạo PDF
    html = weasyprint.HTML(string=html_string, base_url=request.build_absolute_uri('/'))
    pdf = html.write_pdf()
    
    # Trả về file cho trình duyệt tải xuống
    response = HttpResponse(pdf, content_type='application/pdf')
    # Encode tên file để tránh lỗi tiếng Việt
    filename = f"Ket_qua_{attempt.quiz.id}.pdf" 
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    
    return response