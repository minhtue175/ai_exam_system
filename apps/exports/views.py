from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from apps.quizzes.models import Quiz
from .services.export_services import prepare_quiz_data, generate_word_document, generate_pdf_document
import urllib.parse

def export_word_view(request, quiz_id):
    # 1. Tìm cái đề thi mà người dùng muốn tải
    quiz = get_object_or_404(Quiz, id=quiz_id)
    
    # 2. Hứng các tham số từ URL (VD: ?mode=teacher&shuffle=true)
    mode = request.GET.get('mode', 'student') # Mặc định là bản sinh viên
    should_shuffle = request.GET.get('shuffle') == 'true'
    
    # 3. Gọi "Bộ não" để xáo trộn và chuẩn bị dữ liệu
    prepared_data = prepare_quiz_data(quiz, should_shuffle=should_shuffle)
    
    # 4. Gọi "Thợ xây" để nặn ra file Word trên RAM
    word_buffer = generate_word_document(quiz.title, prepared_data, mode=mode)
    
    # 5. Đóng gói chuẩn bị gửi đi (Khai báo đúng chuẩn định dạng file Word)
    response = HttpResponse(
        word_buffer.getvalue(),
        content_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document'
    )
    
    # Kỹ thuật xử lý tên file có tiếng Việt có dấu để không bị lỗi lúc tải về
    safe_title = urllib.parse.quote(quiz.title)
    file_suffix = "Dap_An" if mode == 'teacher' else "De_Thi"
    filename = f"{file_suffix}_{safe_title}.docx"
    
    # Lệnh ép trình duyệt phải hiển thị hộp thoại "Save As..." tải file xuống
    response['Content-Disposition'] = f'attachment; filename*=UTF-8\'\'{filename}'
    
    return response

def export_pdf_view(request, quiz_id):
    quiz = get_object_or_404(Quiz, id=quiz_id)
    mode = request.GET.get('mode', 'student')
    should_shuffle = request.GET.get('shuffle') == 'true'
    
    # Tái sử dụng "Bộ não" xáo đề
    prepared_data = prepare_quiz_data(quiz, should_shuffle=should_shuffle)
    pdf_buffer = generate_pdf_document(quiz.title, prepared_data, mode=mode)
    
    # Khai báo định dạng PDF
    response = HttpResponse(pdf_buffer.getvalue(), content_type='application/pdf')
    
    safe_title = urllib.parse.quote(quiz.title)
    file_suffix = "Dap_An" if mode == 'teacher' else "De_Thi"
    filename = f"{file_suffix}_{safe_title}.pdf"
    
    response['Content-Disposition'] = f'attachment; filename*=UTF-8\'\'{filename}'
    return response