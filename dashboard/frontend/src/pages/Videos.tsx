import { useEffect, useState } from "react";
import { Film, Download, Trash2, X, ChevronLeft, ChevronRight } from "lucide-react";
import { api } from "../lib/api";
import { Badge } from "../components/Badge";
import type { VideoEntry } from "../lib/types";
import { NICHE_LABELS } from "../lib/types";

export function Videos() {
  const [videos, setVideos] = useState<VideoEntry[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [niche, setNiche] = useState("");
  const [format, setFormat] = useState("");
  const [status, setStatus] = useState("");
  const [selected, setSelected] = useState<VideoEntry | null>(null);
  const [loading, setLoading] = useState(true);

  const perPage = 12;

  const load = async () => {
    setLoading(true);
    try {
      const r = await api.getVideos({ niche, format, status, page, per_page: perPage });
      setVideos(r.items);
      setTotal(r.total);
    } catch { /* ignore */ }
    setLoading(false);
  };

  useEffect(() => { load(); }, [page, niche, format, status]);

  const handleDelete = async (id: string) => {
    if (!confirm("Delete this video and all its files?")) return;
    await api.deleteVideo(id);
    setSelected(null);
    load();
  };

  const totalPages = Math.ceil(total / perPage);

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold text-white">Video Library</h2>
        <span className="text-sm text-slate-400">{total} videos</span>
      </div>

      {/* Filters */}
      <div className="flex gap-2 flex-wrap">
        <select value={niche} onChange={(e) => { setNiche(e.target.value); setPage(1); }}
          className="bg-[#1e293b] border border-[#334155] rounded-lg px-3 py-1.5 text-sm text-slate-300 focus:outline-none focus:border-purple-500">
          <option value="">All Niches</option>
          <option value="ai_trading">AI Trading</option>
          <option value="ai_money">AI Money</option>
          <option value="tech_news">Tech News</option>
        </select>
        <select value={format} onChange={(e) => { setFormat(e.target.value); setPage(1); }}
          className="bg-[#1e293b] border border-[#334155] rounded-lg px-3 py-1.5 text-sm text-slate-300 focus:outline-none focus:border-purple-500">
          <option value="">All Formats</option>
          <option value="long">Long</option>
          <option value="short">Short</option>
        </select>
        <select value={status} onChange={(e) => { setStatus(e.target.value); setPage(1); }}
          className="bg-[#1e293b] border border-[#334155] rounded-lg px-3 py-1.5 text-sm text-slate-300 focus:outline-none focus:border-purple-500">
          <option value="">All Status</option>
          <option value="success">Success</option>
          <option value="error">Error</option>
        </select>
      </div>

      {/* Video Grid */}
      {loading ? (
        <div className="text-center py-12 text-slate-500">Loading...</div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
          {videos.map((v) => (
            <div
              key={v.id}
              onClick={() => setSelected(v)}
              className="bg-[#1e293b] rounded-xl border border-[#334155] overflow-hidden cursor-pointer hover:border-purple-500/50 transition-colors"
            >
              <div className="aspect-video bg-[#0f172a] relative">
                {v.thumbnail_url ? (
                  <img src={v.thumbnail_url} alt="" className="w-full h-full object-cover" />
                ) : (
                  <div className="w-full h-full flex items-center justify-center">
                    <Film className="w-8 h-8 text-slate-700" />
                  </div>
                )}
                <div className="absolute bottom-2 right-2 bg-black/70 text-xs text-white px-1.5 py-0.5 rounded">
                  {v.duration_seconds ? `${Math.floor(v.duration_seconds / 60)}:${String(Math.round(v.duration_seconds % 60)).padStart(2, "0")}` : "--"}
                </div>
                {v.status === "error" && (
                  <div className="absolute top-2 left-2">
                    <Badge variant="error">Error</Badge>
                  </div>
                )}
              </div>
              <div className="p-3">
                <p className="text-sm text-white font-medium truncate">{v.title}</p>
                <div className="flex items-center gap-2 mt-1.5">
                  <Badge niche={v.niche}>{NICHE_LABELS[v.niche] || v.niche}</Badge>
                  <Badge variant={v.format === "long" ? "info" : "default"}>{v.format}</Badge>
                </div>
                <p className="text-[11px] text-slate-500 mt-1.5">
                  {new Date(v.timestamp).toLocaleDateString()} {new Date(v.timestamp).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
                </p>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-center gap-2">
          <button onClick={() => setPage(Math.max(1, page - 1))} disabled={page <= 1}
            className="p-1.5 rounded-lg border border-[#334155] text-slate-400 hover:text-white disabled:opacity-30">
            <ChevronLeft className="w-4 h-4" />
          </button>
          <span className="text-sm text-slate-400">Page {page} of {totalPages}</span>
          <button onClick={() => setPage(Math.min(totalPages, page + 1))} disabled={page >= totalPages}
            className="p-1.5 rounded-lg border border-[#334155] text-slate-400 hover:text-white disabled:opacity-30">
            <ChevronRight className="w-4 h-4" />
          </button>
        </div>
      )}

      {/* Video Detail Modal */}
      {selected && (
        <div className="fixed inset-0 bg-black/60 z-50 flex items-center justify-center p-4" onClick={() => setSelected(null)}>
          <div className="bg-[#1e293b] rounded-2xl border border-[#334155] max-w-3xl w-full max-h-[90vh] overflow-auto" onClick={(e) => e.stopPropagation()}>
            <div className="flex items-center justify-between p-4 border-b border-[#334155]">
              <h3 className="text-sm font-medium text-white truncate pr-4">{selected.title}</h3>
              <button onClick={() => setSelected(null)} className="text-slate-400 hover:text-white">
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Video Player */}
            {selected.video_url && (
              <div className="bg-black">
                <video
                  src={selected.video_url}
                  controls
                  className="w-full max-h-96 mx-auto"
                  poster={selected.thumbnail_url || undefined}
                />
              </div>
            )}

            <div className="p-4 space-y-4">
              {/* Meta */}
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                <div>
                  <p className="text-xs text-slate-500">Niche</p>
                  <Badge niche={selected.niche}>{NICHE_LABELS[selected.niche]}</Badge>
                </div>
                <div>
                  <p className="text-xs text-slate-500">Format</p>
                  <p className="text-sm text-white">{selected.format}</p>
                </div>
                <div>
                  <p className="text-xs text-slate-500">Duration</p>
                  <p className="text-sm text-white">{Math.round(selected.duration_seconds)}s</p>
                </div>
                <div>
                  <p className="text-xs text-slate-500">Status</p>
                  <Badge variant={selected.status === "success" ? "success" : "error"}>{selected.status}</Badge>
                </div>
              </div>

              {/* Error */}
              {selected.error && (
                <div className="bg-red-500/10 border border-red-500/30 rounded-lg p-3">
                  <p className="text-xs text-red-400 font-medium">Error</p>
                  <p className="text-xs text-red-300 mt-1">{selected.error}</p>
                </div>
              )}

              {/* Uploads */}
              {selected.uploads.length > 0 && (
                <div>
                  <p className="text-xs text-slate-500 mb-2">Uploads</p>
                  <div className="space-y-1">
                    {selected.uploads.map((u, i) => (
                      <div key={i} className="flex items-center justify-between bg-[#0f172a] rounded-lg px-3 py-2">
                        <span className="text-sm text-slate-300 capitalize">{u.platform}</span>
                        <Badge variant={u.status === "uploaded" ? "success" : u.status === "skipped" ? "warning" : "error"}>
                          {u.status}
                        </Badge>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Actions */}
              <div className="flex gap-2">
                {selected.video_url && (
                  <a href={selected.video_url} download
                    className="flex items-center gap-1.5 px-3 py-1.5 bg-purple-600 hover:bg-purple-700 text-white rounded-lg text-sm">
                    <Download className="w-3.5 h-3.5" /> Download
                  </a>
                )}
                <button onClick={() => handleDelete(selected.id)}
                  className="flex items-center gap-1.5 px-3 py-1.5 bg-red-600/20 hover:bg-red-600/30 text-red-400 rounded-lg text-sm">
                  <Trash2 className="w-3.5 h-3.5" /> Delete
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
