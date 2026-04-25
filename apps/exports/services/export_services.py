import random
import copy
import io
from docx import Document
from docx.shared import Pt, RGBColor
from django.template.loader import render_to_string
from weasyprint import HTML

def prepare_quiz_data(quiz, should_shuffle=False):
    """
    Hàm chuẩn bị dữ liệu đề thi. Có khả năng xáo trộn câu hỏi và đáp án 
    nhưng vẫn giữ nguyên tính chính xác của đáp án đúng.
    """
    # Lấy toàn bộ câu hỏi của quiz này từ Database
    original_questions = list(quiz.questions.all())
    
    # Tạo một bản sao để xáo trộn mà không làm ảnh hưởng đến dữ liệu gốc trong Database
    questions_to_process = copy.deepcopy(original_questions)
    
    if should_shuffle:
        random.shuffle(questions_to_process) # Xáo trộn thứ tự các CÂU HỎI
        
    prepared_data = []
    
    for q in questions_to_process:
        # Lấy dữ liệu của 1 câu hỏi
        q_data = {
            'id': q.id,
            'question_text': q.question_text,
            'options': list(q.options), # Ví dụ: ['Hà Nội', 'Đà Nẵng', 'Huế', 'Sài Gòn']
            'correct_index': q.correct_answer, # Ví dụ: 0 (Hà Nội)
            'explanation': getattr(q, 'explanation', 'Không có giải thích')
        }
        
        if should_shuffle:
            # 1. Lưu lại CÁI CHỮ của đáp án đúng trước khi xáo
            # Ví dụ: q_data['options'][0] -> 'Hà Nội'
            correct_text_value = q_data['options'][q_data['correct_index']]
            
            # 2. Bắt đầu xáo trộn các đáp án A, B, C, D
            random.shuffle(q_data['options'])
            
            # 3. Tìm lại xem cái chữ 'Hà Nội' giờ nó đang nằm ở index số mấy (0, 1, 2 hay 3?)
            new_correct_index = q_data['options'].index(correct_text_value)
            
            # 4. Cập nhật lại index đáp án đúng mới
            q_data['correct_index'] = new_correct_index
            
        prepared_data.append(q_data)
        
    return prepared_data

def generate_word_document(quiz_title, prepared_data, mode='student'):
    """
    Hàm tạo file Word từ dữ liệu đã được chuẩn bị.
    mode: 'student' (chỉ có đề) hoặc 'teacher' (có đáp án đỏ + giải thích)
    """
    doc = Document()
    
    # 1. In Tiêu đề bài thi
    title = doc.add_heading(f'ĐỀ THI: {quiz_title.upper()}', 0)
    title.alignment = 1  # Căn giữa
    
    if mode == 'teacher':
        subtitle = doc.add_paragraph('BẢN DÀNH CHO GIÁO VIÊN (CÓ ĐÁP ÁN CHI TIẾT)')
        subtitle.alignment = 1
        
    doc.add_paragraph()  # Thêm một dòng trống cho thoáng
    
    # 2. Bắt đầu in từng câu hỏi
    labels = ['A', 'B', 'C', 'D']
    
    for i, q in enumerate(prepared_data, 1):
        # In nội dung câu hỏi (In đậm)
        p_question = doc.add_paragraph()
        run_q = p_question.add_run(f'Câu {i}: {q["question_text"]}')
        run_q.bold = True
        
        # In 4 đáp án
        for j, option_text in enumerate(q['options']):
            p_option = doc.add_paragraph()
            run_opt = p_option.add_run(f'   {labels[j]}. {option_text}')
            
            # Logic "Thần thánh" cho Giáo viên: Tô đỏ đáp án đúng
            if mode == 'teacher' and j == q['correct_index']:
                run_opt.bold = True
                run_opt.font.color.rgb = RGBColor(255, 0, 0) # Màu đỏ
                
        # In phần giải thích của AI (Chỉ cho Giáo viên)
        if mode == 'teacher' and q['explanation']:
            p_exp = doc.add_paragraph()
            run_exp = p_exp.add_run(f'   Giải thích: {q["explanation"]}')
            run_exp.italic = True
            run_exp.font.color.rgb = RGBColor(89, 89, 89) # Màu xám cho đỡ chói
            
        doc.add_paragraph() # Dòng trống ngăn cách giữa các câu
        
    # 3. Kỹ thuật Pro: Lưu file vào bộ nhớ ảo (RAM) thay vì lưu rác ra ổ cứng
    buffer = io.BytesIO()
    doc.save(buffer)
    buffer.seek(0)
    
    return buffer

def generate_pdf_document(quiz_title, prepared_data, mode='student'):
    """
    Hàm tạo file PDF bằng cách render file HTML rồi convert sang PDF.
    """
    # 1. Gom dữ liệu để ném vào file HTML
    context = {
        'title': quiz_title,
        'questions': prepared_data,
        'mode': mode
    }
    
    # 2. Dịch file HTML sang dạng text
    html_string = render_to_string('quizzes/export_pdf_template.html', context)
    
    # 3. Dùng "Máy in ảo" WeasyPrint in ra file PDF lưu vào RAM
    buffer = io.BytesIO()
    HTML(string=html_string).write_pdf(buffer)
    buffer.seek(0)
    
    return buffer