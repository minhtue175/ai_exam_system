/**
 * Fluesy Exam - Interactive Quiz Examination Engine
 * Bộ máy quản lý phiên thi trắc nghiệm: Countdown Timer, Auto-save câu trả lời LocalStorage,
 * Cảnh báo thời gian khẩn cấp, phím tắt A/B/C/D, kiểm tra câu chưa trả lời trước khi nộp.
 * @file frontend/src/modules/quiz-engine.ts
 */

import { QuizSessionState } from '../types';

declare const Swal: {
  fire: (options: Record<string, unknown>) => Promise<{ isConfirmed: boolean }>;
};

declare const bootstrap: {
  Modal: {
    getInstance: (element: Element | null) => { hide: () => void } | null;
  };
};

export interface QuizEngineConfig {
  quizId: number;
  durationSeconds: number;
  formSelector?: string;
  timerDisplaySelector?: string;
  timeSpentInputSelector?: string;
  autoSaveDraft?: boolean;
}

export class QuizEngine {
  private config: QuizEngineConfig;
  private state: QuizSessionState;
  private timerInterval: number | null = null;
  private autoSubmitted = false;

  private formElement: HTMLFormElement | null = null;
  private timerDisplay: HTMLElement | null = null;
  private timerContainer: HTMLElement | null = null;
  private timerIcon: HTMLElement | null = null;
  private timeSpentInput: HTMLInputElement | null = null;

  constructor(config: QuizEngineConfig) {
    this.config = {
      formSelector: '#quizForm',
      timerDisplaySelector: '#timerDisplay',
      timeSpentInputSelector: '#timeSpentInput',
      autoSaveDraft: true,
      ...config,
    };

    const now = Date.now();
    this.state = {
      quizId: this.config.quizId,
      currentQuestionIndex: 0,
      answers: {},
      remainingSeconds: this.config.durationSeconds,
      isSubmitted: false,
      startedAt: now,
      lastSavedAt: now,
    };
  }

  /**
   * Khởi tạo bộ máy thi và gắn toàn bộ listener
   */
  public init(): void {
    this.formElement = document.querySelector<HTMLFormElement>(this.config.formSelector || '#quizForm');
    this.timerDisplay = document.querySelector<HTMLElement>(this.config.timerDisplaySelector || '#timerDisplay');
    this.timerContainer = document.getElementById('timerContainer');
    this.timerIcon = document.getElementById('timerIcon');
    this.timeSpentInput = document.querySelector<HTMLInputElement>(this.config.timeSpentInputSelector || '#timeSpentInput');

    if (!this.formElement) {
      console.warn('[QuizEngine] Không tìm thấy Form đề thi để khởi chạy.');
      return;
    }

    console.log(`[QuizEngine] Khởi động đề thi ID #${this.config.quizId} (Thời lượng: ${this.config.durationSeconds}s)`);

    this.restoreDraftAnswers();
    this.bindOptionSelectionEvents();
    this.bindSubmissionEvents();
    this.bindKeyboardShortcuts();
    this.startTimer();
  }

  /**
   * Khởi chạy đồng hồ đếm ngược / đếm xuôi
   */
  private startTimer(): void {
    this.updateTimerTick();
    this.timerInterval = window.setInterval(() => {
      this.updateTimerTick();
    }, 1000);
  }

  private updateTimerTick(): void {
    const elapsedSeconds = Math.max(0, Math.floor((Date.now() - this.state.startedAt) / 1000));
    if (this.timeSpentInput) {
      this.timeSpentInput.value = String(elapsedSeconds);
    }

    if (this.config.durationSeconds > 0) {
      const remaining = this.config.durationSeconds - elapsedSeconds;
      this.state.remainingSeconds = remaining;

      if (remaining <= 0) {
        this.handleTimeExpired();
        return;
      }

      if (this.timerDisplay) {
        this.timerDisplay.textContent = this.formatTime(remaining);
      }

      this.updateUrgencyVisuals(remaining);
    } else {
      // Đề thi không giới hạn giờ -> Đếm tiến
      if (this.timerDisplay) {
        this.timerDisplay.textContent = this.formatTime(elapsedSeconds);
      }
    }
  }

