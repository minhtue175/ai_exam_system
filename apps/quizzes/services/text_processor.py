"""
Thuật toán Semantic Chunking, TextRank Key-Sentence Extraction,
và Deduplication cho tài liệu và câu hỏi thi.
"""
import re
import math
from typing import List, Dict, Set


class TextRankSummarizer:
    """
    Thuật toán TextRank (biến thể của PageRank):
    Trích xuất các câu trọng tâm chứa nhiều khái niệm, định nghĩa cốt lõi
    xuyên suốt toàn bộ văn bản để làm ngữ cảnh ưu tiên cho AI.
    """

    STOPWORDS: Set[str] = {
        # Từ dừng tiếng Việt phổ biến
        'và', 'là', 'của', 'có', 'trong', 'được', 'cho', 'với', 'về', 'các', 'những',
        'này', 'đó', 'khi', 'thì', 'như', 'tại', 'theo', 'đã', 'sẽ', 'đang', 'từ',
        'đến', 'để', 'một', 'người', 'ra', 'vào', 'lại', 'nên', 'cũng', 'bởi', 'vì',
        'do', 'nếu', 'hoặc', 'nhưng', 'mà', 'sau', 'trước', 'nhiều', 'rất', 'hơn',
        # English common stopwords
        'the', 'is', 'at', 'which', 'on', 'a', 'an', 'and', 'or', 'in', 'of', 'to',
        'for', 'with', 'as', 'by', 'that', 'this', 'it', 'from', 'be', 'are', 'was'
    }

    @classmethod
    def split_sentences(cls, text: str) -> List[str]:
        """Tách văn bản thành danh sách các câu hoàn chỉnh"""
        # Tách theo dấu chấm, chấm than, hỏi chấm hoặc xuống dòng đôi
        raw_sentences = re.split(r'(?<=[.!?\n])\s+', text)
        sentences = []
        for s in raw_sentences:
            s_clean = s.strip()
            # Bỏ qua các câu quá ngắn (dưới 25 ký tự) hoặc chỉ toàn số/ký hiệu
            if len(s_clean) >= 25 and len(s_clean.split()) >= 4:
                sentences.append(s_clean)
        return sentences

    @classmethod
    def tokenize(cls, sentence: str) -> Set[str]:
        """Tách từ và lọc từ dừng (stopwords)"""
        words = re.findall(r'\b[a-zA-Zà-ỹÀ-Ỹ0-9_-]+\b', sentence.lower())
        return {w for w in words if w not in cls.STOPWORDS and len(w) > 1}

    @classmethod
    def sentence_similarity(cls, words1: Set[str], words2: Set[str]) -> float:
        """
        Tính độ tương đồng giữa 2 câu bằng Logarithmic Jaccard:
        Sim(S1, S2) = |W1 ∩ W2| / (log(|W1| + 1) + log(|W2| + 1))
        """
        if not words1 or not words2:
            return 0.0
        intersection = len(words1 & words2)
        if intersection == 0:
            return 0.0
        log_len = math.log(len(words1) + 1) + math.log(len(words2) + 1)
        return intersection / log_len if log_len > 0 else 0.0

    @classmethod
    def extract_key_sentences(cls, text: str, top_k: int = 8) -> List[str]:
        """
        Chạy thuật toán TextRank để chọn ra top_k câu quan trọng nhất.
        Giữ nguyên thứ tự xuất hiện ban đầu trong văn bản.
        """
        sentences = cls.split_sentences(text)
        n = len(sentences)
        if n <= top_k:
            return sentences

        word_sets = [cls.tokenize(s) for s in sentences]

        # Xây dựng ma trận kề trọng số tương đồng
        weights = [[0.0] * n for _ in range(n)]
        degree = [0.0] * n
        for i in range(n):
            for j in range(i + 1, n):
                sim = cls.sentence_similarity(word_sets[i], word_sets[j])
                weights[i][j] = sim
                weights[j][i] = sim
                degree[i] += sim
                degree[j] += sim

        # Khởi tạo PageRank vector
        scores = [1.0 / n] * n
        damping = 0.85
        max_iter = 25
        eps = 1e-4

        for _ in range(max_iter):
            new_scores = [0.0] * n
            diff = 0.0
            for i in range(n):
                rank_sum = 0.0
                for j in range(n):
                    if i != j and degree[j] > 0:
                        rank_sum += (weights[j][i] / degree[j]) * scores[j]
                new_scores[i] = (1.0 - damping) / n + damping * rank_sum
                diff += abs(new_scores[i] - scores[i])
            scores = new_scores
            if diff < eps:
                break

        # Chọn top_k câu có điểm cao nhất
        ranked_indices = sorted(range(n), key=lambda i: scores[i], reverse=True)[:top_k]
        # Sắp xếp lại theo thứ tự câu ban đầu trong văn bản để giữ mạch tư duy logic
        ranked_indices.sort()
        return [sentences[i] for i in ranked_indices]


