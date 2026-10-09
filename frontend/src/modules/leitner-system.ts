/**
 * Fluesy Exam - Spaced Repetition (Leitner System) Review Engine
 * Module quản lý phiên ôn tập ngắt quãng: Render flashcards, xử lý trả lời và thăng/giáng cấp ngăn Leitner,
 * phím tắt 1-4 & Space, thống kê tổng kết phiên học.
 * @file frontend/src/modules/leitner-system.ts
 */

import { ReviewCardItem, LeitnerBoxLevel, LeitnerSessionState } from '../types';

export interface LeitnerSubmitResult {
  is_correct: boolean;
  old_box: LeitnerBoxLevel;
  new_box: LeitnerBoxLevel;
  interval_display: string;
  is_mastered: boolean;
  explanation: string;
  correct_answer_index: number;
}

export interface LeitnerApiResponse {
  success: boolean;
  result: LeitnerSubmitResult;
  error?: string;
}

export class LeitnerReviewEngine {
  private cards: ReviewCardItem[] = [];
  private state: LeitnerSessionState;
  private submitEndpoint: string;
  private csrfToken: string;
  private isProcessingAnswer = false;

  constructor(cards: ReviewCardItem[], submitUrl: string, csrfToken?: string) {
    this.cards = cards;
    this.submitEndpoint = submitUrl;
    this.csrfToken = csrfToken || this.getCookie('csrftoken') || '';

    this.state = {
      currentCardIndex: 0,
      cards: this.cards,
      isFlipped: false,
      reviewedCardsCount: 0,
      correctCount: 0,
      incorrectCount: 0,
      startTime: Date.now(),
    };
  }

  public init(): void {
    if (!this.cards || this.cards.length === 0) {
      console.warn('[LeitnerReviewEngine] Không có thẻ ôn tập nào trong phiên này.');
      return;
    }

    console.log(`[LeitnerReviewEngine] Khởi động phiên ôn tập với ${this.cards.length} thẻ.`);
    this.bindKeyboardShortcuts();
    this.bindNextButtonEvent();
    this.renderCard(0);
  }

  /**
   * Tạo Badge HTML cho từng cấp độ hộp Leitner (1 - 5)
   */
  public getBoxBadgeHTML(boxLevel: LeitnerBoxLevel): string {
    const badgeStyles: Record<LeitnerBoxLevel, { cls: string; name: string }> = {
      1: { cls: 'bg-danger-subtle text-danger', name: 'Ngăn 1 (Ghi nhớ tức thì)' },
      2: { cls: 'bg-warning-subtle text-warning', name: 'Ngăn 2 (Củng cố sơ cấp)' },
      3: { cls: 'bg-primary-subtle text-primary', name: 'Ngăn 3 (Nắm vững trung cấp)' },
      4: { cls: 'bg-info-subtle text-info', name: 'Ngăn 4 (Trí nhớ dài hạn)' },
      5: { cls: 'bg-success-subtle text-success', name: 'Ngăn 5 (Thành thạo tối đa)' },
    };

    const info = badgeStyles[boxLevel] || { cls: 'bg-secondary-subtle text-secondary', name: `Ngăn ${boxLevel}` };
    return `<span class="badge ${info.cls} px-3 py-2 rounded-pill fw-bold"><i class="bi bi-box me-1"></i>${info.name}</span>`;
  }

