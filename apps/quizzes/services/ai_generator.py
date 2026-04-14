"""
Service để generate quiz questions bằng Gemini AI
"""
from google import genai
from django.conf import settings
import json
import re
import time
from typing import List, Dict
import logging

logger = logging.getLogger(__name__)


class GeminiQuizGenerator:
    """Generate quiz questions using Google Gemini AI"""
    
    QUIZ_PROMPT_TEMPLATE = """
Bạn là một giáo viên chuyên nghiệp tạo đề thi trắc nghiệm.

**NHIỆM VỤ:**
Dựa trên văn bản dưới đây, hãy tạo {num_questions} câu hỏi trắc nghiệm chất lượng cao.

**YÊU CẦU BẮT BUỘC:**
1. Câu hỏi phải DỰA HOÀN TOÀN vào nội dung văn bản được cung cấp
2. KHÔNG tạo câu hỏi về thông tin KHÔNG có trong văn bản
3. Câu hỏi phải rõ ràng, dễ hiểu, ngắn gọn
4. Mỗi câu hỏi có ĐÚNG 4 đáp án
5. Chỉ có DUY NHẤT 1 đáp án đúng
6. Các đáp án sai phải hợp lý, liên quan đến chủ đề
7. Độ khó: {difficulty}

**ĐỊNH DẠNG OUTPUT (CHỈ TRẢ VỀ JSON):**
{{
  "questions": [
    {{
      "question": "Câu hỏi ở đây?",
      "options": ["Đáp án A", "Đáp án B", "Đáp án C", "Đáp án D"],
      "correct_answer": 0,
      "explanation": "Giải thích ngắn gọn"
    }}
  ]
}}

**VĂN BẢN:**
{text_content}

Trả về ĐÚNG định dạng JSON, KHÔNG thêm markdown hay text khác.
"""
    
    def __init__(self):
        """Initialize Gemini AI"""
        api_key = settings.GEMINI_API_KEY
        
        if not api_key:
            raise ValueError("GEMINI_API_KEY chưa được cấu hình!")
        
        # Khởi tạo client với API key
        self.client = genai.Client(api_key=api_key)
        logger.info("Gemini AI initialized")
    
    def generate_questions(
        self,
        text_content: str,
        num_questions: int = 10,
        difficulty: str = "medium"
    ) -> List[Dict]:
        """Generate quiz questions from text"""
        try:
            # Validate
            if not text_content or len(text_content.strip()) < 100:
                raise ValueError("Văn bản quá ngắn! Cần ít nhất 100 ký tự.")
            
            if num_questions < 1 or num_questions > 40:
                raise ValueError("Số câu hỏi phải từ 1 đến 40")
            
            if difficulty not in ['easy', 'medium', 'hard']:
                difficulty = 'medium'
            
            # Truncate if too long - TĂNG LÊN CHO 40 CÂU
            max_chars = 30000
            if len(text_content) > max_chars:
                logger.warning(f"Text too long, truncating to {max_chars}")
                text_content = text_content[:max_chars] + "\n\n[...văn bản đã rút gọn...]"
            
            # Build prompt
            prompt = self.QUIZ_PROMPT_TEMPLATE.format(
                num_questions=num_questions,
                difficulty=difficulty,
                text_content=text_content
            )
            
            logger.info(f"Generating {num_questions} questions (difficulty: {difficulty})")
            
           # Call Gemini API
            logger.info(f"Generating {num_questions} questions (difficulty: {difficulty})")
            
            # === BẮT ĐẦU ĐOẠN CODE "MẶT DÀY" CHỐNG LỖI 503 ===
            max_retries = 3
            response_text = ""
            
            for attempt in range(max_retries):
                try:
                    # Gọi cửa Google Gemini
                    response = self.client.models.generate_content(
                        model='gemini-2.5-flash',
                        contents=prompt
                    )
                    response_text = response.text.strip()
                    break  # Nếu gọi thành công, lập tức thoát khỏi vòng lặp
                    
                except Exception as api_err:
                    err_msg = str(api_err).lower()
                    # Nếu Google báo bận (503 hoặc high demand)
                    if '503' in err_msg or 'unavailable' in err_msg or 'high demand' in err_msg:
                        if attempt < max_retries - 1:
                            logger.warning(f"Google AI đang kẹt xe. Đợi 5s rồi thử lại lần {attempt + 2}...")
                            time.sleep(5)  # Đứng chơi 5 giây rồi quay lại vòng lặp
                        else:
                            # Đợi 3 lần mà vẫn không được thì mới báo lỗi ra ngoài
                            raise Exception("Hệ thống AI của Google đang bị quá tải cục bộ, vui lòng thử lại sau ít phút!")
                    else:
                        # Nếu là lỗi khác (như API Key hết tiền) thì văng lỗi luôn không cần đợi
                        raise api_err
            # === KẾT THÚC ĐOẠN CODE CHỐNG 503 ===

            # Parse JSON
            questions = self._parse_response(response_text)
            
            # Parse JSON
            questions = self._parse_response(response_text)
            
            # Validate
            validated = self._validate_questions(questions, num_questions)
            
            logger.info(f"Generated {len(validated)} questions successfully")
            
            return validated
            
        except Exception as e:
            logger.error(f"Error generating questions: {str(e)}")
            raise Exception(f"Lỗi khi tạo câu hỏi: {str(e)}")
    
    def _parse_response(self, response_text: str) -> List[Dict]:
        """Parse JSON from Gemini"""
        try:
            # Remove markdown
            response_text = re.sub(r'```json\s*', '', response_text)
            response_text = re.sub(r'```\s*', '', response_text)
            response_text = response_text.strip()
            
            # Parse JSON
            data = json.loads(response_text)
            
            if 'questions' not in data:
                raise ValueError("Response không có 'questions'")
            
            return data['questions']
            
        except json.JSONDecodeError as e:
            logger.error(f"JSON parse error: {str(e)}")
            raise Exception("AI trả về định dạng không hợp lệ")
    
    def _validate_questions(self, questions: List[Dict], expected: int) -> List[Dict]:
        """Validate questions"""
        validated = []
        
        for idx, q in enumerate(questions):
            try:
                # Check fields
                if not all(k in q for k in ['question', 'options', 'correct_answer']):
                    logger.warning(f"Question {idx} missing fields")
                    continue
                
                # Validate question
                if len(q['question'].strip()) < 10:
                    continue
                
                # Validate options
                if len(q['options']) != 4:
                    continue
                
                # Validate answer
                if q['correct_answer'] not in [0, 1, 2, 3]:
                    continue
                
                # Clean
                validated.append({
                    'question': q['question'].strip(),
                    'options': [opt.strip() for opt in q['options']],
                    'correct_answer': q['correct_answer'],
                    'explanation': q.get('explanation', '').strip() or 'Không có giải thích'
                })
                
            except Exception as e:
                logger.warning(f"Error validating question {idx}: {str(e)}")
                continue
        
        if len(validated) < expected * 0.5:
            raise Exception(
                f"Chỉ tạo được {len(validated)}/{expected} câu hợp lệ. "
                "Vui lòng thử lại!"
            )
        
        return validated[:expected]