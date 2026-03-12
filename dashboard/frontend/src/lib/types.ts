export interface VideoUpload {
  platform: string;
  status: string;
  video_id?: string;
  url?: string;
  error?: string;
  post_id?: string;
}

export interface VideoEntry {
  id: string;
  timestamp: string;
  niche: string;
  topic: string;
  format: string;
  title: string;
  video_path: string | null;
  video_url?: string | null;
  thumbnail_url?: string | null;
  duration_seconds: number;
  uploads: VideoUpload[];
  status: "success" | "error";
  error: string | null;
}

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  per_page: number;
}

export interface DailySummary {
  date: string;
  total_videos: number;
  successful: number;
  failed: number;
  by_niche: Record<string, number>;
  platforms_uploaded: number;
}

export interface TotalStats {
  total_videos: number;
  successful: number;
  failed: number;
  total_uploads: number;
  by_niche: Record<string, number>;
}

export interface TimelinePoint {
  date: string;
  total: number;
  ai_trading?: number;
  ai_money?: number;
  tech_news?: number;
}

export interface PipelineState {
  running: boolean;
  current_niche: string | null;
  current_format: string | null;
  started_at: string | null;
  last_result: Record<string, unknown> | null;
}

export interface HealthCheck {
  status: "ready" | "degraded";
  checks: Record<string, string>;
  timestamp: string;
}

export interface Schedule {
  [niche: string]: {
    name: string;
    long_form: number;
    shorts: number;
  };
}

export interface LogEntry {
  timestamp: string;
  message: string;
}

export interface UploadEntry {
  video_id: string;
  video_title: string;
  niche: string;
  format: string;
  timestamp: string;
  platform: string;
  status: string;
  url?: string;
  error?: string;
}

export interface UploadSummary {
  total: number;
  by_platform: Record<string, number>;
  by_status: Record<string, number>;
}

export const NICHE_COLORS: Record<string, string> = {
  ai_trading: "#22c55e",
  ai_money: "#3b82f6",
  tech_news: "#8b5cf6",
};

export const NICHE_LABELS: Record<string, string> = {
  ai_trading: "AI Trading",
  ai_money: "AI Money",
  tech_news: "Tech News",
};