  /**
   * Hiển thị câu hỏi và các phương án của thẻ hiện tại
   */
  public renderCard(index: number): void {
    if (index >= this.cards.length) {
      this.showCompletionScreen();
      return;
    }

    this.state.currentCardIndex = index;
    this.isProcessingAnswer = false;
    const card = this.cards[index];

    // Cập nhật chỉ số tiến trình
    const progressText = document.getElementById('progressIndicator');
    if (progressText) {
      progressText.innerText = `${index + 1} / ${this.cards.length}`;
    }

    const progressBar = document.getElementById('sessionProgressBar');
    if (progressBar) {
      const percent = (index / this.cards.length) * 100;
      progressBar.style.width = `${percent}%`;
    }

    const boxBadgeEl = document.getElementById('boxBadge');
    if (boxBadgeEl) {
      boxBadgeEl.innerHTML = this.getBoxBadgeHTML(card.boxLevel);
    }

    const questionTitle = document.getElementById('questionTitle');
    if (questionTitle) {
      questionTitle.innerText = card.questionText;
    }

    // Ẩn bảng phản hồi kết quả và nút Next
    const feedbackAlert = document.getElementById('feedbackAlert');
    if (feedbackAlert) {
      feedbackAlert.className = 'p-4 rounded-3 d-none mb-3';
    }

    const nextActionWrapper = document.getElementById('nextActionWrapper');
    if (nextActionWrapper) {
      nextActionWrapper.classList.add('d-none');
    }

    // Render danh sách các nút phương án
    const container = document.getElementById('optionsContainer');
    if (container) {
      container.innerHTML = '';
      const letters = ['A', 'B', 'C', 'D'];

      card.options.forEach((optText, optIdx) => {
        const btn = document.createElement('button');
        btn.type = 'button';
        btn.className = 'option-btn w-100 text-start d-flex align-items-center mb-3 p-3';
        btn.innerHTML = `<span class="opt-badge me-3">${letters[optIdx]}</span><span>${optText}</span>`;
        btn.onclick = () => this.handleSelectAnswer(optIdx, btn);
        container.appendChild(btn);
      });
    }
  }

  /**
   * Xử lý nộp câu trả lời lên server và nhận kết quả thăng/hạ hộp Leitner
   */
  public async handleSelectAnswer(selectedIndex: number, buttonElement: HTMLButtonElement): Promise<void> {
    if (this.isProcessingAnswer) return;
    this.isProcessingAnswer = true;

    // Vô hiệu hóa toàn bộ buttons
    const allButtons = document.querySelectorAll<HTMLButtonElement>('.option-btn');
    allButtons.forEach((btn) => (btn.disabled = true));

    const currentCard = this.cards[this.state.currentCardIndex];

    try {
      const response = await fetch(this.submitEndpoint, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': this.csrfToken,
        },
        body: JSON.stringify({
          card_id: currentCard.id,
          selected_index: selectedIndex,
        }),
      });

