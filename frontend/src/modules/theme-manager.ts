/**
 * Fluesy Exam - Theme Management Module
 * Quản lý Dark / Light mode, đồng bộ LocalStorage, cập nhật UI và dispatch sự kiện đổi theme
 * @file frontend/src/modules/theme-manager.ts
 */

import { ThemeMode } from '../types';

export class ThemeManager {
  private static instance: ThemeManager;
  private readonly storageKey: string = 'fluesy_theme';
  private currentTheme: ThemeMode = 'light';

  private constructor() {
    this.currentTheme = this.getSavedTheme();
  }

  public static getInstance(): ThemeManager {
    if (!ThemeManager.instance) {
      ThemeManager.instance = new ThemeManager();
    }
    return ThemeManager.instance;
  }

  /**
   * Lấy theme hiện tại đã lưu hoặc theo cấu hình hệ thống
   */
  public getSavedTheme(): ThemeMode {
    const saved = localStorage.getItem(this.storageKey);
    if (saved === 'dark' || saved === 'light') {
      return saved;
    }
    // Mặc định kiểm tra prefers-color-scheme nếu chưa từng lưu
    if (window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches) {
      return 'dark';
    }
    return 'light';
  }

  /**
   * Áp dụng theme lên document root và cập nhật toàn bộ icon, text, badge
   */
  public applyTheme(theme: ThemeMode): void {
    this.currentTheme = theme;
    document.documentElement.setAttribute('data-bs-theme', theme);
    localStorage.setItem(this.storageKey, theme);

    this.updateUIElements(theme);
    this.dispatchThemeChangeEvent(theme);
  }

  /**
   * Chuyển đổi qua lại giữa Light và Dark mode
   */
  public toggleTheme(): ThemeMode {
    const newTheme: ThemeMode = this.currentTheme === 'dark' ? 'light' : 'dark';
    this.applyTheme(newTheme);
    return newTheme;
  }

  /**
   * Cập nhật các icon và nhãn hiển thị trên thanh điều hướng
   */
  private updateUIElements(theme: ThemeMode): void {
    const isDark = theme === 'dark';

    // Cập nhật Icons
    const icons = document.querySelectorAll<HTMLElement>('#themeIcon, #guestThemeIcon');
    icons.forEach((icon) => {
      icon.className = isDark ? 'bi bi-sun-fill me-2' : 'bi bi-moon-stars-fill me-2';
      icon.style.color = isDark ? '#f59e0b' : '#8b5cf6';
    });

    // Cập nhật Text
    const themeText = document.getElementById('themeText');
    if (themeText) {
      themeText.textContent = isDark ? 'Chế độ sáng' : 'Chế độ tối';
    }

    // Cập nhật Badge
    const themeBadge = document.getElementById('themeBadge');
    if (themeBadge) {
      themeBadge.textContent = isDark ? 'Dark' : 'Light';
      themeBadge.className = isDark
        ? 'badge rounded-pill bg-warning-subtle text-warning'
        : 'badge rounded-pill bg-primary-subtle text-primary';
    }
  }

  /**
   * Phát sự kiện CustomEvent để các module khác (như Chart.js) tự vẽ lại theo theme
   */
  private dispatchThemeChangeEvent(theme: ThemeMode): void {
    const event = new CustomEvent('fluesy:theme-change', {
      detail: { theme, isDark: theme === 'dark' },
    });
    window.dispatchEvent(event);
  }

  /**
   * Lắng nghe sự kiện đổi theme
   */
  public onThemeChange(callback: (theme: ThemeMode) => void): () => void {
    const handler = (e: Event) => {
      const customEvent = e as CustomEvent<{ theme: ThemeMode }>;
      callback(customEvent.detail.theme);
    };
    window.addEventListener('fluesy:theme-change', handler);
    return () => window.removeEventListener('fluesy:theme-change', handler);
  }

  /**
   * Tự động đóng các thông báo Flash / Alert của Bootstrap sau thời gian quy định
   */
  public initAlertAutoDismiss(timeoutMs: number = 5000): void {
    setTimeout(() => {
      const alerts = document.querySelectorAll('.alert');
      alerts.forEach((alert) => {
        // Hỗ trợ Bootstrap Alert nếu có
        const bs = (window as unknown as { bootstrap?: { Alert: { getOrCreateInstance: (el: Element) => { close: () => void } } } }).bootstrap;
        if (bs?.Alert) {
          const bsAlert = bs.Alert.getOrCreateInstance(alert);
          bsAlert.close();
        } else {
          alert.classList.add('fade');
          setTimeout(() => alert.remove(), 300);
        }
      });
    }, timeoutMs);
  }

  /**
   * Khởi tạo gắn sự kiện click cho các nút chuyển đổi theme
   */
  public init(): void {
    const initialTheme = this.getSavedTheme();
    this.applyTheme(initialTheme);

    const toggleButtons = document.querySelectorAll<HTMLElement>(
      '#themeToggleBtn, #guestThemeToggleBtn'
    );
    toggleButtons.forEach((btn) => {
      btn.addEventListener('click', (e) => {
        e.preventDefault();
        this.toggleTheme();
      });
    });

    this.initAlertAutoDismiss(5000);
  }
}

export const themeManager = ThemeManager.getInstance();
