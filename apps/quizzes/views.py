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
from .models import Quiz, UserQuizAttempt, Question
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
    """Xem chi tiết bộ đề đã tạo (Preview) kèm lịch sử làm bài"""
    quiz = get_object_or_404(Quiz, pk=pk, user=request.user)
    questions = quiz.questions.all().order_by('order')
    
    attempts = quiz.attempts.filter(user=request.user).order_by('-completed_at')
    best_score = None
    if attempts.exists():
        best_score = max(a.score for a in attempts)
    
    return render(request, 'quizzes/detail.html', {
        'quiz': quiz,
        'questions': questions,
        'attempts': attempts,
        'best_score': best_score,
        'attempts_count': attempts.count(),
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

def _reconstruct_attempt_results(attempt):
    """
    Tái tạo động nội dung câu hỏi/giải thích cho bài thi:
    - Nếu attempt cũ đã có full text ('question_text' trong item) -> dùng luôn (backward compatibility).
    - Nếu là Lean Snapshot (chỉ có question_id) -> nạp động question_text, options, correct_answer từ DB.
    """
    raw_details = attempt.details or []
    if not raw_details:
        return []

    # 1. Tương thích ngược: Nếu bản ghi cũ đã có sẵn text thì trả về luôn
    if isinstance(raw_details[0], dict) and 'question_text' in raw_details[0]:
        return raw_details

    # 2. Lean Snapshot: Chỉ 1 query duy nhất để lấy thông tin các câu hỏi
    q_ids = [item.get('question_id') for item in raw_details if item.get('question_id')]
    questions_map = {q.id: q for q in Question.objects.filter(id__in=q_ids)}

    reconstructed = []
    for item in raw_details:
        qid = item.get('question_id')
        q_obj = questions_map.get(qid)
        user_ans = item.get('user_answer', -1)
        is_corr = item.get('is_correct', False)

        if q_obj:
            reconstructed.append({
                'question_id': qid,
                'question_text': q_obj.question_text,
                'options': q_obj.options,
                'correct_answer': q_obj.correct_answer,
                'user_answer': user_ans,
                'is_correct': is_corr,
                'explanation': q_obj.explanation or 'Theo tài liệu tham khảo.'
            })
        else:
            reconstructed.append({
                'question_id': qid,
                'question_text': f"Câu hỏi #{qid} (Đã được cập nhật trong ngân hàng đề)",
                'options': ['Phương án A', 'Phương án B', 'Phương án C', 'Phương án D'],
                'correct_answer': user_ans if is_corr else 0,
                'user_answer': user_ans,
                'is_correct': is_corr,
                'explanation': 'Nội dung câu hỏi này đã được lưu trữ vĩnh viễn trong nhật ký thi.'
            })
    return reconstructed


@login_required
def quiz_result_view(request, attempt_id):
    """Hiển thị kết quả bài làm: nạp động từ Question hoặc dùng Lean Snapshot"""
    attempt = get_object_or_404(UserQuizAttempt, id=attempt_id, user=request.user)
    results_data = _reconstruct_attempt_results(attempt)
        
    return render(request, 'quizzes/quiz_result.html', {
        'attempt': attempt,
        'results_data': results_data
    })




@login_required
def export_pdf_view(request, attempt_id):
    """Xuất kết quả bài làm ra file PDF đảm bảo đúng dữ liệu lúc thi"""
    attempt = get_object_or_404(UserQuizAttempt, id=attempt_id, user=request.user)
    results_data = _reconstruct_attempt_results(attempt)
       
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


@login_required
def cognitive_analytics_api(request):
    """API trả về phân tích Bloom's Taxonomy Mastery và Lỗ hổng kiến thức"""
    from .services.analytics_service import CognitiveAnalyticsService
    bloom_data = CognitiveAnalyticsService.analyze_bloom_mastery(request.user)
    gaps = CognitiveAnalyticsService.detect_knowledge_gaps(request.user)
    return JsonResponse({
        'status': 'success',
        'bloom_mastery': bloom_data,
        'knowledge_gaps': gaps
    })


@login_required
def retention_curve_api(request):
    """API trả về dữ liệu mô hình hóa đường cong quên lãng Ebbinghaus"""
    from .services.sm2_service import SuperMemo2Service
    try:
        stability = float(request.GET.get('stability', 7.0))
        days = int(request.GET.get('days', 30))
    except (ValueError, TypeError):
        stability = 7.0
        days = 30
        
    curve = SuperMemo2Service.calculate_ebbinghaus_retention_curve(stability_days=stability, days_range=days)
    return JsonResponse({
        'status': 'success',
        'stability_days': stability,
        'curve': curve
    })


@login_required
def quiz_retake_wrong_view(request, pk, attempt_id):
    """Chế độ thi lại thông minh: Chỉ làm lại những câu hỏi đã trả lời sai trong lần thi trước"""
    quiz = get_object_or_404(Quiz, pk=pk, user=request.user)
    attempt = get_object_or_404(UserQuizAttempt, id=attempt_id, user=request.user)

    # Tìm ra danh sách các câu hỏi bị sai
    wrong_qids = [
        item.get('question_id')
        for item in (attempt.details or [])
        if not item.get('is_correct', False) and item.get('question_id')
    ]

    if not wrong_qids:
        messages.success(request, "🎉 Bạn đã làm đúng 100% tất cả các câu hỏi trong lần thi này, không có câu nào bị sai để ôn lại!")
        return redirect('quizzes:result', attempt_id=attempt.id)

    # Lấy các câu hỏi sai
    questions = list(quiz.questions.filter(id__in=wrong_qids).values('id', 'question_text', 'options', 'correct_answer'))
    
    session_key = f'quiz_seed_{quiz.id}'
    seed = random.randint(0, 2**32 - 1)
    request.session[session_key] = seed
    shuffled_questions = QuestionShuffler.shuffle_quiz(questions, seed=seed)

    messages.info(request, f"🎯 Đã kích hoạt Chế độ Phục Thù: Làm lại {len(shuffled_questions)} câu hỏi bạn đã trả lời chưa chính xác!")

    return render(request, 'quizzes/quiz_take.html', {
        'quiz': quiz,
        'questions': shuffled_questions,
        'duration_seconds': 0,
        'is_retake_wrong': True,
        'original_attempt_id': attempt.id
    })


@login_required
def quiz_draft_api(request, pk):
    """Lưu và đồng bộ bản nháp câu trả lời làm bài thi trắc nghiệm (Auto-Save Draft API)"""
    from django.core.cache import cache
    quiz = get_object_or_404(Quiz, pk=pk, user=request.user)
    cache_key = f"quiz_draft_{request.user.id}_{quiz.id}"
    
    if request.method == 'POST':
        try:
            data = json.loads(request.body.decode('utf-8'))
            answers = data.get('answers', {})
            # Lưu draft vào cache trong 24 giờ
            cache.set(cache_key, answers, timeout=86400)
            return JsonResponse({'status': 'ok', 'saved_count': len(answers)})
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
            
    # GET: lấy bản nháp hiện tại
    saved_draft = cache.get(cache_key, {})
    return JsonResponse({'status': 'ok', 'draft': saved_draft})
