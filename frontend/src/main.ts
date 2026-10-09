import { themeManager } from './modules/theme-manager';

export * from './types';
export * from './modules/theme-manager';

// Tự động khởi tạo ThemeManager khi DOM tải xong
if (typeof document !== 'undefined') {
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
      themeManager.init();
    });
  } else {
    themeManager.init();
  }
}

console.log('🎓 Fluesy Exam Frontend Toolchain Initialized with TypeScript & Vite');
