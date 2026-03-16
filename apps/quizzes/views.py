
from django.shortcuts import render, redirect, get_object_or_404

from django.contrib import messages
from django.contrib.auth.decorators import login_required # Quan trọng nhất để bảo mật
from django.utils import timezone

from django.http import HttpResponse

from django.template.loader import render_to_string
import weasyprint

# Import models
from .models import Quiz, UserQuizAttempt
from apps.documents.models import Document
from .services.quiz_service import QuizService 

# ==========================================
# PHASE 4: QUIZ GENERATION & MANAGEMENT
# ==========================================

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
    """Giao diện làm bài thi và xử lý chấm điểm"""
    quiz = get_object_or_404(Quiz, pk=pk, user=request.user)
    
    
    
    
    
    if request.method == 'POST':
        correct_answers = 0
        total_questions = quiz.num_questions
        user_answers = {}
        
        
        
        
        
        questions = quiz.questions.all()
        for q in questions:
            
            selected_idx = request.POST.get(f'question_{q.id}')
            
            if selected_idx is not None:
                selected_idx = int(selected_idx)
                user_answers[str(q.id)] = selected_idx
                
                
                if selected_idx == q.correct_answer:
                    correct_answers += 1
               
               
        score = (correct_answers / total_questions) * 10 if total_questions > 0 else 0
        
        
        
        attempt = UserQuizAttempt.objects.create(
            quiz=quiz,
            user=request.user,
            answers=user_answers,
            total_questions=total_questions,
            correct_answers=correct_answers,
            score=score,
            completed_at=timezone.now()
        )
        
        messages.success(request, "Đã nộp bài thành công!")
        return redirect('quizzes:result', attempt_id=attempt.id)

    # Shuffle câu hỏi để chống gian lận
    questions = quiz.questions.all().order_by('?')
    
    return render(request, 'quizzes/quiz_take.html', {
        'quiz': quiz,
        'questions': questions
    })

@login_required
def quiz_result_view(request, attempt_id):
    """Hiển thị kết quả, chấm câu đúng/sai và hiện giải thích"""
    
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
        
    return render(request, 'quizzes/quiz_result.html', {
        'attempt': attempt,
        'results_data': results_data
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