  /**
   * Cập nhật màu sắc và hiệu ứng nhịp tim (pulse) khi sắp hết thời gian
   */
  private updateUrgencyVisuals(remaining: number): void {
    if (!this.timerContainer || !this.timerDisplay) return;

    if (remaining <= 60) {
      this.timerContainer.classList.remove('bg-white', 'text-dark');
      this.timerContainer.classList.add('bg-danger', 'text-white', 'pulse-warning');
      if (this.timerIcon) {
        this.timerIcon.classList.remove('text-primary');
        this.timerIcon.classList.add('text-white');
      }
      this.timerDisplay.classList.remove('text-primary', 'text-warning');
      this.timerDisplay.classList.add('text-white');

      // Tích tắc âm thanh cảnh báo ở 10 giây cuối cùng
      if (remaining <= 10) {
        this.playTickSound();
      }
    } else if (remaining <= 180) {
      // Dưới 3 phút: số màu cam
      this.timerDisplay.classList.remove('text-primary');
      this.timerDisplay.classList.add('text-warning');
    }
  }

  private handleTimeExpired(): void {
    if (this.timerInterval) {
      window.clearInterval(this.timerInterval);
      this.timerInterval = null;
    }

    if (this.timerDisplay) {
      this.timerDisplay.textContent = '00:00';
    }
    if (this.timeSpentInput) {
      this.timeSpentInput.value = String(this.config.durationSeconds);
    }

    if (this.autoSubmitted) return;
    this.autoSubmitted = true;
    this.state.isSubmitted = true;

    // Ẩn modal xác nhận nếu đang mở
    const submitModalEl = document.getElementById('confirmSubmitModal');
    if (submitModalEl && typeof bootstrap !== 'undefined') {
      const modalInstance = bootstrap.Modal.getInstance(submitModalEl);
      modalInstance?.hide();
    }

    if (typeof Swal !== 'undefined') {
      Swal.fire({
        title: 'Hết giờ làm bài! ⏰',
        text: 'Thời gian thi đã kết thúc. Hệ thống đang tự động nộp bài và chấm điểm...',
        icon: 'warning',
        allowOutsideClick: false,
        showConfirmButton: false,
        timer: 2000,
      });
    }

    setTimeout(() => {
      this.clearDraftAnswers();
      this.formElement?.submit();
    }, 1800);
  }

  /**
   * Lắng nghe người dùng click chọn phương án và tự động lưu nháp
   */
  private bindOptionSelectionEvents(): void {
    const radioInputs = this.formElement?.querySelectorAll<HTMLInputElement>('input[type="radio"]') || [];
    radioInputs.forEach((input) => {
      input.addEventListener('change', () => {
        const questionMatch = input.name.match(/question_(\d+)/);
        if (questionMatch) {
          const questionId = parseInt(questionMatch[1], 10);
          const optionIndex = parseInt(input.value, 10);
          this.state.answers[questionId] = optionIndex;
          this.saveDraftAnswers();
          this.highlightSelectedOptionRow(input);
        }
      });
    });
  }

  /**
   * Tạo hiệu ứng viền nổi bật cho phương án được chọn
   */
  private highlightSelectedOptionRow(selectedRadio: HTMLInputElement): void {
    const parentQuestion = selectedRadio.closest('.card-custom');
    if (!parentQuestion) return;

    const allOptions = parentQuestion.querySelectorAll<HTMLElement>('.option-hover');
    allOptions.forEach((opt) => opt.classList.remove('border-primary', 'bg-light'));

    const currentOptionRow = selectedRadio.closest<HTMLElement>('.option-hover');
    if (currentOptionRow) {
      currentOptionRow.classList.add('border-primary', 'bg-light');
    }
  }

  /**
   * Lưu nháp câu trả lời vào LocalStorage
   */
  private saveDraftAnswers(): void {
    if (!this.config.autoSaveDraft) return;
    try {
      const key = `fluesy_quiz_draft_${this.config.quizId}`;
      localStorage.setItem(key, JSON.stringify(this.state.answers));
    } catch {
      // Bỏ qua nếu storage đầy
    }
  }

