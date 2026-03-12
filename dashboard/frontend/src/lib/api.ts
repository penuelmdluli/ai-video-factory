import type {
  VideoEntry, PaginatedResponse, DailySummary, TotalStats,
  PipelineState, HealthCheck, Schedule, UploadEntry, UploadSummary,
  TimelinePoint,
} from "./types";

const BASE = "";

async function apiFetch<T>(path: string, options?: RequestInit): Promise<T> {
  const token = localStorage.getItem("avf_token");
  const res = await fetch(`${BASE}/api${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...options?.headers,
    },
  });
  if (res.status === 401) {
    localStorage.removeItem("avf_token");
    window.location.href = "/login";
    throw new Error("Unauthorized");
  }
  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || `HTTP ${res.status}`);
  }
  return res.json();
}

export const api = {
  // Auth
  login: (password: string) =>
    apiFetch<{ token: string }>("/auth/login", {
      method: "POST",
      body: JSON.stringify({ password }),
    }),

  // Videos
  getVideos: (params?: Record<string, string | number>) => {
    const qs = params ? "?" + new URLSearchParams(
      Object.fromEntries(Object.entries(params).filter(([, v]) => v !== undefined && v !== "").map(([k, v]) => [k, String(v)]))
    ).toString() : "";
    return apiFetch<PaginatedResponse<VideoEntry>>(`/videos${qs}`);
  },
  getVideo: (id: string) => apiFetch<VideoEntry>(`/videos/${id}`),
  deleteVideo: (id: string) => apiFetch(`/videos/${id}`, { method: "DELETE" }),

  // Stats
  getDailyStats: () => apiFetch<DailySummary>("/stats/daily"),
  getTotalStats: () => apiFetch<TotalStats>("/stats/total"),
  getTimeline: (days = 30) => apiFetch<{ timeline: TimelinePoint[] }>(`/stats/timeline?days=${days}`),

  // Pipeline
  triggerPipeline: (body: { niche: string; format: string; dry_run: boolean }) =>
    apiFetch("/pipeline/trigger", { method: "POST", body: JSON.stringify(body) }),
  getPipelineStatus: () => apiFetch<PipelineState>("/pipeline/status"),

  // Schedule
  getSchedule: () => apiFetch<Schedule>("/schedule"),
  updateSchedule: (schedule: Record<string, unknown>) =>
    apiFetch("/schedule", { method: "PUT", body: JSON.stringify({ schedule }) }),

  // Health
  getHealth: () => apiFetch<HealthCheck>("/health"),

  // Settings
  getSettings: () => apiFetch<Record<string, unknown>>("/settings"),
  getNiches: () => apiFetch<Record<string, unknown>>("/settings/niches"),

  // Uploads
  getUploads: (params?: Record<string, string | number>) => {
    const qs = params ? "?" + new URLSearchParams(
      Object.fromEntries(Object.entries(params).filter(([, v]) => v !== undefined && v !== "").map(([k, v]) => [k, String(v)]))
    ).toString() : "";
    return apiFetch<{ items: UploadEntry[]; total: number; summary: UploadSummary }>(`/uploads${qs}`);
  },
  retryUpload: (videoId: string, platform: string) =>
    apiFetch(`/uploads/${videoId}/retry/${platform}`, { method: "POST" }),

  // Topics
  suggestTopic: (niche: string) => apiFetch<{ topic: string }>(`/topics/suggest?niche=${niche}`),
};
