import random
from django.shortcuts import render, redirect, get_object_or_404

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.utils import timezone

from django.http import HttpResponse

from django.template.loader import render_to_string
import weasyprint


from .models import Quiz, UserQuizAttempt
from apps.documents.models import Document
from .services.quiz_service import QuizService 
from .services.grading_service import GradingService
from .services.shuffler import QuestionShuffler



@login_required
def quiz_list_view(request):
    """Hiển thị danh sách các bài Quiz đã tạo (Chỉ của user hiện tại)"""
    # Chỉ lấy quiz của người đang đăng nhập
    quizzes = Quiz.objects.filter(user=request.user).order_by('-created_at')
    return render(request, 'quizzes/list.html', {'quizzes': quizzes})

@login_required
def quiz_create_view(request, document_id):
    """Xử lý form tạo Quiz mới từ Document bằng AI"""
    document = get_object_or_404(Document, id=document_id, user=request.user)
    
    if request.method == 'POST':
        num_questions = int(request.POST.get('num_questions', 5))
        difficulty = request.POST.get('difficulty', 'medium')
        
        try:
            
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
            return redirect('documents:detail', pk=document_id)

    return render(request, 'quizzes/create.html', {'document': document})

@login_required
def quiz_detail_view(request, pk):
    """Xem chi tiết bộ đề đã tạo (Preview)"""
    # Bảo mật: Chỉ chủ sở hữu mới được xem chi tiết đề
    quiz = get_object_or_404(Quiz, pk=pk, user=request.user)
    questions = quiz.questions.all().order_by('order')
    
    return render(request, 'quizzes/detail.html', {
        'quiz': quiz,
        'questions': questions,
    })

@login_required
def quiz_delete_view(request, pk):
    """Xóa bộ đề"""
    quiz = get_object_or_404(Quiz, pk=pk, user=request.user)

    if request.method == 'POST':
        quiz.delete()
        messages.success(request, "Đã xóa bộ đề thành công!")
        return redirect('quizzes:list')

    return redirect('quizzes:detail', pk=pk)


# ==========================================
# PHASE 5: EXAM & GRADING
# ==========================================

@login_required
def quiz_take_view(request, pk):
    """Giao diện làm bài thi và xử lý chấm điểm dùng Session Seed"""
    quiz = get_object_or_404(Quiz, pk=pk, user=request.user)
    session_key = f'quiz_seed_{quiz.id}'
    
    if request.method == 'POST':
        # Lấy lại seed từ session lúc user mở đề thi
        seed = request.session.get(session_key)
        if seed is None:
            messages.error(request, "Phiên làm bài đã hết hạn hoặc không hợp lệ. Vui lòng thi lại.")
            return redirect('quizzes:detail', pk=quiz.id)

        # 1. Trộn lại đề Y HỆT như lúc hiển thị cho user (để index correct_answer khớp với UI)
        questions_raw = list(quiz.questions.values('id', 'question_text', 'options', 'correct_answer', 'explanation'))
        shuffled_questions = QuestionShuffler.shuffle_quiz(questions_raw, seed=seed)
        
        # 2. Thu thập đáp án user gửi lên
        user_answers = {}
        for q in shuffled_questions:
            selected_idx = request.POST.get(f"question_{q['id']}")
            if selected_idx is not None:
                user_answers[int(q['id'])] = int(selected_idx)
                
        # 3. Dùng GradingService để chấm điểm (Không tự code tay vòng lặp ở View nữa)
        grading_result = GradingService.grade_shuffled_quiz(shuffled_questions, user_answers)
        
        # 4. Lưu kết quả
        attempt = GradingService.save_attempt(quiz, request.user, user_answers, grading_result)
        
        # 5. Xóa seed để user không thể f5 nộp lại bài cũ
        request.session.pop(session_key, None)
        
        messages.success(request, "Đã nộp bài thành công!")
        return redirect('quizzes:result', attempt_id=attempt.id)

    # --- GET: XỬ LÝ HIỂN THỊ ĐỀ THI ---
    # Tạo seed mới hoặc dùng lại seed nếu user lỡ F5 trang
    seed = request.session.get(session_key) or random.randint(0, 2**32 - 1)
    request.session[session_key] = seed

    # Chuyển QuerySet thành list các dictionary để Shuffler xử lý được
    questions_raw = list(quiz.questions.values('id', 'question_text', 'options', 'correct_answer'))
    shuffled_questions = QuestionShuffler.shuffle_quiz(questions_raw, seed=seed)
    
    return render(request, 'quizzes/quiz_take.html', {
        'quiz': quiz,
        'questions': shuffled_questions  # Đẩy list đã xáo trộn xuống template
    })


# ==========================================
# PHASE 6: XUẤT PDF
# ==========================================

@login_required
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
       
        
    html_string = render_to_string('quizzes/pdf_template.html', {
        'attempt': attempt,
        'results_data': results_data,
    })
    
    
    html = weasyprint.HTML(string=html_string, base_url=request.build_absolute_uri('/'))
    pdf = html.write_pdf()
    
    
    response = HttpResponse(pdf, content_type='application/pdf')
    filename = f"Ket_qua_{attempt.id}.pdf" 
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    
    return response