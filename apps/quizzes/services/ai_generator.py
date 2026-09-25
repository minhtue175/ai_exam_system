"""
Service để generate quiz questions bằng Gemini AI
Áp dụng:
1. Thuật toán Parallel Batching (Chia để trị & Gọi đa luồng song song)
2. Thuật toán Semantic Chunking & TextRank Key-Sentence Extraction
3. Bộ lọc chống trùng lặp câu hỏi (Question Deduplicator)
4. Tự động chuyển đổi mô hình dự phòng (Auto-Fallback) chống lỗi 503 Overload
"""
from google import genai
from google.genai import types
from django.conf import settings
import json
import re
import time
from typing import List, Dict
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed

from .text_processor import TextRankSummarizer, SemanticChunker, QuestionDeduplicator

logger = logging.getLogger(__name__)


class GeminiQuizGenerator:
    """Generate quiz questions using Google Gemini AI with Parallel Batching & TextRank"""
    
    # Danh sách các mô hình Flash khả dụng theo thứ tự ưu tiên (Tự động fallback nếu model chính kẹt xe)
    CANDIDATE_MODELS = [
        'gemini-2.5-flash',
        'gemini-3-flash-preview',
        'gemini-3.5-flash-lite',
    ]

    QUIZ_PROMPT_TEMPLATE = """
Bạn là một giảng viên đại học kỳ cựu đang biên soạn đề thi trắc nghiệm. 
Văn phong của bạn tự nhiên, mạch lạc, đi thẳng vào trọng tâm. Tuyệt đối KHÔNG sử dụng các cụm từ sáo rỗng, khuôn mẫu mang "mùi AI".

**NHIỆM VỤ:**
Đọc kỹ phân đoạn văn bản dưới đây và tạo ra chính xác {num_questions} câu hỏi trắc nghiệm chất lượng cao. Độ khó yêu cầu: {difficulty}.

**Ý TƯỞNG CỐT LÕI CỦA TOÀN BỘ TÀI LIỆU (THAM KHẢO TỔNG QUAN):**
{key_concepts}

**KỸ THUẬT RA ĐỀ (BẮT BUỘC TUÂN THỦ):**
1. Nội dung trọng tâm: Hỏi vào các khái niệm cốt lõi, cơ chế hoạt động, định nghĩa hoặc ứng dụng có trong phân đoạn văn bản, KHÔNG hỏi vào tiểu tiết vô nghĩa.
2. Xử lý Ngoại ngữ: 
   - Nếu tài liệu chứa từ vựng/câu văn ngoại ngữ (ví dụ: Tiếng Anh), TRUYỆT ĐỐI KHÔNG dịch sang tiếng Việt. 
   - Giữ nguyên ngoại ngữ trong câu hỏi hoặc đáp án để kiểm tra kỹ năng ngôn ngữ.
3. Nghệ thuật "Gài bẫy" (Distractors):
   - 3 đáp án sai phải cực kỳ hợp lý, dựa trên các nhầm lẫn phổ biến.
   - Các đáp án phải có độ dài tương đương nhau, tránh để đáp án đúng dài bất thường.
4. Giải thích ngắn gọn:
   - Phần "explanation" chỉ từ 1-2 câu, nêu rõ lý do đáp án đúng.

**ĐỊNH DẠNG OUTPUT (BẮT BUỘC TRẢ VỀ JSON THUẦN TÚY):**
{{
  "questions": [
    {{
      "question": "Nội dung câu hỏi...",
      "options": ["Đáp án 1", "Đáp án 2", "Đáp án 3", "Đáp án 4"],
      "correct_answer": 0,
      "explanation": "Giải thích vì..."
    }}
  ]
}}

**PHÂN ĐOẠN VĂN BẢN ĐỂ TẠO {num_questions} CÂU HỎI:**
{text_content}
"""

    def __init__(self):
        """Khởi tạo Gemini AI Client"""
        api_key = settings.GEMINI_API_KEY
        if not api_key:
            raise ValueError("GEMINI_API_KEY chưa được cấu hình!")
        self.client = genai.Client(api_key=api_key)
        logger.info("Gemini AI Client initialized successfully")

    def _determine_batches(self, total_questions: int) -> List[int]:
        """
        Thuật toán phân bổ Batch (Chia để trị):
        - <= 6 câu: 1 batch
        - 7 - 15 câu: 2 batches (VD 10 câu -> [5, 5])
        - 16 - 25 câu: 3 batches (VD 20 câu -> [7, 7, 6])
        - 26 - 40 câu: 4 batches (VD 30 câu -> [8, 8, 7, 7], 40 câu -> [10, 10, 10, 10])
        """
        if total_questions <= 6:
            return [total_questions]
        elif total_questions <= 15:
            num_batches = 2
        elif total_questions <= 25:
            num_batches = 3
        else:
            num_batches = 4

        base = total_questions // num_batches
        rem = total_questions % num_batches
        batches = [base + (1 if i < rem else 0) for i in range(num_batches)]
        return batches

    def _call_gemini_with_fallback(self, prompt: str) -> str:
        """
        Gọi API Gemini với cơ chế Auto-Fallback:
        Nếu model chính quá tải (503/429), tự động chuyển sang model dự phòng tiếp theo.
        """
        config = types.GenerateContentConfig(
            response_mime_type="application/json",
            temperature=0.7,
        )

        last_error = None
        for model_name in self.CANDIDATE_MODELS:
            for attempt in range(2):
                try:
                    logger.info(f"Đang gọi Gemini model '{model_name}' (Thử lần {attempt + 1})...")
                    response = self.client.models.generate_content(
                        model=model_name,
                        contents=prompt,
                        config=config
                    )
                    if response.text and response.text.strip():
                        return response.text.strip()
                except Exception as err:
                    err_msg = str(err).lower()
                    last_error = err
                    if '503' in err_msg or 'unavailable' in err_msg or 'high demand' in err_msg or '429' in err_msg:
                        logger.warning(f"Model '{model_name}' đang quá tải. Đổi thử model khác...")
                        time.sleep(1.5)
                        break  # Đổi sang candidate model tiếp theo
                    else:
                        logger.warning(f"Lỗi gọi model '{model_name}': {err}")
                        time.sleep(1)

        raise Exception(f"Tất cả các mô hình AI đều đang bận: {str(last_error)}")

    def _generate_single_batch(self, chunk_text: str, batch_count: int, difficulty: str, key_concepts: str, batch_idx: int) -> List[Dict]:
        """Worker tạo 1 batch câu hỏi từ 1 phân đoạn văn bản"""
        # Thêm 1 câu dự phòng để phòng trường hợp bị trùng lặp hoặc validate hỏng
        request_count = batch_count + 1
        prompt = self.QUIZ_PROMPT_TEMPLATE.format(
            num_questions=request_count,
            difficulty=difficulty,
            key_concepts=key_concepts or "Tập trung vào các thuật ngữ và định nghĩa chính trong phân đoạn.",
            text_content=chunk_text
        )

        logger.info(f"[Batch {batch_idx + 1}] Bắt đầu tạo {request_count} câu hỏi...")
        response_text = self._call_gemini_with_fallback(prompt)
        questions = self._parse_response(response_text)
        validated = self._validate_questions(questions)
        logger.info(f"[Batch {batch_idx + 1}] Đã nhận {len(validated)} câu hợp lệ.")
        return validated

    def generate_questions(
        self,
        text_content: str,
        num_questions: int = 10,
        difficulty: str = "medium"
    ) -> List[Dict]:
        """
        Hàm chính sinh câu hỏi trắc nghiệm:
        - TextRank trích xuất ý chính toàn văn
        - SemanticChunker phân đoạn tài liệu
        - ThreadPoolExecutor chạy song song các batch
        - QuestionDeduplicator khử trùng lặp
        """
        start_time = time.time()

        if not text_content or len(text_content.strip()) < 100:
            raise ValueError("Văn bản quá ngắn! Cần ít nhất 100 ký tự.")

        if num_questions < 1 or num_questions > 40:
            raise ValueError("Số câu hỏi phải từ 1 đến 40")

        if difficulty not in ['easy', 'medium', 'hard', 'basic', 'advanced']:
            difficulty = 'medium'

        # 1. Thuật toán TextRank: Trích xuất các câu cốt lõi của toàn văn
        logger.info("Đang chạy thuật toán TextRank để trích xuất ý tưởng cốt lõi...")
        key_sentences = TextRankSummarizer.extract_key_sentences(text_content, top_k=6)
        key_concepts_text = "\n- " + "\n- ".join(key_sentences) if key_sentences else ""

        # 2. Thuật toán Phân bổ Batch (Chia để trị)
        batches = self._determine_batches(num_questions)
        num_batches = len(batches)
        logger.info(f"Tổng số câu: {num_questions} -> Chia thành {num_batches} batches song song: {batches}")

        # 3. Thuật toán Semantic Chunking: Chia văn bản thành các phân đoạn đại diện cho từng batch
        chunks = SemanticChunker.chunk_document_for_batches(text_content, num_batches=num_batches)

        # 4. Thuật toán Parallel Batching (Gọi song song qua ThreadPoolExecutor)
        all_generated: List[Dict] = []
        max_workers = min(4, num_batches)

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_batch = {
                executor.submit(
                    self._generate_single_batch,
                    chunks[i if i < len(chunks) else 0],
                    batches[i],
                    difficulty,
                    key_concepts_text,
                    i
                ): i for i in range(num_batches)
            }

            for future in as_completed(future_to_batch):
                batch_i = future_to_batch[future]
                try:
                    batch_questions = future.result()
                    all_generated.extend(batch_questions)
                except Exception as e:
                    logger.error(f"[Batch {batch_i + 1}] Lỗi sinh câu hỏi: {str(e)}")

        # 5. Thuật toán Khử Trùng Lặp (Question Deduplication)
        logger.info(f"Tổng hợp {len(all_generated)} câu thô. Bắt đầu lọc trùng lặp...")
        unique_questions = QuestionDeduplicator.filter_duplicates(all_generated, similarity_threshold=0.55)

        # Đảm bảo đủ số lượng yêu cầu
        if len(unique_questions) < num_questions * 0.5:
            # Nếu lọc quá tay, lấy thêm từ danh sách ban đầu
            unique_questions = all_generated

        if len(unique_questions) < 1:
            raise Exception("Không thể tạo được câu hỏi hợp lệ từ tài liệu này. Vui lòng thử lại!")

        # Cắt đúng số lượng người dùng yêu cầu
        final_questions = unique_questions[:num_questions]
        
        elapsed = time.time() - start_time
        logger.info(f"🎉 Hoàn thành sinh {len(final_questions)} câu hỏi trong {elapsed:.2f} giây (Tăng tốc song song)!")

        return final_questions

    def _parse_response(self, response_text: str) -> List[Dict]:
        """Parse JSON từ kết quả Gemini"""
        try:
            # Dọn dẹp markdown nếu có
            cleaned = re.sub(r'```json\s*', '', response_text)
            cleaned = re.sub(r'```\s*', '', cleaned).strip()

            data = json.loads(cleaned)
            if isinstance(data, list):
                return data
            if isinstance(data, dict):
                return data.get('questions', data.get('items', []))
            return []
        except Exception as e:
            logger.warning(f"Lỗi parse JSON: {e}. Thử regex trích xuất khối mảng...")
            # Fallback regex tìm khối [ ... ]
            match = re.search(r'\[\s*\{.*\}\s*\]', response_text, re.DOTALL)
            if match:
                try:
                    return json.loads(match.group(0))
                except Exception:
                    pass
            return []

    def _validate_questions(self, questions: List[Dict]) -> List[Dict]:
        """Kiểm định tính hợp lệ của từng câu hỏi"""
        validated = []
        for idx, q in enumerate(questions):
            try:
                if not isinstance(q, dict):
                    continue
                q_text = str(q.get('question', '')).strip()
                options = q.get('options', [])
                correct_ans = q.get('correct_answer')

                if len(q_text) < 10:
                    continue
                if not isinstance(options, list) or len(options) != 4:
                    continue
                if correct_ans not in [0, 1, 2, 3, '0', '1', '2', '3']:
                    continue

                validated.append({
                    'question': q_text,
                    'options': [str(opt).strip() for opt in options],
                    'correct_answer': int(correct_ans),
                    'explanation': str(q.get('explanation', '')).strip() or 'Theo tài liệu tham khảo.'
                })
            except Exception as e:
                logger.warning(f"Bỏ qua câu {idx} không hợp lệ: {e}")
                continue

        return validated