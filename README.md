                                          Hệ thống Lưu trữ Tài liệu và Tự động Tạo Đề thi bằng AI

📝 Mô tả dự án
Một hệ thống web hiện đại được xây dựng trên nền tảng Django, cho phép người dùng quản lý tài liệu lưu trữ và ứng dụng sức mạnh của Gemini AI để tự động biên soạn các bộ đề thi trắc nghiệm chất lượng cao. Hệ thống được thiết kế với kiến trúc chịu tải tốt, tích hợp xử lý tác vụ nền bất đồng bộ giúp tối ưu hóa hiệu năng và trải nghiệm người dùng.

🚀 Tính năng nổi bật
Quản lý tài liệu thông minh: Upload và lưu trữ an toàn các định dạng tài liệu (PDF, Word) bằng cách tách biệt file vật lý và cơ sở dữ liệu.

Tự động sinh đề thi (AI-Powered): Ứng dụng kỹ thuật Prompt Engineering với Google Gemini AI để trích xuất ngữ cảnh, tạo câu hỏi trọng tâm, gài bẫy đáp án nhiễu hợp lý và giữ nguyên thuật ngữ chuyên ngành.

Xử lý bất đồng bộ mượt mà: Tích hợp hệ thống Background Tasks không gây "treo" giao diện khi AI đang xử lý văn bản nặng.

Môi trường nhất quán: Đóng gói toàn bộ hệ thống bằng Container để triển khai nhanh chóng.

🛠️ Công nghệ & Kiến trúc (Tech Stack)
Backend: Python, Django

Cơ sở dữ liệu: PostgreSQL (quản lý qua pgAdmin)

Message Broker & Task Queue: Redis, Celery

Trí tuệ nhân tạo: Google Gemini API (gemini-2.5-flash)

Đóng gói & Triển khai: Docker, Docker Compose

UI/UX Design: Thiết kế hiện đại, sáng sủa (Bright Style) với Figma
