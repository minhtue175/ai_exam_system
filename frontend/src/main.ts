import { themeManager } from './modules/theme-manager';
import { notificationClient } from './modules/notification-socket';
import { QuizEngine } from './modules/quiz-engine';
import { LeitnerReviewEngine } from './modules/leitner-system';
import { ReviewCardItem } from './types';

export * from './types';
export * from './modules/theme-manager';
export * from './modules/notification-socket';
export * from './modules/quiz-engine';
export * from './modules/leitner-system';

// Khởi tạo các module toàn cục
if (typeof document !== 'undefined') {
  const initApp = () => {
    themeManager.init();

    // Tự động kết nối WebSocket nếu phát hiện phiên người dùng
    const userElement = document.querySelector('[data-user-authenticated="true"]') || document.querySelector('.left-sidebar');
    if (userElement) {
      notificationClient.connect();
    }

    // Tự động kích hoạt Quiz Engine nếu đang ở trang làm bài thi
    const quizForm = document.getElementById('quizForm') as HTMLFormElement | null;
    if (quizForm) {
      const durationSeconds = parseInt(quizForm.dataset.duration || '0', 10);
      const quizId = parseInt(quizForm.dataset.quizId || '0', 10);
      const engine = new QuizEngine({
        quizId,
        durationSeconds,
      });
      engine.init();
      (window as unknown as { quizEngine: QuizEngine }).quizEngine = engine;
    }

    // Tự động kích hoạt Leitner Review Engine nếu ở trang Flashcard session
    const flashcardEl = document.getElementById('flashcardContainer');
    const cardsDataScript = document.getElementById('cardsDataJson');
    if (flashcardEl && cardsDataScript) {
      try {
        const cardsData = JSON.parse(cardsDataScript.textContent || '[]') as ReviewCardItem[];
        const submitUrl = flashcardEl.dataset.submitUrl || '/quizzes/review/submit/';
        const reviewEngine = new LeitnerReviewEngine(cardsData, submitUrl);
        reviewEngine.init();
        (window as unknown as { reviewEngine: LeitnerReviewEngine }).reviewEngine = reviewEngine;
      } catch (e) {
        console.error('[Main] Lỗi parse cardsDataJson:', e);
      }
    }
  };

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initApp);
  } else {
    initApp();
  }
}

console.log('🎓 Fluesy Exam Frontend Toolchain Initialized with TypeScript & Vite');
