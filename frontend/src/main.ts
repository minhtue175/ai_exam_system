import { themeManager } from './modules/theme-manager';
import { notificationClient } from './modules/notification-socket';
import { QuizEngine } from './modules/quiz-engine';
import { LeitnerReviewEngine } from './modules/leitner-system';
import { analyticsChartEngine } from './modules/analytics-chart';
import { documentUploadManager } from './modules/document-uploader';
import { ReviewCardItem, ScoreTrendDataPoint } from './types';

export * from './types';
export * from './modules/theme-manager';
export * from './modules/notification-socket';
export * from './modules/quiz-engine';
export * from './modules/leitner-system';
export * from './modules/analytics-chart';
export * from './modules/document-uploader';

// Khởi tạo các module toàn cục
if (typeof document !== 'undefined') {
  const initApp = () => {
    themeManager.init();

    // Tự động kết nối WebSocket nếu phát hiện phiên người dùng
    const userElement = document.querySelector('[data-user-authenticated="true"]') || document.querySelector('.left-sidebar');
    if (userElement) {
      notificationClient.connect();
    }

    // Tự động kích hoạt đồng hồ & chào hỏi trên Dashboard
    if (document.getElementById('realtime-clock')) {
      analyticsChartEngine.initClockAndGreeting();
    }

    // Tự động kích hoạt biểu đồ điểm số trên Dashboard nếu có canvas
    const scoreChartCanvas = document.getElementById('scoreChart');
    const scoreDataScript = document.getElementById('scoreChartDataJson');
    if (scoreChartCanvas && scoreDataScript) {
      try {
        const points = JSON.parse(scoreDataScript.textContent || '[]') as ScoreTrendDataPoint[];
        analyticsChartEngine.renderScoreTrendChart('scoreChart', points);
      } catch (e) {
        console.error('[Main] Lỗi parse scoreChartDataJson:', e);
      }
    }

    // Tự động kích hoạt Bloom's Taxonomy selector khi tạo đề thi AI
    if (document.getElementById('id_difficulty')) {
      documentUploadManager.initBloomSelector('id_difficulty');
    }

    // Tự động kích hoạt Drag and Drop Zone tải tài liệu
    if (document.getElementById('dropZone')) {
      documentUploadManager.initDropzone('dropZone', 'fileInput');
    }

    // Tự động gắn sự kiện nút copy văn bản trích xuất
    const copyBtn = document.getElementById('copyExtractedTextBtn');
    if (copyBtn) {
      copyBtn.addEventListener('click', () => {
        documentUploadManager.copyExtractedText('pre');
      });
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
