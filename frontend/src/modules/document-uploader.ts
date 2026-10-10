/**
 * Fluesy Exam - Document Uploader & AI Generation Configuration Module
 * Quản lý kéo thả Upload tài liệu (Drag & Drop), kiểm tra định dạng và dung lượng phía client,
 * xử lý sao chép văn bản trích xuất, và cập nhật phân loại tư duy Bloom's Taxonomy khi sinh đề AI.
 * @file frontend/src/modules/document-uploader.ts
 */

import { QuizDifficulty } from '../types';

declare const Swal: {
  fire: (options: Record<string, unknown>) => Promise<{ isConfirmed: boolean }>;
};

export interface BloomInfo {
  title: string;
  desc: string;
  icon: string;
}

export const BLOOM_TAXONOMY_MAP: Record<QuizDifficulty, BloomInfo> = {
  remember: {
    title: 'Cấp 1: Nhớ (Remember) — Nhắc lại kiến thức',
    desc: 'AI sẽ tập trung vào các câu hỏi yêu cầu nhắc lại định nghĩa, công thức, thuật ngữ và sự kiện chính có trong tài liệu.',
    icon: 'bi-bookmark-check-fill',
  },
  understand: {
    title: 'Cấp 2: Hiểu (Understand) — Giải thích ý nghĩa',
    desc: 'AI sẽ đặt câu hỏi yêu cầu giải thích bản chất khái niệm, so sánh đối chiếu và diễn giải nguyên lý hoạt động.',
    icon: 'bi-lightbulb-fill',
  },
  apply: {
    title: 'Cấp 3: Áp dụng (Apply) — Vận dụng thực tế',
    desc: 'AI sẽ xây dựng các tình huống giả định hoặc bài toán cụ thể để kiểm tra khả năng áp dụng kiến thức vào thực tiễn.',
    icon: 'bi-tools',
  },
  analyze: {
    title: 'Cấp 4: Phân tích (Analyze) — Phân tích mối quan hệ',
    desc: 'AI sẽ tạo các câu hỏi đào sâu nguyên nhân - kết quả, phân biệt cấu trúc và nhận diện các yếu tố cốt lõi.',
    icon: 'bi-diagram-3-fill',
  },
  evaluate: {
    title: 'Cấp 5: Đánh giá (Evaluate) — Phán đoán & Tiêu chí',
    desc: 'AI sẽ yêu cầu đánh giá ưu/nhược điểm, nhận định giải pháp tối ưu và phản biện dựa trên tiêu chuẩn cụ thể.',
    icon: 'bi-shield-check',
  },
  create: {
    title: 'Cấp 6: Sáng tạo (Create) — Đề xuất giải pháp',
    desc: 'AI sẽ đưa ra bối cảnh mới đòi hỏi tổng hợp kiến thức từ nhiều phần để thiết kế, đề xuất phương án cải tiến.',
    icon: 'bi-stars',
  },
  basic: {
    title: 'Cơ Bản (Tổng hợp Nhớ & Hiểu)',
    desc: 'Câu hỏi trực quan, đi thẳng vào các khái niệm nền tảng dành cho ôn tập đại cương.',
    icon: 'bi-check2-circle',
  },
  advanced: {
    title: 'Nâng Cao (Tổng hợp Áp dụng & Phân tích)',
    desc: 'Câu hỏi phân tích tình huống nâng cao và đào sâu tư duy phản biện.',
    icon: 'bi-lightning-charge-fill',
  },
};

export class DocumentUploadManager {
  private static instance: DocumentUploadManager;
  private readonly maxFileSizeBytes = 20 * 1024 * 1024; // 20MB
  private readonly allowedExtensions = ['.pdf', '.docx', '.doc', '.txt'];

  private constructor() {}

  public static getInstance(): DocumentUploadManager {
    if (!DocumentUploadManager.instance) {
      DocumentUploadManager.instance = new DocumentUploadManager();
    }
    return DocumentUploadManager.instance;
  }

  /**
   * Khởi tạo tính năng cập nhật thông tin Bloom Taxonomy trên form tạo đề AI
   */
  public initBloomSelector(selectId = 'id_difficulty'): void {
    const selectEl = document.getElementById(selectId) as HTMLSelectElement | null;
    if (!selectEl) return;

    const updateDisplay = () => {
      const val = selectEl.value as QuizDifficulty;
      const info = BLOOM_TAXONOMY_MAP[val] || BLOOM_TAXONOMY_MAP['remember'];

      const titleEl = document.getElementById('bloomLevelTitle');
      if (titleEl) {
        titleEl.innerHTML = `<i class="bi ${info.icon} me-1 text-primary"></i> ${info.title}`;
      }

      const descEl = document.getElementById('bloomLevelDesc');
      if (descEl) {
        descEl.innerText = info.desc;
      }
    };

    updateDisplay();
    selectEl.addEventListener('change', updateDisplay);

    // Xử lý chống submit trùng lặp
    const form = selectEl.closest('form');
    if (form) {
      form.addEventListener('submit', (e) => {
        const submitBtn = form.querySelector('button[type="submit"]') as HTMLButtonElement | null;
        if (submitBtn) {
          form.classList.add('submitting');
          submitBtn.disabled = true;
          submitBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span> AI đang phân tích tài liệu...';
        }
      });
    }
  }

