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
import hashlib
from concurrent.futures import ThreadPoolExecutor, as_completed

from apps.core.cache_utils import CacheManager
from .text_processor import TextRankSummarizer, SemanticChunker, QuestionDeduplicator

logger = logging.getLogger(__name__)


class GeminiKeyPool:
    """
    Quản lý danh sách Gemini API Keys (Key Rotation Pool):
    - Tự động luân phiên (Round-Robin) giữa các key khỏe mạnh.
    - Tự động phát hiện lỗi 429 / QuotaExceeded / ResourceExhausted và đưa key vào trạng thái Cooldown (nghỉ 60s).
    - Tức thì chuyển sang key dự phòng tiếp theo để không làm gián đoạn bài thi của học viên.
    """
    def __init__(self, api_keys: List[str]):
        self.keys = list(dict.fromkeys([k.strip() for k in api_keys if k and k.strip()]))
        self.cooldowns: Dict[str, float] = {}  # key -> timestamp hết hạn cooldown
        self.current_idx = 0
        self._clients: Dict[str, genai.Client] = {}
        
        for k in self.keys:
            try:
                self._clients[k] = genai.Client(api_key=k)
            except Exception as e:
                logger.warning(f"Không thể khởi tạo client cho API key ...{k[-6:] if len(k) >= 6 else '***'}: {e}")

    def get_healthy_client(self) -> tuple[genai.Client, str]:
        """Lấy một Client có API Key sẵn sàng, ưu tiên key chưa bị cooldown"""
        now = time.time()
        available_keys = [k for k in self.keys if self.cooldowns.get(k, 0) <= now]
        
        if not available_keys:
            # Nếu tất cả key đều bị cooldown, chọn key có thời gian cooldown sắp hết nhất
            logger.warning("Toàn bộ API Keys trong Pool đều đang trong thời gian Cooldown! Đang tái sử dụng key có thời gian chờ ngắn nhất...")
            sorted_keys = sorted(self.keys, key=lambda k: self.cooldowns.get(k, 0))
            chosen_key = sorted_keys[0]
        else:
            # Round-robin giữa các available keys
            self.current_idx = (self.current_idx + 1) % len(available_keys)
            chosen_key = available_keys[self.current_idx]

        client = self._clients.get(chosen_key)
        if not client:
            client = genai.Client(api_key=chosen_key)
            self._clients[chosen_key] = client

        return client, chosen_key

    def mark_key_exhausted(self, key: str, cooldown_seconds: int = 60):
        """Đánh dấu key bị quá tải (429/ResourceExhausted) và tạm thời cho nghỉ"""
        self.cooldowns[key] = time.time() + cooldown_seconds
        masked_key = f"...{key[-6:]}" if len(key) >= 6 else "***"
        logger.warning(
            f"⚠️ Gemini API Key {masked_key} đã hết hạn mức (429/Quota). "
            f"Đang đưa vào Cooldown {cooldown_seconds}s và chuyển sang Key dự phòng khác..."
        )