  /**
   * Khôi phục nháp nếu người dùng lỡ tay bấm F5 / Reload
   */
  private restoreDraftAnswers(): void {
    if (!this.config.autoSaveDraft) return;
    try {
      const key = `fluesy_quiz_draft_${this.config.quizId}`;
      const raw = localStorage.getItem(key);
      if (!raw) return;

      const restored = JSON.parse(raw) as Record<number, number>;
      this.state.answers = restored;

      Object.entries(restored).forEach(([qId, optIdx]) => {
        const radio = this.formElement?.querySelector<HTMLInputElement>(
          `input[name="question_${qId}"][value="${optIdx}"]`
        );
        if (radio) {
          radio.checked = true;
          this.highlightSelectedOptionRow(radio);
        }
      });
      console.log(`[QuizEngine] Đã khôi phục thành công ${Object.keys(restored).length} câu trả lời từ bản nháp!`);
    } catch {
      // Bỏ qua nếu parse JSON lỗi
    }
  }

  public clearDraftAnswers(): void {
    try {
      localStorage.removeItem(`fluesy_quiz_draft_${this.config.quizId}`);
    } catch {
      // Ignored
    }
  }

  /**
   * Nộp bài thủ công
   */
  private bindSubmissionEvents(): void {
    const realSubmitBtn = document.getElementById('realSubmitBtn');
    if (realSubmitBtn) {
      realSubmitBtn.addEventListener('click', () => {
        if (this.timerInterval) {
          window.clearInterval(this.timerInterval);
        }
        const timeSpent = Math.max(1, Math.floor((Date.now() - this.state.startedAt) / 1000));
        if (this.timeSpentInput) {
          this.timeSpentInput.value = String(timeSpent);
        }

        realSubmitBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span> Đang chấm điểm...';
        realSubmitBtn.classList.add('disabled');
        realSubmitBtn.style.pointerEvents = 'none';

        const closeBtn = document.getElementById('closeModalBtn');
        if (closeBtn) {
          closeBtn.style.display = 'none';
        }

        this.clearDraftAnswers();
        this.formElement?.submit();
      });
    }
  }

  /**
   * Phím tắt A, B, C, D (hoặc 1, 2, 3, 4) cho câu hỏi đang focus
   */
  private bindKeyboardShortcuts(): void {
    window.addEventListener('keydown', (e) => {
      // Chỉ kích hoạt nếu không gõ trong ô input/textarea
      if (['INPUT', 'TEXTAREA'].includes((e.target as HTMLElement)?.tagName)) {
        return;
      }

      const key = e.key.toUpperCase();
      const optionMap: Record<string, number> = {
        'A': 0, '1': 0,
        'B': 1, '2': 1,
        'C': 2, '3': 2,
        'D': 3, '4': 3,
      };

      if (key in optionMap) {
        // Tìm câu hỏi gần vị trí cuộn chuột nhất
        const questions = Array.from(document.querySelectorAll<HTMLElement>('.card-custom[id^="question_card_"]'));
        const activeQuestion = questions.find((card) => {
          const rect = card.getBoundingClientRect();
          return rect.top >= 50 && rect.top <= window.innerHeight / 2;
        }) || questions[0];

        if (activeQuestion) {
          const targetRadio = activeQuestion.querySelectorAll<HTMLInputElement>('input[type="radio"]')[optionMap[key]];
          if (targetRadio) {
            targetRadio.checked = true;
            targetRadio.dispatchEvent(new Event('change'));
          }
        }
      }
    });
  }

  private playTickSound(): void {
    try {
      const AudioCtx = window.AudioContext || (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
      if (!AudioCtx) return;
      const ctx = new AudioCtx();
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      osc.connect(gain);
      gain.connect(ctx.destination);
      osc.frequency.setValueAtTime(800, ctx.currentTime);
      gain.gain.setValueAtTime(0.05, ctx.currentTime);
      gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.05);
      osc.start(ctx.currentTime);
      osc.stop(ctx.currentTime + 0.05);
    } catch {
      // Ignored
    }
  }

  private formatTime(totalSec: number): string {
    const mins = Math.floor(totalSec / 60);
    const secs = totalSec % 60;
    return `${String(mins).padStart(2, '0')}:${String(secs).padStart(2, '0')}`;
  }
}
