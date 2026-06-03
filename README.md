# 🎓 Hệ thống Lưu trữ Tài liệu và Tự động Tạo Đề thi bằng AI

### 📝 Mô tả dự án
Một hệ thống web hiện đại được xây dựng trên nền tảng **Django**, cho phép người dùng quản lý tài liệu lưu trữ tập trung và ứng dụng sức mạnh của **Gemini AI** để tự động biên soạn các bộ đề thi trắc nghiệm chất lượng cao. Dự án hướng tới sự tinh gọn, tối ưu hóa hiệu suất và nâng cao trải nghiệm người dùng với giao diện sáng sủa, hiện đại.

### 🚀 Tính năng nổi bật
* **Lưu trữ tài liệu tinh gọn:** Upload và quản lý các định dạng tài liệu (PDF, Word). Hệ thống tập trung hoàn toàn vào việc lưu trữ file vật lý trực tiếp, tối giản hóa quản lý thư mục nhằm tiết kiệm tài nguyên hệ thống và tối ưu tốc độ truy xuất.
* **Xử lý PDF chuyên sâu:** Tích hợp bộ công cụ tự động đọc, bóc tách văn bản thô từ tài liệu và xuất kết quả đề thi ra định dạng PDF.
* **Tự động sinh đề thi (AI-Powered):** Ứng dụng kỹ thuật Prompt Engineering với Google Gemini AI để trích xuất ngữ cảnh, tạo câu hỏi trọng tâm, gài bẫy đáp án nhiễu hợp lý và giữ nguyên các thuật ngữ chuyên ngành.
* **Xử lý bất đồng bộ mượt mà:** Tích hợp hệ thống Background Tasks không gây "treo" giao diện khi hệ thống đang bóc tách file nặng và giao tiếp với AI.

### 🛠️ Công nghệ & Kiến trúc (Tech Stack)
* **Backend:** Python, Django
* **Cơ sở dữ liệu:** PostgreSQL
* **Message Broker & Task Queue:** Redis, Celery
* **Trí tuệ nhân tạo:** Google Gemini API (gemini-2.5-flash)
* **Xử lý Tài liệu (PDF/Report):** PyPDF2, ReportLab
* **UI/UX Design:** Figma (Bright Style)

---

### ⚙️ Hướng dẫn cài đặt (Installation & Setup)

**Yêu cầu môi trường (Prerequisites):**
* [Python 3.x](https://www.python.org/)
* Hệ quản trị CSDL [PostgreSQL](https://www.postgresql.org/)
* [Redis](https://redis.io/) (Đang chạy ở port mặc định 6379)

**Các bước khởi chạy hệ thống:**

**Bước 1: Clone mã nguồn về máy**
```bash
git clone [https://github.com/minhtue175/ai_exam_system.git](https://github.com/minhtue175/ai_exam_system.git)
cd ai_exam_system
```

**Bước 2: Cài đặt môi trường ảo và thư viện**
```bash
python -m venv venv

# Active môi trường ảo (Windows)
venv\Scripts\activate
# Active môi trường ảo (Mac/Linux)
source venv/bin/activate

# Cài đặt các thư viện cần thiết (Bao gồm Django, PyPDF2, ReportLab, Celery, Redis...)
pip install -r requirements.txt
```

**Bước 3: Cấu hình biến môi trường**
Tạo file `.env` ở thư mục gốc của dự án (ngang hàng với file `manage.py`) và điền thông tin:
```env
# Database Configuration (PostgreSQL)
POSTGRES_DB=tên_database_của_bạn
POSTGRES_USER=tên_user_của_bạn
POSTGRES_PASSWORD=mật_khẩu_db_của_bạn
POSTGRES_HOST=localhost
POSTGRES_PORT=5432

# Google Gemini API
GEMINI_API_KEY=điền_api_key_gemini_của_bạn_vào_đây
```

**Bước 4: Khởi tạo Cơ sở dữ liệu và Tạo Admin**
```bash
python manage.py migrate
python manage.py createsuperuser
```

**Bước 5: Khởi chạy hệ thống (Yêu cầu mở 2 Terminal riêng biệt)**

*Terminal 1: Chạy Server Django chính*
```bash
python manage.py runserver
```

*Terminal 2: Chạy tiến trình nền Celery (Nhớ active venv trước khi chạy)*
```bash
celery -A ai_exam_system worker -l info --pool=solo
```

**Bước 6: Trải nghiệm**
* Website chính: `http://localhost:8000`
* Giao diện quản trị (Admin): `http://localhost:8000/admin`