class GeminiQuizGenerator:
    """Generate quiz questions using Google Gemini AI with Parallel Batching & TextRank"""
    
    # Danh sách các mô hình Flash khả dụng theo thứ tự ưu tiên (Tự động fallback nếu model chính kẹt xe)
    CANDIDATE_MODELS = [
        'gemini-2.5-flash',
        'gemini-3-flash-preview',
        'gemini-3.5-flash-lite',
    ]

    BLOOM_TAXONOMY_GUIDES = {
        'remember': (
            "CẤP ĐỘ 1: NHỚ (REMEMBER) — Nhắc lại kiến thức\n"
            "- Trọng tâm: Hỏi về định nghĩa, thuật ngữ, sự kiện cụ thể, liệt kê các đặc điểm.\n"
            "- Cụm từ gợi ý ra đề: 'Định nghĩa nào sau đây...', 'Đặc điểm nào dưới đây...', 'Liệt kê các...', 'Thuật ngữ nào chỉ...'"
        ),
        'understand': (
            "CẤP ĐỘ 2: HIỂU (UNDERSTAND) — Giải thích ý nghĩa & bản chất\n"
            "- Trọng tâm: Diễn giải khái niệm, so sánh sự tương đồng/khác biệt, giải thích lý do.\n"
            "- Cụm từ gợi ý ra đề: 'Ý nghĩa của...', 'Tại sao lại...', 'So sánh giữa X và Y...', 'Khái niệm nào mô tả đúng nhất...'"
        ),
        'apply': (
            "CẤP ĐỘ 3: ÁP DỤNG (APPLY) — Vận dụng kiến thức vào thực tế\n"
            "- Trọng tâm: Đưa vào bài toán hoặc tình huống giả định thực tế để người học áp dụng quy tắc/quy trình.\n"
            "- Cụm từ gợi ý ra đề: 'Trong tình huống X, cách xử lý nào là...', 'Tính toán...', 'Vận dụng nguyên lý để...'"
        ),
        'analyze': (
            "CẤP ĐỘ 4: PHÂN TÍCH (ANALYZE) — Chia nhỏ vấn đề & mối quan hệ\n"
            "- Trọng tâm: Phân tích nguyên nhân - kết quả, nhận diện cấu trúc, phát hiện lỗi sai hoặc quan hệ tương tác.\n"
            "- Cụm từ gợi ý ra đề: 'Nguyên nhân cốt lõi gây ra...', 'Phân tích điểm mấu chốt...', 'Yếu tố nào quyết định...'"
        ),
        'evaluate': (
            "CẤP ĐỘ 5: ĐÁNH GIÁ (EVALUATE) — Nhận xét, phán đoán & tiêu chí\n"
            "- Trọng tâm: Đánh giá tính hợp lý, so sánh ưu/nhược điểm, nhận định giải pháp tối ưu theo tiêu chí cụ thể.\n"
            "- Cụm từ gợi ý ra đề: 'Nhận định nào là xác đáng nhất...', 'Phương án nào tối ưu nhất và vì sao...', 'Hạn chế lớn nhất...'"
        ),
        'create': (
            "CẤP ĐỘ 6: SÁNG TẠO (CREATE) — Tổng hợp & đề xuất giải pháp mới\n"
            "- Trọng tâm: Thiết kế quy trình, đề xuất giải pháp cải tiến, tổng hợp các yếu tố tạo mô hình mới.\n"
            "- Cụm từ gợi ý ra đề: 'Để giải quyết vấn đề X, giải pháp nào cải tiến nhất...', 'Đề xuất phương án thiết kế...'"
        ),
        'basic': (
            "CẤP ĐỘ CƠ BẢN: Kết hợp Cấp 1 (Nhớ) và Cấp 2 (Hiểu). Đi thẳng vào định nghĩa và cơ chế căn bản."
        ),
        'advanced': (
            "CẤP ĐỘ NÂNG CAO: Kết hợp Cấp 3 (Áp dụng) và Cấp 4 (Phân tích). Tư duy tình huống và phân tích sâu."
        ),
    }

    QUIZ_PROMPT_TEMPLATE = """
Bạn là một giảng viên đại học kỳ cựu đang biên soạn đề thi trắc nghiệm. 
Văn phong của bạn tự nhiên, mạch lạc, đi thẳng vào trọng tâm. Tuyệt đối KHÔNG sử dụng các cụm từ sáo rỗng, khuôn mẫu mang "mùi AI".

**NHIỆM VỤ:**
Đọc kỹ phân đoạn văn bản dưới đây và tạo ra chính xác {num_questions} câu hỏi trắc nghiệm chất lượng cao.

**CHUẨN MỰC TƯ DUY (BLOOM'S TAXONOMY):**
{difficulty_guidance}

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
        """Khởi tạo Gemini AI Client với Key Rotation Pool"""
        keys = getattr(settings, 'GEMINI_API_KEYS', [])
        if not keys and getattr(settings, 'GEMINI_API_KEY', ''):
            keys = [settings.GEMINI_API_KEY]
        
        if not keys:
            raise ValueError("Chưa có GEMINI_API_KEY nào được cấu hình trong file .env!")

        self.key_pool = GeminiKeyPool(keys)
        logger.info(f"GeminiKeyPool đã kích hoạt thành công với {len(self.key_pool.keys)} API Keys dự phòng.")

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
        Gọi API Gemini với cơ chế Auto-Fallback 2 chiều:
        1. Key Rotation: Đổi sang API Key khác khi gặp lỗi 429 / Quota / ResourceExhausted.
        2. Model Fallback: Đổi sang candidate model tiếp theo khi gặp lỗi 503 / High Demand.
        """
        config = types.GenerateContentConfig(
            response_mime_type="application/json",
            temperature=0.7,
        )

        last_error = None
        max_key_attempts = max(len(self.key_pool.keys), 1)

        for key_attempt in range(max_key_attempts):
            client, active_key = self.key_pool.get_healthy_client()
            masked_key = f"...{active_key[-6:]}" if len(active_key) >= 6 else "***"

            for model_name in self.CANDIDATE_MODELS:
                for attempt in range(2):
                    try:
                        logger.info(
                            f"Đang gọi Gemini model '{model_name}' với Key {masked_key} "
                            f"(Thử lần {attempt + 1})..."
                        )
                        response = client.models.generate_content(
                            model=model_name,
                            contents=prompt,
                            config=config
                        )
                        if response.text and response.text.strip():
                            return response.text.strip()
                    except Exception as err:
                        err_msg = str(err).lower()
                        last_error = err
                        
                        # 1. Phát hiện lỗi hết Quota / Rate Limit 429 trên Key này
                        if '429' in err_msg or 'resource_exhausted' in err_msg or 'quota' in err_msg:
                            self.key_pool.mark_key_exhausted(active_key, cooldown_seconds=60)
                            # Thoát khỏi vòng lặp model để chuyển sang Key tiếp theo ngay
                            break
                        
                        # 2. Phát hiện lỗi Model quá tải (503/Unavailable)
                        elif '503' in err_msg or 'unavailable' in err_msg or 'high demand' in err_msg:
                            logger.warning(f"Model '{model_name}' đang quá tải. Đổi thử model khác...")
                            time.sleep(1.5)
                            break  # Chuyển sang candidate model tiếp theo
                        else:
                            logger.warning(f"Lỗi gọi model '{model_name}': {err}")
                            time.sleep(1)
                else:
                    continue
                # Nếu đã break do 429 (hết quota key), nhảy sang key_attempt tiếp theo
                if active_key in self.key_pool.cooldowns:
                    break

        raise Exception(f"Tất cả các API Keys và mô hình AI đều đang bận hoặc quá tải: {str(last_error)}")

    def _generate_single_batch(self, chunk_text: str, batch_count: int, difficulty: str, key_concepts: str, batch_idx: int) -> List[Dict]:
        """Worker tạo 1 batch câu hỏi từ 1 phân đoạn văn bản"""
        # Thêm 1 câu dự phòng để phòng trường hợp bị trùng lặp hoặc validate hỏng
        request_count = batch_count + 1
        bloom_guide = self.BLOOM_TAXONOMY_GUIDES.get(
            difficulty.lower(),
            self.BLOOM_TAXONOMY_GUIDES.get('basic')
        )
        prompt = self.QUIZ_PROMPT_TEMPLATE.format(
            num_questions=request_count,
            difficulty_guidance=bloom_guide,
            key_concepts=key_concepts or "Tập trung vào các thuật ngữ và định nghĩa chính trong phân đoạn.",
            text_content=chunk_text
        )

        logger.info(f"[Batch {batch_idx + 1}] Bắt đầu tạo {request_count} câu hỏi với Bloom level: {difficulty}...")
        response_text = self._call_gemini_with_fallback(prompt)
        questions = self._parse_response(response_text)
        validated = self._validate_questions(questions)
        logger.info(f"[Batch {batch_idx + 1}] Đã nhận {len(validated)} câu hợp lệ.")
        return validated

    def generate_questions(
        self,
        text_content: str,
        num_questions: int = 10,
        difficulty: str = "remember",
        force_regenerate: bool = False
    ) -> List[Dict]:
        """
        Hàm chính sinh câu hỏi trắc nghiệm:
        - Semantic / Prompt Cache: Tiết kiệm chi phí AI & Phản hồi tức thì khi tạo lại đề cùng cấu hình
        - Phân loại cấp độ tư duy Bloom's Taxonomy (remember, understand, apply, analyze, evaluate, create)
        - TextRank trích xuất ý chính toàn văn (có cache)
        - SemanticChunker phân đoạn tài liệu
        - ThreadPoolExecutor chạy song song các batch
        - QuestionDeduplicator khử trùng lặp
        """
        start_time = time.time()

        if not text_content or len(text_content.strip()) < 100:
            raise ValueError("Văn bản quá ngắn! Cần ít nhất 100 ký tự.")

        if num_questions < 1 or num_questions > 40:
            raise ValueError("Số câu hỏi phải từ 1 đến 40")

        valid_difficulties = [
            'remember', 'understand', 'apply', 'analyze', 'evaluate', 'create',
            'basic', 'advanced', 'easy', 'medium', 'hard'
        ]
        if difficulty not in valid_difficulties:
            difficulty = 'remember'

        # Tính toán mã băm SHA256 đại diện cho văn bản
        text_hash = hashlib.sha256(text_content.encode('utf-8')).hexdigest()[:16]

        # ⚡ 0. SEMANTIC & PROMPT CACHE CHECK (Kiểm tra xem đề thi đã từng được sinh hay chưa)
        if not force_regenerate:
            cached_quiz = CacheManager.get_ai_quiz(text_hash, num_questions, difficulty)
            if cached_quiz and len(cached_quiz) >= num_questions:
                logger.info(
                    f"⚡ [Cache HIT] Tái sử dụng {num_questions} câu hỏi từ Semantic Cache (hash={text_hash}). "
                    f"Phản hồi ngay tức thì, tiết kiệm 100% chi phí AI Token!"
                )
                return cached_quiz[:num_questions]

        # 1. Thuật toán TextRank: Trích xuất các câu cốt lõi (Kiểm tra cache trước)
        cached_summary = CacheManager.get_ai_summary(text_hash)
        if cached_summary:
            logger.info("⚡ [Cache HIT] Tái sử dụng tóm tắt TextRank từ Semantic Cache.")
            key_sentences = cached_summary
        else:
            logger.info("Đang chạy thuật toán TextRank để trích xuất ý tưởng cốt lõi...")
            key_sentences = TextRankSummarizer.extract_key_sentences(text_content, top_k=6)
            CacheManager.set_ai_summary(text_hash, key_sentences)

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
        
        # ⚡ Lưu vào Semantic / Prompt Cache cho các lần tái sử dụng sau (TTL 24 giờ)
        CacheManager.set_ai_quiz(text_hash, num_questions, difficulty, final_questions)

        elapsed = time.time() - start_time
        logger.info(f"🎉 Hoàn thành sinh {len(final_questions)} câu hỏi trong {elapsed:.2f} giây (Đã lưu vào Semantic Cache)!")

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