      const data = (await response.json()) as LeitnerApiResponse;
      if (data.success) {
        this.renderAnswerFeedback(data.result, selectedIndex, buttonElement, allButtons);
      } else {
        alert(`Có lỗi xảy ra: ${data.error || 'Vui lòng thử lại'}`);
      }
    } catch (err) {
      console.error('[LeitnerReviewEngine] Lỗi gửi đáp án:', err);
      alert('Mất kết nối mạng khi nộp đáp án. Vui lòng thử lại!');
    }
  }

  private renderAnswerFeedback(
    res: LeitnerSubmitResult,
    selectedIndex: number,
    buttonElement: HTMLButtonElement,
    allButtons: NodeListOf<HTMLButtonElement>
  ): void {
    const isCorrect = res.is_correct;

    if (isCorrect) {
      this.state.correctCount++;
      buttonElement.classList.add('selected-correct');
    } else {
      this.state.incorrectCount++;
      buttonElement.classList.add('selected-wrong');
      // Highlight phương án đúng thực sự
      if (allButtons[res.correct_answer_index]) {
        allButtons[res.correct_answer_index].classList.add('selected-correct');
      }
    }

    const feedbackAlert = document.getElementById('feedbackAlert');
    const feedbackIcon = document.getElementById('feedbackIcon');
    const feedbackTitle = document.getElementById('feedbackTitle');
    const feedbackLeitner = document.getElementById('feedbackLeitnerAction');
    const feedbackExp = document.getElementById('feedbackExplanationText');

    if (feedbackAlert && feedbackIcon && feedbackTitle && feedbackLeitner && feedbackExp) {
      if (isCorrect) {
        feedbackAlert.className = 'p-4 rounded-3 mb-3 bg-success-subtle text-success border border-success';
        feedbackIcon.className = 'bi bi-check-circle-fill text-success fs-1';
        feedbackTitle.innerText = 'Chính xác! Xuất sắc!';
        if (res.is_mastered) {
          feedbackLeitner.innerText = `🎉 Câu hỏi đã đạt NGĂN 5 (Thành thạo) — Ôn lại sau ${res.interval_display}!`;
        } else {
          feedbackLeitner.innerText = `🚀 Thăng cấp: Ngăn ${res.old_box} ➔ Ngăn ${res.new_box} (Ôn lại sau ${res.interval_display})!`;
        }
      } else {
        feedbackAlert.className = 'p-4 rounded-3 mb-3 bg-danger-subtle text-danger border border-danger';
        feedbackIcon.className = 'bi bi-x-circle-fill text-danger fs-1';
        feedbackTitle.innerText = 'Chưa chính xác!';
        feedbackLeitner.innerText = `⚠️ Câu hỏi chuyển về Ngăn 1 (Ôn lại sau ${res.interval_display}) để củng cố trí nhớ.`;
      }

      feedbackExp.innerText = res.explanation || 'Không có giải thích chi tiết.';
      feedbackAlert.classList.remove('d-none');
    }

    // Hiển thị nút qua câu tiếp theo
    const nextActionWrapper = document.getElementById('nextActionWrapper');
    if (nextActionWrapper) {
      nextActionWrapper.classList.remove('d-none');
    }
  }

  private bindNextButtonEvent(): void {
    const nextBtn = document.getElementById('nextCardBtn');
    if (nextBtn) {
      nextBtn.addEventListener('click', () => {
        this.renderCard(this.state.currentCardIndex + 1);
      });
    }
  }

  private bindKeyboardShortcuts(): void {
    window.addEventListener('keydown', (e) => {
      // Nhấn Space hoặc Enter để qua câu tiếp theo nếu đã trả lời xong
      if ((e.code === 'Space' || e.key === 'Enter') && this.isProcessingAnswer) {
        const nextWrapper = document.getElementById('nextActionWrapper');
        if (nextWrapper && !nextWrapper.classList.contains('d-none')) {
          e.preventDefault();
          this.renderCard(this.state.currentCardIndex + 1);
          return;
        }
      }

      // Nhấn 1-4 hoặc A-D để chọn đáp án
      if (!this.isProcessingAnswer) {
        const keyMap: Record<string, number> = { '1': 0, '2': 1, '3': 2, '4': 3, 'A': 0, 'B': 1, 'C': 2, 'D': 3 };
        const key = e.key.toUpperCase();
        if (key in keyMap) {
          const btns = document.querySelectorAll<HTMLButtonElement>('.option-btn');
          const targetBtn = btns[keyMap[key]];
          if (targetBtn && !targetBtn.disabled) {
            e.preventDefault();
            this.handleSelectAnswer(keyMap[key], targetBtn);
          }
        }
      }
    });
  }

  /**
   * Màn hình hoàn thành phiên ôn tập
   */
  private showCompletionScreen(): void {
    const cardContainer = document.getElementById('flashcardContainer');
    if (cardContainer) {
      cardContainer.classList.add('d-none');
    }

    const completionEl = document.getElementById('completionScreen');
    if (completionEl) {
      completionEl.classList.remove('d-none');

      const correctCountEl = document.getElementById('summaryCorrectCount');
      if (correctCountEl) correctCountEl.innerText = String(this.state.correctCount);

      const wrongCountEl = document.getElementById('summaryWrongCount');
      if (wrongCountEl) wrongCountEl.innerText = String(this.state.incorrectCount);

      const totalCountEl = document.getElementById('summaryTotalCount');
      if (totalCountEl) totalCountEl.innerText = String(this.cards.length);
    }
  }

  private getCookie(name: string): string | null {
    let cookieValue: string | null = null;
    if (document.cookie && document.cookie !== '') {
      const cookies = document.cookie.split(';');
      for (let i = 0; i < cookies.length; i++) {
        const cookie = cookies[i].trim();
        if (cookie.substring(0, name.length + 1) === name + '=') {
          cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
          break;
        }
      }
    }
    return cookieValue;
  }
}
