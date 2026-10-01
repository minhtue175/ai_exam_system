import random
import redis
import weasyprint

from django.conf import settings
from django.core.paginator import Paginator
from django.shortcuts import render, redirect, get_object_or_404

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.utils import timezone

from django.http import HttpResponse, JsonResponse
from django.views.decorators.http import require_POST
import json

from django.template.loader import render_to_string



from apps.core.security import TokenBucket
from apps.core.cache_utils import CacheManager
from .models import Quiz, UserQuizAttempt
from apps.documents.models import Document
from .services.quiz_service import QuizService 
from .services.grading_service import GradingService
from .services.shuffler import QuestionShuffler
from .tasks import generate_quiz_task



@login_required
def quiz_list_view(request):
    """Hiển thị danh sách các bài Quiz đã tạo (Chỉ của user hiện tại, tối ưu chống N+1)"""
    
    quizzes = Quiz.objects.filter(user=request.user).select_related('document').order_by('-created_at')
    paginator = Paginator(quizzes, 9)  # 9 per page (3x3 grid)
    page_obj = paginator.get_page(request.GET.get('page'))
    return render(request, 'quizzes/list.html', {'quizzes': page_obj, 'page_obj': page_obj})

@login_required
def quiz_create_view(request, document_id):
    """Xử lý form tạo Quiz mới từ Document bằng AI (Bảo vệ bởi TokenBucket Rate Limiter)"""
    document = get_object_or_404(Document, id=document_id, user=request.user)
    bucket_key = f"user_quiz_{request.user.id}"
    
    if request.method == 'POST':
        # 1. Kiểm tra hạn mức tiêu thụ bằng Token Bucket (Tối đa 5 lượt, hồi 1 lượt mỗi 10 phút)
        is_allowed, remaining, wait_secs = TokenBucket.consume(
            key=bucket_key,
            cost=1.0,
            capacity=5.0,
            refill_time_seconds=600.0
        )

        if not is_allowed:
            wait_mins = max(1, wait_secs // 60)
            messages.warning(
                request,
                f"☕ Bạn đã dùng hết hạn mức ôn tập AI trong giờ này (còn 0/5 lượt). "
                f"Vui lòng nghỉ ngơi thư giãn khoảng {wait_mins} phút để hệ thống tự động nạp lại năng lượng nhé!"
            )
            return redirect('documents:detail', pk=document_id)

        try:
            num_questions = int(request.POST.get('num_questions', 5))
            if num_questions < 1 or num_questions > 40:
                messages.error(request, "Số câu hỏi phải từ 1 đến 40.")
                return redirect('documents:detail', pk=document_id)
        except (ValueError, TypeError):
            messages.error(request, "Số câu hỏi không hợp lệ.")
            return redirect('documents:detail', pk=document_id)

        difficulty = request.POST.get('difficulty', 'remember')
        valid_difficulties = [
            'remember', 'understand', 'apply', 'analyze', 'evaluate', 'create',
            'basic', 'advanced'
        ]
        if difficulty not in valid_difficulties:
            difficulty = 'remember'
        
        try:
            generate_quiz_task.delay(
                document_id=document.id,
                user_id=request.user.id,
                num_questions=num_questions,
                difficulty=difficulty
            )
            
            messages.info(request, f"🚀 AI đang phân tích tài liệu và tạo {num_questions} câu hỏi. Bạn còn {remaining}/5 lượt ôn tập!")
            return redirect('quizzes:list')
        
        except Exception as e:
            messages.error(request, f"Có lỗi xảy ra khi đưa vào hàng đợi: {str(e)}")
            return redirect('documents:detail', pk=document_id)

    # GET: Lấy trạng thái hạn mức để hiển thị lên giao diện
    tokens_available, wait_secs = TokenBucket.get_status(
        key=bucket_key,
        capacity=5.0,
        refill_time_seconds=600.0
    )
    wait_minutes = max(1, wait_secs // 60)

    context = {
        'document': document,
        'tokens_available': tokens_available,
        'wait_minutes': wait_minutes
    }
    return render(request, 'quizzes/create.html', context)


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
        # Invalidate cache sau khi xóa quiz
        CacheManager.invalidate_user_cache(request.user.id)
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
        
        # 4. Thu thập thời gian hoàn thành (tính bằng giây)
        time_spent_raw = request.POST.get('time_spent_seconds', '0')
        try:
            time_spent_seconds = max(0, int(time_spent_raw))
        except (ValueError, TypeError):
            time_spent_seconds = 0
            
        # 5. Lưu kết quả
        attempt = GradingService.save_attempt(
            quiz=quiz,
            user=request.user,
            user_answers=user_answers,
            grading_result=grading_result,
            time_spent_seconds=time_spent_seconds
        )
        
        # 6. Xóa seed để user không thể f5 nộp lại bài cũ
        request.session.pop(session_key, None)
        
        messages.success(request, "Đã nộp bài thành công!")
        return redirect('quizzes:result', attempt_id=attempt.id)

    seed = request.session.get(session_key) or random.randint(0, 2**32 - 1)
    request.session[session_key] = seed

    questions_raw = list(quiz.questions.values('id', 'question_text', 'options', 'correct_answer'))
    shuffled_questions = QuestionShuffler.shuffle_quiz(questions_raw, seed=seed)
    duration_seconds = (quiz.duration_minutes * 60) if (quiz.duration_minutes and quiz.duration_minutes > 0) else 0
    
    return render(request, 'quizzes/quiz_take.html', {
        'quiz': quiz,
        'questions': shuffled_questions,
        'duration_seconds': duration_seconds
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


# =====================================================================
# B1: THUẬT TOÁN SPACED REPETITION (HỆ THỐNG HỘP LEITNER)
# =====================================================================

@login_required
def spaced_repetition_view(request):
    """
    Dashboard Spaced Repetition (Hệ thống hộp Leitner Đa Chế Độ):
    - Chế độ Ngắn Hạn: Ôn thi cấp tốc < 1 tuần (tính bằng Giờ: 1h -> 6h -> 1 ngày -> 3 ngày -> 6 ngày)
    - Chế độ Dài Hạn: Học ngoại ngữ/chứng chỉ 1 tuần -> 1 tháng (1 ngày -> 3 ngày -> 7 ngày -> 14 ngày -> 30 ngày)
    """
    from .services.leitner_service import LeitnerService
    
    # Lấy chế độ từ query parameter hoặc session (mặc định ngắn hạn cho ôn thi)
    mode = request.GET.get('mode') or request.session.get('leitner_mode', 'short_term')
    if mode not in ['short_term', 'long_term']:
        mode = 'short_term'
    request.session['leitner_mode'] = mode

    stats = LeitnerService.get_dashboard_stats(request.user, mode=mode)
    due_cards = LeitnerService.get_due_cards(request.user, mode=mode, limit=10)

    context = {
        'stats': stats,
        'due_cards': due_cards,
        'current_mode': mode,
    }
    return render(request, 'quizzes/spaced_repetition.html', context)


@login_required
@require_POST
def switch_review_mode_view(request):
    """
    API endpoint chuyển đổi chế độ ôn tập (Ngắn hạn / Dài hạn):
    Cập nhật chế độ cho toàn bộ thẻ ôn tập hiện có của user và tính lại thời gian ôn tập.
    """
    from .services.leitner_service import LeitnerService
    try:
        data = json.loads(request.body)
        new_mode = data.get('mode', 'short_term')
        if new_mode not in ['short_term', 'long_term']:
            return JsonResponse({'success': False, 'error': 'Chế độ không hợp lệ!'}, status=400)
            
        custom_first_hours = int(data.get('custom_first_hours', 1))
        if custom_first_hours not in [1, 2, 4, 6, 12, 24]:
            custom_first_hours = 1

        request.session['leitner_mode'] = new_mode
        updated_count = LeitnerService.switch_user_mode(
            request.user,
            new_mode=new_mode,
            custom_first_hours=custom_first_hours
        )

        return JsonResponse({
            'success': True,
            'mode': new_mode,
            'updated_count': updated_count,
            'message': f"Đã chuyển sang chế độ {'Ngắn Hạn (< 1 tuần)' if new_mode == 'short_term' else 'Dài Hạn (1 tuần - 1 tháng)'} thành công!"
        })
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)


@login_required
def review_session_view(request):
    """
    Phiên ôn tập tương tác cho các câu hỏi đến hạn (Due Review Cards):
    Cho phép người dùng kiểm tra lại từng câu, chấm điểm tức thì và điều chỉnh hộp Leitner.
    """
    from .services.leitner_service import LeitnerService
    mode = request.GET.get('mode') or request.session.get('leitner_mode', 'short_term')
    if mode not in ['short_term', 'long_term']:
        mode = 'short_term'

    due_cards = LeitnerService.get_due_cards(request.user, mode=mode, limit=30)
    
    cards_data = []
    for c in due_cards:
        cards_data.append({
            'card_id': c.id,
            'question_text': c.question.question_text,
            'options': c.question.options,
            'box_level': c.box_level,
            'review_mode': c.review_mode,
            'interval_display': c.get_interval_display(),
            'quiz_title': c.question.quiz.title,
        })
    
    context = {
        'cards_count': len(due_cards),
        'cards_data': cards_data,
        'cards_json': json.dumps(cards_data),
        'current_mode': mode,
    }
    return render(request, 'quizzes/review_session.html', context)


@login_required
@require_POST
def review_submit_answer(request):
    """
    API endpoint xử lý câu trả lời của 1 thẻ ôn tập:
    Cập nhật level hộp Leitner (tăng lên hoặc rớt về hộp 1).
    """
    from .services.leitner_service import LeitnerService
    try:
        data = json.loads(request.body)
        card_id = int(data.get('card_id'))
        selected_index = int(data.get('selected_index'))
        
        result = LeitnerService.answer_card(request.user, card_id, selected_index)
        return JsonResponse({'success': True, 'result': result})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)