/**
 * Fluesy Exam - Core TypeScript Definitions and Domain Interfaces
 * @file frontend/src/types/index.ts
 */

// ============================================================================
// 1. QUIZ & EXAMINATION TYPES
// ============================================================================

export type QuizDifficulty =
  | 'remember'
  | 'understand'
  | 'apply'
  | 'analyze'
  | 'evaluate'
  | 'create'
  | 'basic'
  | 'advanced';

export interface QuestionOption {
  index: number;
  label: string;
  text: string;
}

export interface QuestionData {
  id: number;
  order: number;
  question_text: string;
  options: string[];
  correct_answer: number;
  explanation?: string;
}

export interface QuizMetadata {
  id: number;
  title: string;
  num_questions: number;
  difficulty: QuizDifficulty;
  duration_minutes: number;
  document_filename?: string;
  created_at: string;
}

export interface QuizSessionState {
  quizId: number;
  currentQuestionIndex: number;
  answers: Record<number, number>; // questionId -> selectedOptionIndex (0-3)
  remainingSeconds: number;
  isSubmitted: boolean;
  startedAt: number;
  lastSavedAt: number;
}

export interface QuestionResultItem {
  question_id: number;
  question_text: string;
  options: string[];
  user_answer: number | null;
  correct_answer: number;
  is_correct: boolean;
  explanation?: string;
}

export interface UserAttemptSummary {
  id: number;
  quiz_id: number | null;
  quiz_title: string;
  score: number;
  correct_answers: number;
  total_questions: number;
  time_spent_seconds: number;
  formatted_time_spent?: string;
  completed_at: string;
}

// ============================================================================
// 2. SPACED REPETITION & LEITNER FLASHCARD TYPES
// ============================================================================

export type LeitnerMode = 'short_term' | 'long_term';

export type LeitnerBoxLevel = 1 | 2 | 3 | 4 | 5;

export interface ReviewCardItem {
  id: number;
  questionId: number;
  questionText: string;
  options: string[];
  correctAnswer: number;
  explanation: string;
  boxLevel: LeitnerBoxLevel;
  nextReviewAt: string;
  lastReviewedAt: string | null;
  reviewCount: number;
  isMastered: boolean;
}

export interface LeitnerSessionState {
  currentCardIndex: number;
  cards: ReviewCardItem[];
  isFlipped: boolean;
  reviewedCardsCount: number;
  correctCount: number;
  incorrectCount: number;
  startTime: number;
}

// ============================================================================
// 3. WEBSOCKET & REALTIME NOTIFICATIONS
// ============================================================================

export type NotificationType = 'success' | 'error' | 'warning' | 'info';

export interface WebSocketNotificationEvent {
  type: 'send_notification';
  notification_type: NotificationType;
  title: string;
  message: string;
  quiz_id?: number | null;
  url?: string | null;
}

export type ConnectionStatus = 'CONNECTING' | 'OPEN' | 'CLOSING' | 'CLOSED';

export interface ReconnectConfig {
  maxRetries: number;
  baseDelayMs: number;
  maxDelayMs: number;
}

// ============================================================================
// 4. ANALYTICS & CHART VISUALIZATION TYPES
// ============================================================================

export interface ScoreTrendDataPoint {
  date: string;
  score: number;
  quizTitle: string;
}

export interface DashboardAnalytics {
  totalAttempts: number;
  averageScore: number;
  highestScore: number;
  scoreHistory: ScoreTrendDataPoint[];
  difficultyBreakdown: Record<string, number>;
}

// ============================================================================
// 5. THEME & USER PREFERENCES
// ============================================================================

export type ThemeMode = 'light' | 'dark';

export interface ThemeConfig {
  current: ThemeMode;
  storageKey: string;
}

// ============================================================================
// 6. DOCUMENT MANAGEMENT & AI PIPELINE
// ============================================================================

export type DocumentProcessingStatus = 'uploaded' | 'processing' | 'completed' | 'failed';

export interface DocumentUploadEvent {
  fileName: string;
  fileSize: number;
  progressPercent: number;
  status: DocumentProcessingStatus;
}