class SemanticChunker:
    """
    Thuật toán phân đoạn văn bản thông minh (Semantic Chunking with Overlap):
    Chia tài liệu lớn thành các lát cắt đại diện trải dài từ đầu đến cuối sách.
    """

    @staticmethod
    def chunk_document_for_batches(text: str, num_batches: int, max_chunk_chars: int = 8000, overlap_chars: int = 500) -> List[str]:
        """
        Chia văn bản thành num_batches phần tương ứng để giao cho các worker song song.
        Mỗi worker phụ trách 1 phân đoạn riêng biệt (ví dụ: Đầu sách, Giữa sách, Cuối sách).
        """
        text = text.strip()
        total_len = len(text)

        if num_batches <= 1 or total_len <= max_chunk_chars:
            # Tài liệu ngắn hoặc chỉ chạy 1 batch
            return [text[:max_chunk_chars]]

        # Tính bước nhảy để bao phủ đều toàn bộ văn bản
        slice_size = max(total_len // num_batches, 1000)
        chunks = []

        for b in range(num_batches):
            start = max(0, b * slice_size - (overlap_chars if b > 0 else 0))
            end = min(total_len, (b + 1) * slice_size + overlap_chars)
            
            # Cắt tại ranh giới câu hoặc dòng để không cụt câu
            chunk_slice = text[start:end]
            # Tinh chỉnh đầu và đuôi lát cắt để bắt đầu ở đầu câu
            if start > 0 and '\n' in chunk_slice[:200]:
                chunk_slice = chunk_slice[chunk_slice.find('\n') + 1:]
            
            chunks.append(chunk_slice)

        return chunks


class QuestionDeduplicator:
    """
    Thuật toán lọc trùng lặp và kiểm soát chất lượng câu hỏi
    (Pairwise Jaccard Similarity & Distractor Balance Filter).
    """

    @classmethod
    def _get_ngrams(cls, text: str, n: int = 2) -> Set[str]:
        """Tạo tập hợp n-grams từ câu hỏi đã chuẩn hóa"""
        clean_text = re.sub(r'[^\w\s]', '', text.lower())
        words = clean_text.split()
        if len(words) < n:
            return set(words)
        return {' '.join(words[i:i + n]) for i in range(len(words) - n + 1)}

    @classmethod
    def jaccard_similarity(cls, text1: str, text2: str) -> float:
        """Tính độ tương đồng Jaccard giữa 2 câu hỏi"""
        ngrams1 = cls._get_ngrams(text1, n=2)
        ngrams2 = cls._get_ngrams(text2, n=2)
        if not ngrams1 or not ngrams2:
            return 0.0
        intersection = len(ngrams1 & ngrams2)
        union = len(ngrams1 | ngrams2)
        return intersection / union if union > 0 else 0.0

    @classmethod
    def filter_duplicates(cls, questions: List[Dict], similarity_threshold: float = 0.55) -> List[Dict]:
        """
        Loại bỏ các câu hỏi có độ tương đồng ngữ nghĩa quá cao với câu đã có.
        """
        unique_questions: List[Dict] = []

        for q in questions:
            q_text = q.get('question', '').strip()
            is_duplicate = False

            for existing_q in unique_questions:
                existing_text = existing_q.get('question', '').strip()
                sim = cls.jaccard_similarity(q_text, existing_text)
                if sim >= similarity_threshold:
                    is_duplicate = True
                    break

            if not is_duplicate:
                unique_questions.append(q)

        return unique_questions
