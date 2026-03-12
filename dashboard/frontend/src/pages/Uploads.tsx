import { useEffect, useState } from "react";
import { Upload, RefreshCw, CheckCircle, XCircle, MinusCircle, Loader2 } from "lucide-react";
import { api } from "../lib/api";
import { Badge } from "../components/Badge";
import { StatsCard } from "../components/StatsCard";
import type { UploadEntry, UploadSummary } from "../lib/types";
import { NICHE_LABELS } from "../lib/types";

export function Uploads() {
  const [uploads, setUploads] = useState<UploadEntry[]>([]);
  const [summary, setSummary] = useState<UploadSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [retrying, setRetrying] = useState<string | null>(null);

  const load = async () => {
    setLoading(true);
    try {
      const r = await api.getUploads({ per_page: 50 });
      setUploads(r.items);
      setSummary(r.summary);
    } catch { /* ignore */ }
    setLoading(false);
  };

  useEffect(() => { load(); }, []);

  const handleRetry = async (videoId: string, platform: string) => {
    setRetrying(`${videoId}-${platform}`);
    try {
      await api.retryUpload(videoId, platform);
      load();
    } catch { /* ignore */ }
    setRetrying(null);
  };

  const statusIcon = (status: string) => {
    switch (status) {
      case "uploaded": return <CheckCircle className="w-4 h-4 text-green-400" />;
      case "failed": return <XCircle className="w-4 h-4 text-red-400" />;
      case "skipped": return <MinusCircle className="w-4 h-4 text-slate-500" />;
      default: return <MinusCircle className="w-4 h-4 text-slate-500" />;
    }
  };

  return (
    <div className="space-y-6">
      <h2 className="text-lg font-semibold text-white flex items-center gap-2">
        <Upload className="w-5 h-5 text-purple-400" /> Upload Manager
      </h2>

      {/* Summary */}
      {summary && (
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          <StatsCard label="Total Uploads" value={summary.total} icon={<Upload className="w-4 h-4" />} color="purple" />
          <StatsCard label="YouTube" value={summary.by_platform?.youtube || 0} icon={<CheckCircle className="w-4 h-4" />} color="green" />
          <StatsCard label="TikTok" value={summary.by_platform?.tiktok || 0} icon={<CheckCircle className="w-4 h-4" />} color="blue" />
          <StatsCard label="Failed" value={summary.by_status?.failed || 0} icon={<XCircle className="w-4 h-4" />} color="red" />
        </div>
      )}

      {/* Upload Table */}
      <div className="bg-[#1e293b] rounded-xl border border-[#334155] overflow-hidden">
        {loading ? (
          <div className="p-8 text-center text-slate-500">Loading...</div>
        ) : (
          <table className="w-full">
            <thead>
              <tr className="border-b border-[#334155]">
                <th className="text-left text-xs text-slate-500 uppercase tracking-wider p-4">Video</th>
                <th className="text-left text-xs text-slate-500 uppercase tracking-wider p-4">Platform</th>
                <th className="text-center text-xs text-slate-500 uppercase tracking-wider p-4">Status</th>
                <th className="text-left text-xs text-slate-500 uppercase tracking-wider p-4">Date</th>
                <th className="text-right text-xs text-slate-500 uppercase tracking-wider p-4">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#334155]">
              {uploads.map((u, i) => (
                <tr key={i} className="hover:bg-white/[0.02]">
                  <td className="p-4">
                    <p className="text-sm text-white truncate max-w-xs">{u.video_title}</p>
                    <Badge niche={u.niche}>{NICHE_LABELS[u.niche] || u.niche}</Badge>
                  </td>
                  <td className="p-4">
                    <span className="text-sm text-slate-300 capitalize">{u.platform}</span>
                  </td>
                  <td className="p-4 text-center">
                    <div className="flex items-center justify-center gap-1.5">
                      {statusIcon(u.status)}
                      <span className="text-xs text-slate-400">{u.status}</span>
                    </div>
                  </td>
                  <td className="p-4">
                    <span className="text-xs text-slate-500">
                      {u.timestamp ? new Date(u.timestamp).toLocaleDateString() : ""}
                    </span>
                  </td>
                  <td className="p-4 text-right">
                    {u.status === "failed" && u.platform !== "dry_run" && (
                      <button
                        onClick={() => handleRetry(u.video_id, u.platform)}
                        disabled={retrying === `${u.video_id}-${u.platform}`}
                        className="flex items-center gap-1 ml-auto px-2 py-1 bg-purple-600/20 hover:bg-purple-600/30 text-purple-300 rounded text-xs"
                      >
                        {retrying === `${u.video_id}-${u.platform}` ? (
                          <Loader2 className="w-3 h-3 animate-spin" />
                        ) : (
                          <RefreshCw className="w-3 h-3" />
                        )}
                        Retry
                      </button>
                    )}
                    {u.url && (
                      <a href={u.url} target="_blank" rel="noopener noreferrer" className="text-xs text-purple-400 hover:text-purple-300">
                        View
                      </a>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
        {!loading && uploads.length === 0 && (
          <div className="p-8 text-center text-slate-500 text-sm">No uploads yet</div>
        )}
      </div>
    </div>
  );
}
