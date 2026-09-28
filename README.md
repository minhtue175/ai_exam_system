<div align="center">

# 🎓 FLUESY EXAM
### Hệ Thống Quản Lý Tài Liệu & Ôn Tập Luyện Thi Thông Minh Hỗ Trợ Bởi AI

[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![Django](https://img.shields.io/badge/Django-5.0+-092E20?style=for-the-badge&logo=django&logoColor=white)](https://www.djangoproject.com/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16+-336791?style=for-the-badge&logo=postgresql&logoColor=white)](https://www.postgresql.org/)
[![Redis](https://img.shields.io/badge/Redis-7.4+-DC382D?style=for-the-badge&logo=redis&logoColor=white)](https://redis.io/)
[![Celery](https://img.shields.io/badge/Celery-5.3+-37814A?style=for-the-badge&logo=celery&logoColor=white)](https://docs.celeryq.dev/)
[![Google Gemini](https://img.shields.io/badge/Gemini_AI-2.5_Flash-4285F4?style=for-the-badge&logo=google&logoColor=white)](https://ai.google.dev/)
[![Channels](https://img.shields.io/badge/WebSockets-Channels-1E3B70?style=for-the-badge&logo=django&logoColor=white)](https://channels.readthedocs.io/)

*Biến tài liệu học tập thô (PDF, Word) thành ngân hàng câu hỏi trắc nghiệm chuẩn hóa sư phạm, kết hợp chu kỳ ôn tập ngắt quãng Spaced Repetition và công nghệ AI hiện đại.*

---

</div>

## 📌 Mục Lục
- [1. Giới Thiệu Dự Án](#1-giới-thiệu-dự-án)
- [2. Các Thuật Toán Cốt Lõi (Core Algorithms)](#2-các-thuật-toán-cốt-lõi-core-algorithms)
  - [2.1. Sinh Đề Song Song (Parallel Batching + Semantic Chunking + TextRank)](#21-sinh-đề-song-song-parallel-batching--semantic-chunking--textrank)
  - [2.2. Trộn Đề Có Ràng Buộc Sư Phạm (Constrained Shuffling)](#22-trộn-đề-có-ràng-buộc-sư-phạm-constrained-shuffling)
  - [2.3. Hệ Thống Ôn Tập Đa Chế Độ (Dual-Mode Leitner Spaced Repetition)](#23-hệ-thống-ôn-tập-đa-chế-độ-dual-mode-leitner-spaced-repetition)
  - [2.4. Phân Loại Tư Duy Chuẩn Quốc Tế (Bloom's Taxonomy Classifier)](#24-phân-loại-tư-duy-chuẩn-quốc-tế-blooms-taxonomy-classifier)
  - [2.5. Kiểm Soát Tài Nguyên API (Token Bucket Rate Limiter)](#25-kiểm-soát-tài-nguyên-api-token-bucket-rate-limiter)
  - [2.6. Tối Ưu Hóa Bộ Nhớ Đệm & CSDL (Cache-Aside & PostgreSQL GIN Search)](#26-tối-ưu-hóa-bộ-nhớ-đệm--csdl-cache-aside--postgresql-gin-search)
- [3. Tính Năng Nổi Bật](#3-tính-năng-nổi-bật)
- [4. Công Nghệ & Kiến Trúc (Tech Stack)](#4-công-nghệ--kiến-trúc-tech-stack)
- [5. Cấu Trúc Thư Mục (Directory Structure)](#5-cấu-trúc-thư-mục-directory-structure)
- [6. Hướng Dẫn Cài Đặt & Khởi Chạy (Installation & Setup)](#6-hướng-dẫn-cài-đặt--khởi-chạy-installation--setup)

---

## 1. Giới Thiệu Dự Án

**Fluesy Exam** là nền tảng quản lý tài liệu và ôn luyện trắc nghiệm tự động hóa. Người dùng chỉ cần tải lên giáo trình, bài giảng hoặc tài liệu tham khảo (PDF, Word), hệ thống sẽ:
1. Tự động bóc tách và tóm lược nội dung trọng tâm.
2. Ứng dụng mô hình AI tiên tiến (**Google Gemini Flash**) để tạo bộ đề trắc nghiệm chuẩn hóa.
3. Cung cấp quy trình làm bài thi trực quan kèm chấm điểm tức thì, xuất bản in Word/PDF có đáp án.
4. Tự động lưu trữ các câu trả lời sai vào **Hộp ghi nhớ Leitner** để nhắc nhở người học ôn tập lại theo chu kỳ khoa học.

---

## 2. Các Thuật Toán Cốt Lõi (Core Algorithms)

### 2.1. Sinh Đề Song Song (Parallel Batching + Semantic Chunking + TextRank)
* **Vấn đề giải quyết:** Khi tài liệu dài (hàng nghìn từ) và người dùng yêu cầu tạo số lượng lớn câu hỏi (20–40 câu), việc gọi AI bằng 1 prompt duy nhất thường dẫn đến lỗi quá tải (timeout), câu hỏi bị cụt hoặc lặp lại ý.
* **Quy trình xử lý:**
  1. **TextRank Keyword Extraction:** Xây dựng đồ thị câu và áp dụng thuật toán PageRank để rút trích các câu ý tưởng cốt lõi của toàn văn bản.
  2. **Semantic Chunking:** Chia văn bản thành các phân đoạn đại diện độc lập mà không làm ngắt đôi cấu trúc câu văn.
  3. **Parallel ThreadPoolExecutor:** Chia bài toán thành các batch nhỏ (tối đa 4 workers song song), giúp giảm thời gian sinh đề xuống chỉ còn **15 – 20 giây**.
  4. **Question Deduplicator:** Tính toán độ tương đồng câu hỏi (Jaccard Similarity + N-gram) để lọc bỏ triệt để các câu trùng ý.

```
[Văn bản thô] ──► [TextRank trích ý cốt lõi] ──► [Semantic Chunking (N Batches)]
                                                         │
               ┌─────────────────┬───────────────────────┼───────────────────────┐
               ▼                 ▼                       ▼                       ▼
          [Worker 1]        [Worker 2]              [Worker 3]              [Worker 4]
               │                 │                       │                       │
               └─────────────────┴───────────────────────┼───────────────────────┘
                                                         ▼
                                          [Question Deduplicator]
                                                         ▼
                                              [Bộ đề Quiz hoàn chỉnh]
```

---

### 2.2. Trộn Đề Có Ràng Buộc Sư Phạm (Constrained Shuffling)
* **Vấn đề giải quyết:** Việc sử dụng hàm `random.shuffle()` ngẫu nhiên thuần túy thường dẫn đến thiên lệch đáp án (ví dụ: đáp án đúng bị dồn về đáp án C, hoặc 3-4 câu liên tiếp đều là đáp án A) gây mất tính khách quan trong thi cử.
* **Quy tắc sư phạm áp dụng:**
  1. **Uniform Distribution Constraint:** Vị trí đáp án đúng A, B, C, D được phân bổ đồng đều xấp xỉ **25%** cho mỗi chữ cái (sai số $\le 1$ câu).
  2. **Anti-Streak Constraint:** Tối đa không quá 2 câu liên tiếp có cùng một chữ cái đáp án đúng.
  3. **Deterministic Seed:** Mã hóa hạt giống (Seed) theo phiên làm bài để tái hiện đúng 100% thứ tự câu hỏi và phương án khi chấm điểm.

---

### 2.3. Hệ Thống Ôn Tập Đa Chế Độ (Dual-Mode Leitner Spaced Repetition)
Hệ thống tích hợp thuật toán Spaced Repetition dựa trên đường cong lãng quên **Ebbinghaus**, tự động phân loại các câu trả lời sai vào **5 ngăn Leitner** với 2 chế độ linh hoạt:

| Ngăn (Box) | 🚀 Chế Độ Ngắn Hạn (< 1 tuần — Ôn Thi Cấp Tốc) | 📚 Chế Độ Dài Hạn (1 tuần — 1 tháng — Ngoại Ngữ/Chứng Chỉ) |
| :---: | :--- | :--- |
| **Ngăn 1** | Sau **1 giờ** *(tùy chọn 1h, 2h, 4h, 6h, 12h)* | Sau **1 ngày (24 giờ)** |
| **Ngăn 2** | Sau **6 giờ** | Sau **3 ngày (72 giờ)** |
| **Ngăn 3** | Sau **24 giờ (1 ngày)** | Sau **7 ngày (1 tuần)** |
| **Ngăn 4** | Sau **72 giờ (3 ngày)** | Sau **14 ngày (2 tuần)** |
| **Ngăn 5** | Sau **144 giờ (6 ngày)** $\rightarrow$ **Thành thạo ✅** | Sau **30 ngày (1 tháng)** $\rightarrow$ **Thành thạo ✅** |

* **Cơ chế:** Trả lời **ĐÚNG** $\rightarrow$ Thăng cấp lên ngăn tiếp theo (`box_level + 1`); Trả lời **SAI** $\rightarrow$ Giáng ngay về **Ngăn 1** để ôn lại.
* **Cảnh báo thông minh:** Hiển thị cảnh báo xác nhận trước khi người dùng chuyển sang Chế độ Dài Hạn để tránh bị lỡ các kỳ thi trong tuần.

---

### 2.4. Phân Loại Tư Duy Chuẩn Quốc Tế (Bloom's Taxonomy Classifier)
Mở rộng thang đo độ khó câu hỏi thành 6 cấp độ tư duy sư phạm của Bloom:
1. **Cấp 1: Nhớ (Remember)** — Nhắc lại định nghĩa, thuật ngữ, sự kiện.
2. **Cấp 2: Hiểu (Understand)** — Giải thích ý nghĩa, bản chất, so sánh đối chiếu.
3. **Cấp 3: Áp dụng (Apply)** — Vận dụng quy tắc vào bài toán/tình huống thực tế.
4. **Cấp 4: Phân tích (Analyze)** — Phân tích nguyên nhân - kết quả, chia nhỏ cấu trúc.
5. **Cấp 5: Đánh giá (Evaluate)** — Nhận xét ưu/nhược điểm, lựa chọn giải pháp tối ưu.
6. **Cấp 6: Sáng tạo (Create)** — Tổng hợp kiến thức và đề xuất giải pháp cải tiến mới.

---

### 2.5. Kiểm Soát Tài Nguyên API (Token Bucket Rate Limiter)
* **Thuật toán Token Bucket:** Mỗi tài khoản được cấp một bình chứa ảo gồm **5 lượt tạo đề AI**. Cứ mỗi **10 phút**, bình tự động hồi lại 1 lượt (Refill rate).
* **Lợi ích:** Ngăn chặn spam request, bảo vệ hạn mức quota miễn phí của Google Gemini API không bị vượt ngưỡng (HTTP 429).
* **Bảo mật đăng nhập:** Chống tấn công Brute-force mật khẩu và chống đăng ký rác theo địa chỉ IP.

---

### 2.6. Tối Ưu Hóa Bộ Nhớ Đệm & CSDL (Cache-Aside & PostgreSQL GIN Search)
* **Thuật toán Cache-Aside (Lazy Loading):** Lưu trữ số liệu thống kê Dashboard và Profile vào Redis với TTL linh hoạt (120s – 300s). Giảm hơn **80%** lượng truy vấn DB lặp lại.
* **Cache Invalidation:** Tự động xóa cache tương ứng khi user upload file mới, xóa tài liệu hoặc nộp bài thi.
* **PostgreSQL GIN Trigram & Full-Text Search:** Tìm kiếm gần đúng (fuzzy search) với `similarity()` và `SearchRank()` trên chỉ mục `gin_trgm_ops`, hỗ trợ gõ sai chính tả và tốc độ truy vấn mili-giây.
* **Loại bỏ N+1 Query:** Sử dụng `select_related('document')` và `select_related('quiz', 'quiz__document')` xuyên suốt các views.

---

## 3. Tính Năng Nổi Bật

* **📤 Upload & Xử lý Tài liệu Đa định dạng:** Hỗ trợ PDF, DOCX với khả năng bóc tách văn bản chuẩn xác và bảo mật phân quyền.
* **⚡ Tạo Đề Tự Động Siêu Tốc:** Sinh 10–40 câu hỏi trắc nghiệm có đầy đủ 4 đáp án nhiễu logic và giải thích chi tiết trong 15–20 giây.
* **📝 Giao Diện Làm Bài Trực Quan:** Đếm ngược thời gian, cảnh báo nộp bài, ghi nhận kết quả và điểm số chi tiết từng câu.
* **📑 Xuất File Đề Thi Chuyên Nghiệp:** Xuất bản Word (.docx) và PDF (.pdf) chuẩn hóa cho Giáo viên (có đáp án + giải thích) và Học sinh (chỉ có đề bài), tích hợp trộn đề ngẫu nhiên có ràng buộc.
* **🔄 Hệ Thống Flashcard Leitner Tương Tác:** Ôn tập các câu sai theo đường cong quên lãng với giao diện phản hồi tức thì.
* **🔔 Thông Báo Realtime (WebSockets):** Nhận thông báo đẩy ngay trên màn hình khi hệ thống AI hoàn tất biên soạn đề thi chạy nền.

---

## 4. Công Nghệ & Kiến Trúc (Tech Stack)

| Thành Phần | Công Nghệ / Thư Viện | Mục Đích Sử Dụng |
| :--- | :--- | :--- |
| **Backend** | Python 3.11+, Django 5.0 | Khung ứng dụng web chính |
| **Database** | PostgreSQL 16+ | CSDL quan hệ chính (GIN Trigram Index & FTS) |
| **Task Queue** | Celery 5.3+, Redis 7.4+ | Xử lý các tác vụ AI và đọc file chạy nền |
| **Cache Backend** | Django RedisCache | Cache-Aside thống kê và Token Bucket |
| **Realtime** | Django Channels, Daphne | Giao tiếp WebSockets hai chiều |
| **AI Engine** | Google GenAI SDK (`gemini-2.5-flash`) | Mô hình AI sinh câu hỏi trắc nghiệm |
| **Document Engine** | PyPDF2, python-docx, WeasyPrint | Bóc tách văn bản và xuất bản Word/PDF |
| **Frontend** | Bootstrap 5, Bootstrap Icons, SweetAlert2 | Giao diện Responsive hiện đại |

---

## 5. Cấu Trúc Thư Mục (Directory Structure)

```
ai_exam_system_demo/
├── apps/
│   ├── core/                  # Dashboard, Cache-Aside Manager, Security (Token Bucket)
│   ├── documents/             # Upload, trích xuất text PDF/Docx, quản lý tài liệu
│   ├── quizzes/               # Quản lý Quiz, Question, ReviewCard (Leitner), Shuffler, AI Generator
│   │   ├── services/          # ai_generator, text_processor, shuffler, grading, leitner
│   │   ├── tasks.py           # Celery background tasks
│   │   └── views.py           # Quiz & Spaced Repetition views
│   ├── exports/               # Xuất bản Word (.docx) & PDF (.pdf) với Constrained Shuffling
│   └── users/                 # Custom User Model, Authentication, Profile Aggregation
├── config/                    # Cấu hình dự án (settings, urls, asgi, wsgi, celery)
├── static/                    # CSS, JavaScript, Static Assets
├── templates/                 # Giao diện HTML (Django Templates)
│   ├── core/                  # dashboard.html, home.html
│   ├── documents/             # upload.html, detail.html, list.html
│   ├── quizzes/               # create.html, detail.html, quiz_take.html, spaced_repetition.html, review_session.html
│   └── users/                 # login.html, register.html, profile.html
├── requirements.txt           # Danh sách các gói thư viện
└── manage.py                  # Django Management Script
```

---

## 6. Hướng Dẫn Cài Đặt & Khởi Chạy (Installation & Setup)

### Yêu Cầu Môi Trường (Prerequisites)
* **Python 3.11+**
* **PostgreSQL 14+** (đã cài đặt và đang chạy)
* **Redis Server 6.0+** (đang chạy ở cổng mặc định `6379`)

---

### Bước 1: Clone Mã Nguồn
```bash
git clone https://github.com/minhtue175/ai_exam_system.git
cd ai_exam_system
```

### Bước 2: Khởi Tạo Môi Trường Ảo (Virtualenv)
* **Trên Windows:**
```bash
python -m venv venv
venv\Scripts\activate
```
* **Trên Linux / macOS:**
```bash
python3 -m venv venv
source venv/bin/activate
```

### Bước 3: Cài Đặt Các Thư Viện Phụ Thuộc
```bash
pip install -r requirements.txt
```

### Bước 4: Thiết Lập Biến Môi Trường (`.env`)
Tạo file `.env` tại thư mục gốc của dự án với nội dung mẫu:
```env
# Django Secret Key & Debug Mode
SECRET_KEY=your-django-super-secret-key-change-in-production
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1

# PostgreSQL Database Configuration
DB_NAME=fluesy_db
DB_USER=postgres
DB_PASSWORD=your_postgres_password
DB_HOST=localhost
DB_PORT=5432

# Redis & Celery Configuration
CELERY_BROKER_URL=redis://127.0.0.1:6379/0
REDIS_CACHE_URL=redis://127.0.0.1:6379/1

# Google Gemini API Key
GEMINI_API_KEY=your_gemini_api_key_here
```

### Bước 5: Thực Thi Migrations & Tạo Tài Khoản Admin
```bash
python manage.py migrate
python manage.py createsuperuser
```

### Bước 6: Khởi Chạy Hệ Thống

Mở **3 cửa sổ Terminal riêng biệt** (đều đã kích hoạt môi trường ảo `venv`):

* **Terminal 1: Khởi chạy Celery Worker (xử lý nền tác vụ AI)**
```bash
# Trên Windows:
celery -A config worker -l info --pool=solo

# Trên Linux / macOS:
celery -A config worker -l info
```

* **Terminal 2: Khởi chạy máy chủ Django ASGI (hỗ trợ WebSockets & HTTP)**
```bash
python manage.py runserver
```

### Bước 7: Trải Nghiệm Ứng Dụng
* **Trang chủ & Dashboard:** `http://127.0.0.1:8000/`
* **Trang Quản trị Admin:** `http://127.0.0.1:8000/admin/`

---

<div align="center">
  <b>Phát triển với ❤️ vì mục tiêu nâng cao trải nghiệm học tập và ôn thi thông minh.</b>
</div>
