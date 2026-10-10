/**
 * Fluesy Exam - Analytics & Visualization Engine
 * Quản lý đồng hồ thời gian thực, lời chào thông minh theo buổi trong ngày,
 * và biểu đồ phân tích năng lực Chart.js tự động đồng bộ theo Dark / Light theme.
 * @file frontend/src/modules/analytics-chart.ts
 */

import { themeManager } from './theme-manager';
import { ScoreTrendDataPoint, ThemeMode } from '../types';

interface ChartJsInstance {
  destroy: () => void;
  update: () => void;
  data: {
    labels: string[];
    datasets: Array<{
      label: string;
      data: number[];
      borderColor: string;
      backgroundColor: CanvasGradient | string;
      [key: string]: unknown;
    }>;
  };
  options: Record<string, unknown>;
}

declare const Chart: {
  new (ctx: CanvasRenderingContext2D, config: Record<string, unknown>): ChartJsInstance;
};

export class AnalyticsChartEngine {
  private static instance: AnalyticsChartEngine;
  private scoreChart: ChartJsInstance | null = null;
  private clockTimer: number | null = null;

  private constructor() {}

  public static getInstance(): AnalyticsChartEngine {
    if (!AnalyticsChartEngine.instance) {
      AnalyticsChartEngine.instance = new AnalyticsChartEngine();
    }
    return AnalyticsChartEngine.instance;
  }

  /**
   * Khởi động đồng hồ thời gian thực và lời chào buổi sáng / chiều / tối
   */
  public initClockAndGreeting(clockElId = 'realtime-clock', greetingElId = 'dynamic-greeting'): void {
    const update = () => {
      const now = new Date();
      const hour = now.getHours();
      const minutes = now.getMinutes().toString().padStart(2, '0');

      const clockEl = document.getElementById(clockElId);
      if (clockEl) {
        clockEl.innerText = `${hour}:${minutes}`;
      }

      let greeting = 'Chào buổi sáng';
      if (hour >= 12 && hour < 18) {
        greeting = 'Chào buổi chiều';
      } else if (hour >= 18 || hour < 5) {
        greeting = 'Chào buổi tối';
      }

      const greetingEl = document.getElementById(greetingElId);
      if (greetingEl) {
        greetingEl.innerText = `${greeting},`;
      }
    };

    update();
    if (this.clockTimer) {
      window.clearInterval(this.clockTimer);
    }
    this.clockTimer = window.setInterval(update, 1000);
  }

  /**
   * Khởi tạo biểu đồ xu hướng điểm số với Chart.js
   */
  public renderScoreTrendChart(
    canvasId: string,
    dataPoints: ScoreTrendDataPoint[]
  ): void {
    const canvas = document.getElementById(canvasId) as HTMLCanvasElement | null;
    if (!canvas) return;

    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    if (this.scoreChart) {
      this.scoreChart.destroy();
      this.scoreChart = null;
    }

    if (typeof Chart === 'undefined') {
      console.warn('[AnalyticsChartEngine] Thư viện Chart.js chưa được tải.');
      return;
    }

    const currentTheme = themeManager.getSavedTheme();
    this.createScoreChart(ctx, dataPoints, currentTheme);

    // Lắng nghe sự kiện đổi theme để vẽ lại màu biểu đồ thích ứng
    themeManager.onThemeChange((newTheme) => {
      if (this.scoreChart && ctx) {
        this.scoreChart.destroy();
        this.createScoreChart(ctx, dataPoints, newTheme);
      }
    });
  }

  private createScoreChart(
    ctx: CanvasRenderingContext2D,
    dataPoints: ScoreTrendDataPoint[],
    theme: ThemeMode
  ): void {
    const isDark = theme === 'dark';
    const primaryColor = isDark ? '#8b5cf6' : '#6a35ff';
    const gridColor = isDark ? 'rgba(255, 255, 255, 0.08)' : 'rgba(0, 0, 0, 0.05)';
    const textColor = isDark ? '#94a3b8' : '#82828b';

    const labels = dataPoints.map((_, idx) => `Q${idx + 1}`);
    const scores = dataPoints.map((pt) => pt.score);

    const gradient = ctx.createLinearGradient(0, 0, 0, 160);
    gradient.addColorStop(0, isDark ? 'rgba(139, 92, 246, 0.45)' : 'rgba(106, 53, 255, 0.35)');
    gradient.addColorStop(1, 'rgba(106, 53, 255, 0.0)');

    this.scoreChart = new Chart(ctx, {
      type: 'line',
      data: {
        labels: labels,
        datasets: [
          {
            label: 'Điểm số',
            data: scores,
            borderColor: primaryColor,
            backgroundColor: gradient,
            borderWidth: 3,
            pointBackgroundColor: '#ffffff',
            pointBorderColor: primaryColor,
            pointBorderWidth: 2,
            pointRadius: 4,
            pointHoverRadius: 6,
            fill: true,
            tension: 0.4,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { display: false },
          tooltip: {
            backgroundColor: isDark ? '#1e293b' : '#2b2b36',
            titleColor: '#ffffff',
            bodyColor: '#ffffff',
            padding: 10,
            cornerRadius: 8,
            callbacks: {
              label: (context: { raw: unknown }) => ` Điểm: ${context.raw}/10`,
            },
          },
        },
        scales: {
          x: {
            grid: { color: gridColor },
            ticks: { color: textColor, font: { family: "'Segoe UI', sans-serif" } },
          },
          y: {
            min: 0,
            max: 10,
            grid: { color: gridColor },
            ticks: {
              stepSize: 2,
              color: textColor,
              font: { family: "'Segoe UI', sans-serif" },
            },
          },
        },
      },
    });
  }
}

export const analyticsChartEngine = AnalyticsChartEngine.getInstance();
