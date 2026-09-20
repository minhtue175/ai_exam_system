import random
import redis
import weasyprint

from django.conf import settings
from django.core.paginator import Paginator
from django.shortcuts import render, redirect, get_object_or_404

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.utils import timezone

from django.http import HttpResponse

from django.template.loader import render_to_string



from .models import Quiz, UserQuizAttempt
from apps.documents.models import Document
from .services.quiz_service import QuizService 
from .services.grading_service import GradingService
from .services.shuffler import QuestionShuffler
from .tasks import generate_quiz_task



@login_required
def quiz_list_view(request):
    """Hiển thị danh sách các bài Quiz đã tạo (Chỉ của user hiện tại)"""
    
    quizzes = Quiz.objects.filter(user=request.user).order_by('-created_at')
    paginator = Paginator(quizzes, 9)  # 9 per page (3x3 grid)
    page_obj = paginator.get_page(request.GET.get('page'))
    return render(request, 'quizzes/list.html', {'quizzes': page_obj, 'page_obj': page_obj})

@login_required
def quiz_create_view(request, document_id):
    """Xử lý form tạo Quiz mới từ Document bằng AI (CHẠY NGẦM)"""
    document = get_object_or_404(Document, id=document_id, user=request.user)
    
    if request.method == 'POST':
       
        try:
            r = redis.Redis.from_url(settings.CELERY_BROKER_URL)
            redis_key = f"spam_lock_quiz_{request.user.id}"
            if r.exists(redis_key):
                messages.warning(request, "⚠️ Bạn thao tác quá nhanh! Vui lòng đợi khoảng 30 giây để AI xử lý trước khi tạo thêm đề mới.")
                return redirect('documents:detail', pk=document_id)
            r.set(redis_key, 'locked', ex=30)
        except Exception:
            pass

        try:
            num_questions = int(request.POST.get('num_questions', 5))
            if num_questions < 1 or num_questions > 40:
                messages.error(request, "Số câu hỏi phải từ 1 đến 40.")
                return redirect('documents:detail', pk=document_id)
        except (ValueError, TypeError):
            messages.error(request, "Số câu hỏi không hợp lệ.")
            return redirect('documents:detail', pk=document_id)

        difficulty = request.POST.get('difficulty', 'medium')
        if difficulty not in ['easy', 'medium', 'hard', 'basic', 'advanced']:
            difficulty = 'medium'
        
        
        try:
            
            generate_quiz_task.delay(
                document_id=document.id,
                user_id=request.user.id,
                num_questions=num_questions,
                difficulty=difficulty
            )
            
            
            messages.info(request, "Hệ thống đang phân tích. Vui lòng chờ trong dây lát!")
            return redirect('quizzes:list')
        
        except Exception as e:
            messages.error(request, f"Có lỗi xảy ra khi đưa vào hàng đợi: {str(e)}")
            return redirect('documents:detail', pk=document_id)

    return render(request, 'quizzes/create.html', {'document': document})


@login_required
def quiz_detail_view(request, pk):
    """Xem chi tiết bộ đề đã tạo (Preview)"""
    
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
                try:
                    user_answers[int(q['id'])] = int(selected_idx)
                except (ValueError, TypeError):
                    continue
                
        # 3. Dùng GradingService để chấm điểm
        grading_result = GradingService.grade_shuffled_quiz(shuffled_questions, user_answers)
        
        # 4. Lưu kết quả
        attempt = GradingService.save_attempt(quiz, request.user, user_answers, grading_result)
        
        # 5. Xóa seed để user không thể f5 nộp lại bài cũ
        request.session.pop(session_key, None)
        
        messages.success(request, "Đã nộp bài thành công!")
        return redirect('quizzes:result', attempt_id=attempt.id)

    
    seed = request.session.get(session_key) or random.randint(0, 2**32 - 1)
    request.session[session_key] = seed


    questions_raw = list(quiz.questions.values('id', 'question_text', 'options', 'correct_answer'))
    shuffled_questions = QuestionShuffler.shuffle_quiz(questions_raw, seed=seed)
    
    return render(request, 'quizzes/quiz_take.html', {
        'quiz': quiz,
        'questions': shuffled_questions  
    })

@login_required
def quiz_result_view(request, attempt_id):
    """Hiển thị kết quả siêu tốc lấy từ JSON snapshot"""
    attempt = get_object_or_404(UserQuizAttempt, id=attempt_id, user=request.user)
    
    # Lấy mảng results đã lưu thẳng từ JSON ra
    results_data = attempt.details or []
        
    return render(request, 'quizzes/quiz_result.html', {
        'attempt': attempt,
        'results_data': results_data
    })




@login_required
def export_pdf_view(request, attempt_id):
    """Xuất kết quả bài làm ra file PDF đảm bảo đúng dữ liệu lúc thi"""
    attempt = get_object_or_404(UserQuizAttempt, id=attempt_id, user=request.user)
    
    
    results_data = attempt.details or []
       
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