  /**
   * Khởi tạo vùng kéo thả tệp (Drag and Drop Zone)
   */
  public initDropzone(dropzoneId = 'dropZone', fileInputId = 'fileInput'): void {
    const dropzone = document.getElementById(dropzoneId);
    const fileInput = document.getElementById(fileInputId) as HTMLInputElement | null;
    if (!dropzone || !fileInput) return;

    ['dragenter', 'dragover'].forEach((eventName) => {
      dropzone.addEventListener(eventName, (e) => {
        e.preventDefault();
        e.stopPropagation();
        dropzone.classList.add('border-primary', 'bg-light');
      });
    });

    ['dragleave', 'drop'].forEach((eventName) => {
      dropzone.addEventListener(eventName, (e) => {
        e.preventDefault();
        e.stopPropagation();
        dropzone.classList.remove('border-primary', 'bg-light');
      });
    });

    dropzone.addEventListener('drop', (e) => {
      const dt = (e as DragEvent).dataTransfer;
      if (dt && dt.files.length > 0) {
        const file = dt.files[0];
        if (this.validateFile(file)) {
          fileInput.files = dt.files;
          this.updateFileNamePreview(file.name);
        }
      }
    });

    fileInput.addEventListener('change', () => {
      if (fileInput.files && fileInput.files.length > 0) {
        const file = fileInput.files[0];
        if (this.validateFile(file)) {
          this.updateFileNamePreview(file.name);
        } else {
          fileInput.value = '';
        }
      }
    });
  }

  private validateFile(file: File): boolean {
    const ext = '.' + file.name.split('.').pop()?.toLowerCase();
    if (!this.allowedExtensions.includes(ext)) {
      if (typeof Swal !== 'undefined') {
        Swal.fire({
          title: 'Định dạng không hỗ trợ',
          text: `Hệ thống chỉ hỗ trợ ${this.allowedExtensions.join(', ')}. Tệp của bạn là: ${ext}`,
          icon: 'error',
          confirmButtonText: 'Đã hiểu',
          confirmButtonColor: '#dc3545',
        });
      } else {
        alert(`Định dạng không hỗ trợ! Vui lòng chọn ${this.allowedExtensions.join(', ')}`);
      }
      return false;
    }

    if (file.size > this.maxFileSizeBytes) {
      const sizeMB = (file.size / (1024 * 1024)).toFixed(1);
      if (typeof Swal !== 'undefined') {
        Swal.fire({
          title: 'Tệp quá lớn',
          text: `Dung lượng tệp (${sizeMB} MB) vượt quá giới hạn cho phép (20 MB).`,
          icon: 'warning',
          confirmButtonText: 'Đã hiểu',
          confirmButtonColor: '#ffc107',
        });
      } else {
        alert(`Tệp quá lớn (${sizeMB}MB)! Vui lòng chọn tệp dưới 20MB.`);
      }
      return false;
    }

    return true;
  }

  private updateFileNamePreview(fileName: string): void {
    const preview = document.getElementById('selectedFileNamePreview');
    if (preview) {
      preview.innerText = `📄 Tệp đã chọn: ${fileName}`;
      preview.classList.remove('d-none');
    }
  }

  /**
   * Sao chép toàn bộ văn bản trích xuất vào Clipboard kèm thông báo Toast
   */
  public copyExtractedText(textSelector = 'pre'): void {
    const textEl = document.querySelector<HTMLElement>(textSelector);
    if (!textEl) return;

    const text = textEl.innerText;
    navigator.clipboard.writeText(text).then(() => {
      if (typeof Swal !== 'undefined') {
        Swal.fire({
          toast: true,
          position: 'top-end',
          icon: 'success',
          title: 'Đã sao chép vào bộ nhớ tạm!',
          showConfirmButton: false,
          timer: 3000,
          timerProgressBar: true,
        });
      } else {
        alert('Đã copy vào clipboard!');
      }
    });
  }
}

export const documentUploadManager = DocumentUploadManager.getInstance();
