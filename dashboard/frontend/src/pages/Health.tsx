import { useEffect, useState } from "react";
import { Heart, RefreshCw, Loader2, CheckCircle, XCircle, AlertTriangle } from "lucide-react";
import { api } from "../lib/api";
import type { HealthCheck as HealthCheckType, VideoEntry } from "../lib/types";

export function Health() {
  const [health, setHealth] = useState<HealthCheckType | null>(null);
  const [errors, setErrors] = useState<VideoEntry[]>([]);
  const [loading, setLoading] = useState(false);
  const [loadingInitial, setLoadingInitial] = useState(true);

  const loadErrors = async () => {
    try {
      const r = await api.getVideos({ status: "error", per_page: 10 });
      setErrors(r.items);
    } catch { /* ignore */ }
  };

  useEffect(() => {
    loadErrors();
    setLoadingInitial(false);
  }, []);

  const runHealthCheck = async () => {
    setLoading(true);
    try {
      const result = await api.getHealth();
      setHealth(result);
    } catch { /* ignore */ }
    setLoading(false);
  };

  const getStatusIcon = (status: string) => {
    if (status.startsWith("OK")) return <CheckCircle className="w-5 h-5 text-green-400" />;
    if (status.includes("NO_KEY")) return <AlertTriangle className="w-5 h-5 text-amber-400" />;
    return <XCircle className="w-5 h-5 text-red-400" />;
  };

  const getStatusColor = (status: string) => {
    if (status.startsWith("OK")) return "border-green-500/30 bg-green-500/5";
    if (status.includes("NO_KEY")) return "border-amber-500/30 bg-amber-500/5";
    return "border-red-500/30 bg-red-500/5";
  };

  const serviceLabels: Record<string, string> = {
    gemini: "Gemini AI",
    pexels: "Pexels API",
    edge_tts: "Edge TTS",
    elevenlabs: "ElevenLabs",
    ffmpeg: "FFmpeg",
    openai_dalle: "OpenAI / DALL-E",
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold text-white flex items-center gap-2">
          <Heart className="w-5 h-5 text-purple-400" /> System Health
        </h2>
        <button
          onClick={runHealthCheck}
          disabled={loading}
          className="flex items-center gap-1.5 px-3 py-1.5 bg-purple-600 hover:bg-purple-700 disabled:opacity-50 text-white rounded-lg text-sm"
        >
          {loading ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <RefreshCw className="w-3.5 h-3.5" />}
          Run Health Check
        </button>
      </div>

      {/* Overall Status */}
      {health && (
        <div className={`rounded-xl border p-4 flex items-center gap-3 ${
          health.status === "ready" ? "border-green-500/30 bg-green-500/10" : "border-amber-500/30 bg-amber-500/10"
        }`}>
          {health.status === "ready" ? (
            <CheckCircle className="w-6 h-6 text-green-400" />
          ) : (
            <AlertTriangle className="w-6 h-6 text-amber-400" />
          )}
          <div>
            <p className="text-sm font-medium text-white">
              {health.status === "ready" ? "All Systems Ready" : "Issues Detected"}
            </p>
            <p className="text-xs text-slate-400">Last checked: {new Date(health.timestamp).toLocaleTimeString()}</p>
          </div>
        </div>
      )}

      {/* Service Cards */}
      {health && (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
          {Object.entries(health.checks).map(([key, status]) => (
            <div key={key} className={`rounded-xl border p-4 ${getStatusColor(status)}`}>
              <div className="flex items-center gap-3">
                {getStatusIcon(status)}
                <div className="min-w-0">
                  <p className="text-sm font-medium text-white">{serviceLabels[key] || key}</p>
                  <p className="text-xs text-slate-400 truncate">{status}</p>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {!health && !loadingInitial && (
        <div className="bg-[#1e293b] rounded-xl border border-[#334155] p-8 text-center">
          <Heart className="w-8 h-8 text-slate-600 mx-auto mb-2" />
          <p className="text-sm text-slate-500">Click "Run Health Check" to test all services</p>
        </div>
      )}

      {/* Recent Errors */}
      <div className="bg-[#1e293b] rounded-xl border border-[#334155]">
        <div className="p-4 border-b border-[#334155]">
          <h3 className="text-sm font-medium text-slate-300">Recent Errors</h3>
        </div>
        <div className="divide-y divide-[#334155]">
          {errors.map((e) => (
            <div key={e.id} className="p-4">
              <div className="flex items-center justify-between mb-1">
                <p className="text-sm text-white">{e.title || e.topic}</p>
                <span className="text-xs text-slate-500">
                  {new Date(e.timestamp).toLocaleDateString()}
                </span>
              </div>
              <p className="text-xs text-red-400">{e.error}</p>
            </div>
          ))}
          {errors.length === 0 && (
            <div className="p-8 text-center text-slate-500 text-sm">No recent errors</div>
          )}
        </div>
      </div>
    </div>
  );
}
