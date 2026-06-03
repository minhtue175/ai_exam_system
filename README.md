# 🎓 Hệ thống Lưu trữ Tài liệu và Tự động Tạo Đề thi bằng AI

### 📝 Mô tả dự án
Một hệ thống web hiện đại được xây dựng trên nền tảng **Django**, cho phép người dùng quản lý tài liệu lưu trữ và ứng dụng sức mạnh của **Gemini AI** để tự động biên soạn các bộ đề thi trắc nghiệm chất lượng cao. Hệ thống được thiết kế với kiến trúc chịu tải tốt, tích hợp xử lý tác vụ nền bất đồng bộ giúp tối ưu hóa hiệu năng và trải nghiệm người dùng.

### 🚀 Tính năng nổi bật
* **Quản lý tài liệu thông minh:** Upload và lưu trữ an toàn các định dạng tài liệu (PDF, Word) bằng cách tách biệt file vật lý và cơ sở dữ liệu.
* **Tự động sinh đề thi (AI-Powered):** Ứng dụng kỹ thuật Prompt Engineering với Google Gemini AI để trích xuất ngữ cảnh, tạo câu hỏi trọng tâm, gài bẫy đáp án nhiễu hợp lý và giữ nguyên thuật ngữ chuyên ngành.
* **Xử lý bất đồng bộ mượt mà:** Tích hợp hệ thống Background Tasks bằng Celery không gây "treo" giao diện khi AI đang xử lý văn bản nặng.
* **Môi trường nhất quán:** Đóng gói toàn bộ hệ thống bằng Container để đảm bảo chạy mượt trên mọi thiết bị.

### 🛠️ Công nghệ & Kiến trúc (Tech Stack)
* **Backend:** Python, Django
* **Cơ sở dữ liệu:** PostgreSQL (quản lý qua pgAdmin)
* **Message Broker & Task Queue:** Redis, Celery
* **Trí tuệ nhân tạo:** Google Gemini API (gemini-2.5-flash)
* **Đóng gói & Triển khai:** Docker, Docker Compose
* **UI/UX Design:** Figma

---

### ⚙️ Hướng dẫn cài đặt (Installation & Setup)

**Yêu cầu môi trường (Prerequisites):**
* Máy tính đã cài đặt [Git](https://git-scm.com/)
* Máy tính đã cài đặt [Docker](https://www.docker.com/) và **Docker Compose**

**Các bước khởi chạy hệ thống:**

**Bước 1: Clone mã nguồn về máy**
Mở Terminal/Command Prompt và chạy lệnh:
```bash
git clone https://github.com/minhtue175/ai_exam_system.git
cd ai_exam_system
```

**Bước 2: Cấu hình biến môi trường**
Tạo một file có tên là `.env` ở thư mục gốc của dự án và điền các thông tin bảo mật vào:
```env
# Database Configuration (PostgreSQL)
POSTGRES_DB=tên_database_của_bạn
POSTGRES_USER=tên_user_của_bạn
POSTGRES_PASSWORD=mật_khẩu_db_của_bạn

# Google Gemini API
GEMINI_API_KEY=điền_api_key_gemini_của_bạn_vào_đây
```

**Bước 3: Đóng gói và khởi động hệ thống**
Chỉ cần 1 câu lệnh duy nhất để Docker tự động build và liên kết 4 dịch vụ (Django, PostgreSQL, Redis, Celery):
```bash
docker-compose up -d --build
```

**Bước 4: Khởi tạo Cơ sở dữ liệu và Tạo Admin**
Sau khi các container đã chạy thành công, tiến hành tạo các bảng dữ liệu và tài khoản quản trị:
```bash
# Chạy migrations để đồng bộ Database
docker-compose exec web python manage.py migrate

# Tạo tài khoản Admin
docker-compose exec web python manage.py createsuperuser
```

**Bước 5: Trải nghiệm**
* Website chính: `http://localhost:8000`
* Giao diện quản trị (Admin): `http://localhost:8000/admin`

---
*Lưu ý: Để dừng toàn bộ hệ thống, sử dụng lệnh `docker-compose down`.*
