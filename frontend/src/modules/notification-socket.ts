/**
 * Fluesy Exam - Realtime WebSocket Notification Module
 * Quản lý kết nối WebSocket với Daphne / Django Channels, tự động reconnect với exponential backoff,
 * xử lý hiển thị SweetAlert2 popup và phát sự kiện custom event.
 * @file frontend/src/modules/notification-socket.ts
 */

import { WebSocketNotificationEvent, ConnectionStatus, ReconnectConfig } from '../types';

declare const Swal: {
  fire: (options: Record<string, unknown>) => Promise<{ isConfirmed: boolean }>;
};

export class NotificationSocketClient {
  private static instance: NotificationSocketClient;
  private socket: WebSocket | null = null;
  private status: ConnectionStatus = 'CLOSED';
  private reconnectAttempts = 0;
  private reconnectTimer: number | null = null;
  private heartbeatTimer: number | null = null;

  private readonly config: ReconnectConfig = {
    maxRetries: 10,
    baseDelayMs: 2000,
    maxDelayMs: 30000,
  };

  private constructor() {}

  public static getInstance(): NotificationSocketClient {
    if (!NotificationSocketClient.instance) {
      NotificationSocketClient.instance = new NotificationSocketClient();
    }
    return NotificationSocketClient.instance;
  }

  /**
   * Tạo URL kết nối WebSocket dựa trên protocol và host hiện tại
   */
  private getWebSocketUrl(): string {
    const protocol = window.location.protocol === 'https:' ? 'wss://' : 'ws://';
    return `${protocol}${window.location.host}/ws/notifications/`;
  }

  /**
   * Khởi tạo kết nối tới server Django Channels
   */
  public connect(): void {
    if (this.socket && (this.socket.readyState === WebSocket.OPEN || this.socket.readyState === WebSocket.CONNECTING)) {
      return;
    }

    const wsUrl = this.getWebSocketUrl();
    this.status = 'CONNECTING';
    console.log(`[NotificationSocket] Đang kết nối tới: ${wsUrl}`);

    try {
      this.socket = new WebSocket(wsUrl);

      this.socket.onopen = this.handleOpen.bind(this);
      this.socket.onmessage = this.handleMessage.bind(this);
      this.socket.onclose = this.handleClose.bind(this);
      this.socket.onerror = this.handleError.bind(this);
    } catch (err) {
      console.error('[NotificationSocket] Lỗi khởi tạo WebSocket:', err);
      this.scheduleReconnect();
    }
  }

  private handleOpen(): void {
    this.status = 'OPEN';
    this.reconnectAttempts = 0;
    console.log('[NotificationSocket] Kết nối WebSocket THÀNH CÔNG! 🎉');

    if (this.reconnectTimer) {
      window.clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }

    this.startHeartbeat();
  }

  private handleMessage(event: MessageEvent): void {
    try {
      const data = JSON.parse(event.data) as WebSocketNotificationEvent;
      console.log('[NotificationSocket] Nhận thông báo từ server:', data);

      // Phát sự kiện toàn cục để các component khác có thể lắng nghe
      const customEvent = new CustomEvent('fluesy:notification', { detail: data });
      window.dispatchEvent(customEvent);

      // Phát âm thanh thông báo nhẹ nhàng
      this.playNotificationSound(data.notification_type === 'success');

      // Hiển thị Popup tương tác với người dùng
      this.displayNotificationPopup(data);
    } catch (err) {
      console.error('[NotificationSocket] Lỗi phân tích gói tin nhận được:', err);
    }
  }

  private handleClose(event: CloseEvent): void {
    this.status = 'CLOSED';
    this.stopHeartbeat();
    console.warn(`[NotificationSocket] WebSocket đã đóng (code: ${event.code}). Chuẩn bị kết nối lại...`);
    this.scheduleReconnect();
  }

  private handleError(error: Event): void {
    console.warn('[NotificationSocket] Lỗi kết nối WebSocket:', error);
    if (this.socket) {
      this.socket.close();
    }
  }

  /**
   * Lên lịch kết nối lại sử dụng Exponential Backoff có Jitter
   */
  private scheduleReconnect(): void {
    if (this.reconnectAttempts >= this.config.maxRetries) {
      console.warn('[NotificationSocket] Đã thử kết nối lại tối đa số lần cho phép. Dừng retry.');
      return;
    }

    if (this.reconnectTimer) {
      return;
    }

    this.reconnectAttempts++;
    const expDelay = this.config.baseDelayMs * Math.pow(1.5, this.reconnectAttempts - 1);
    const jitter = Math.random() * 1000;
    const delay = Math.min(expDelay + jitter, this.config.maxDelayMs);

    console.log(`[NotificationSocket] Thử kết nối lại lần ${this.reconnectAttempts} sau ${Math.round(delay)}ms...`);
    this.reconnectTimer = window.setTimeout(() => {
      this.reconnectTimer = null;
      this.connect();
    }, delay);
  }

  /**
   * Giữ kết nối liveness (Heartbeat)
   */
  private startHeartbeat(): void {
    this.stopHeartbeat();
    this.heartbeatTimer = window.setInterval(() => {
      if (this.socket && this.socket.readyState === WebSocket.OPEN) {
        this.socket.send(JSON.stringify({ type: 'ping' }));
      }
    }, 45000); // 45 giây ping một lần
  }

  private stopHeartbeat(): void {
    if (this.heartbeatTimer) {
      window.clearInterval(this.heartbeatTimer);
      this.heartbeatTimer = null;
    }
  }

  /**
   * Phát âm thanh chuông báo tin nhắn sử dụng Web Audio API (không cần tải file mp3 ngoài)
   */
  private playNotificationSound(isSuccess: boolean): void {
    try {
      const AudioCtx = window.AudioContext || (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
      if (!AudioCtx) return;
      const ctx = new AudioCtx();
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();

      osc.connect(gain);
      gain.connect(ctx.destination);

      if (isSuccess) {
        osc.frequency.setValueAtTime(587.33, ctx.currentTime); // D5
        osc.frequency.setValueAtTime(880, ctx.currentTime + 0.1); // A5
      } else {
        osc.frequency.setValueAtTime(300, ctx.currentTime);
        osc.frequency.setValueAtTime(200, ctx.currentTime + 0.15);
      }

      gain.gain.setValueAtTime(0.15, ctx.currentTime);
      gain.gain.exponentialRampToValueAtTime(0.01, ctx.currentTime + 0.3);

      osc.start(ctx.currentTime);
      osc.stop(ctx.currentTime + 0.3);
    } catch {
      // Bỏ qua nếu trình duyệt chặn autoplay audio
    }
  }

  /**
   * Hiển thị thông báo SweetAlert2 chuyên nghiệp
   */
  private displayNotificationPopup(data: WebSocketNotificationEvent): void {
    if (typeof Swal === 'undefined') {
      alert(`${data.title}\n${data.message}`);
      return;
    }

    if (data.notification_type === 'error') {
      Swal.fire({
        title: data.title || 'Không thể tạo đề thi ⚠️',
        text: data.message,
        icon: 'error',
        confirmButtonText: 'Đã hiểu',
        confirmButtonColor: '#dc3545',
        allowOutsideClick: true,
      });
      return;
    }

    // Success notification
    if (data.url) {
      Swal.fire({
        title: data.title || 'Đề thi đã sẵn sàng! 🎉',
        text: data.message,
        icon: 'success',
        showCancelButton: true,
        confirmButtonText: '<i class="bi bi-play-circle-fill me-1"></i> Làm bài ngay',
        cancelButtonText: 'Để sau',
        confirmButtonColor: '#6a35ff',
        cancelButtonColor: '#6c757d',
        allowOutsideClick: false,
        backdrop: 'rgba(0, 0, 123, 0.3)',
      }).then((result) => {
        if (result.isConfirmed && data.url) {
          window.location.href = data.url;
        } else {
          window.location.reload();
        }
      });
    } else {
      Swal.fire({
        title: data.title || 'Thông báo 🎉',
        text: data.message,
        icon: 'success',
        confirmButtonText: 'Đóng',
        confirmButtonColor: '#6a35ff',
        allowOutsideClick: false,
        backdrop: 'rgba(0, 0, 123, 0.3)',
      }).then((result) => {
        if (result.isConfirmed) {
          window.location.reload();
        }
      });
    }
  }

  public getStatus(): ConnectionStatus {
    return this.status;
  }

  public disconnect(): void {
    this.stopHeartbeat();
    if (this.reconnectTimer) {
      window.clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
    if (this.socket) {
      this.socket.close();
      this.socket = null;
    }
    this.status = 'CLOSED';
  }
}

export const notificationClient = NotificationSocketClient.getInstance();
