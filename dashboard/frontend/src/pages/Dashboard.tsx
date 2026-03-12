import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Film, CheckCircle, XCircle, Upload, TrendingUp, Clock } from "lucide-react";
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, PieChart, Pie, Cell } from "recharts";
import { api } from "../lib/api";
import { StatsCard } from "../components/StatsCard";
import { Badge } from "../components/Badge";
import type { DailySummary, TotalStats, VideoEntry, TimelinePoint, PipelineState } from "../lib/types";
import { NICHE_COLORS, NICHE_LABELS } from "../lib/types";
import { formatDistanceToNow } from "date-fns";

export function Dashboard() {
  const [daily, setDaily] = useState<DailySummary | null>(null);
  const [total, setTotal] = useState<TotalStats | null>(null);
  const [videos, setVideos] = useState<VideoEntry[]>([]);
  const [timeline, setTimeline] = useState<TimelinePoint[]>([]);
  const [pipeline, setPipeline] = useState<PipelineState | null>(null);

  useEffect(() => {
    api.getDailyStats().then(setDaily).catch(() => {});
    api.getTotalStats().then(setTotal).catch(() => {});
    api.getVideos({ per_page: 8 }).then((r) => setVideos(r.items)).catch(() => {});
    api.getTimeline(30).then((r) => setTimeline(r.timeline)).catch(() => {});
    api.getPipelineStatus().then(setPipeline).catch(() => {});
  }, []);

  const successRate = total && total.total_videos > 0
    ? ((total.successful / total.total_videos) * 100).toFixed(0)
    : "0";

  const nicheData = total?.by_niche
    ? Object.entries(total.by_niche).map(([key, value]) => ({
        name: NICHE_LABELS[key] || key,
        value,
        color: NICHE_COLORS[key] || "#64748b",
      }))
    : [];

  return (
    <div className="space-y-6">
      {/* Pipeline status banner */}
      {pipeline?.running && (
        <div className="bg-purple-500/10 border border-purple-500/30 rounded-xl p-4 flex items-center gap-3">
          <div className="w-3 h-3 bg-purple-400 rounded-full animate-pulse" />
          <div>
            <p className="text-sm text-purple-300 font-medium">
              Pipeline Running: {NICHE_LABELS[pipeline.current_niche!] || pipeline.current_niche} / {pipeline.current_format}
            </p>
            {pipeline.started_at && (
              <p className="text-xs text-purple-400">
                Started {formatDistanceToNow(new Date(pipeline.started_at))} ago
              </p>
            )}
          </div>
          <Link to="/logs" className="ml-auto text-xs text-purple-300 hover:text-purple-200 underline">
            View Logs
          </Link>
        </div>
      )}

      {/* Stats Cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <StatsCard
          label="Total Videos"
          value={total?.total_videos ?? 0}
          icon={<Film className="w-4 h-4" />}
          color="purple"
        />
        <StatsCard
          label="Today"
          value={daily?.total_videos ?? 0}
          icon={<Clock className="w-4 h-4" />}
          trend={daily ? `${daily.successful} OK, ${daily.failed} failed` : undefined}
          color="blue"
        />
        <StatsCard
          label="Success Rate"
          value={`${successRate}%`}
          icon={<CheckCircle className="w-4 h-4" />}
          color="green"
        />
        <StatsCard
          label="Total Uploads"
          value={total?.total_uploads ?? 0}
          icon={<Upload className="w-4 h-4" />}
          color="amber"
        />
      </div>

      {/* Charts Row */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* Timeline Chart */}
        <div className="lg:col-span-2 bg-[#1e293b] rounded-xl border border-[#334155] p-4">
          <h3 className="text-sm font-medium text-slate-300 mb-4 flex items-center gap-2">
            <TrendingUp className="w-4 h-4" /> Videos Over Time
          </h3>
          <div className="h-56">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={timeline}>
                <XAxis dataKey="date" tick={{ fontSize: 10, fill: "#64748b" }} tickFormatter={(d) => d.slice(5)} />
                <YAxis tick={{ fontSize: 10, fill: "#64748b" }} allowDecimals={false} />
                <Tooltip
                  contentStyle={{ background: "#1e293b", border: "1px solid #334155", borderRadius: 8, fontSize: 12 }}
                  labelStyle={{ color: "#94a3b8" }}
                />
                <Line type="monotone" dataKey="ai_trading" stroke={NICHE_COLORS.ai_trading} strokeWidth={2} dot={false} />
                <Line type="monotone" dataKey="ai_money" stroke={NICHE_COLORS.ai_money} strokeWidth={2} dot={false} />
                <Line type="monotone" dataKey="tech_news" stroke={NICHE_COLORS.tech_news} strokeWidth={2} dot={false} />
              </LineChart>
            </ResponsiveContainer>
          </div>
          <div className="flex gap-4 mt-2 justify-center">
            {Object.entries(NICHE_LABELS).map(([key, label]) => (
              <div key={key} className="flex items-center gap-1.5 text-xs text-slate-400">
                <div className="w-2 h-2 rounded-full" style={{ background: NICHE_COLORS[key] }} />
                {label}
              </div>
            ))}
          </div>
        </div>

        {/* Niche Breakdown */}
        <div className="bg-[#1e293b] rounded-xl border border-[#334155] p-4">
          <h3 className="text-sm font-medium text-slate-300 mb-4">By Niche</h3>
          <div className="h-44">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie data={nicheData} dataKey="value" nameKey="name" cx="50%" cy="50%" innerRadius={40} outerRadius={70} paddingAngle={4}>
                  {nicheData.map((entry, i) => (
                    <Cell key={i} fill={entry.color} />
                  ))}
                </Pie>
                <Tooltip contentStyle={{ background: "#1e293b", border: "1px solid #334155", borderRadius: 8, fontSize: 12 }} />
              </PieChart>
            </ResponsiveContainer>
          </div>
          <div className="space-y-1.5 mt-2">
            {nicheData.map((n) => (
              <div key={n.name} className="flex items-center justify-between text-xs">
                <div className="flex items-center gap-1.5 text-slate-400">
                  <div className="w-2 h-2 rounded-full" style={{ background: n.color }} />
                  {n.name}
                </div>
                <span className="text-white font-medium">{n.value}</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Recent Videos */}
      <div className="bg-[#1e293b] rounded-xl border border-[#334155]">
        <div className="flex items-center justify-between p-4 border-b border-[#334155]">
          <h3 className="text-sm font-medium text-slate-300">Recent Videos</h3>
          <Link to="/videos" className="text-xs text-purple-400 hover:text-purple-300">
            View All
          </Link>
        </div>
        <div className="divide-y divide-[#334155]">
          {videos.map((v) => (
            <div key={v.id} className="flex items-center gap-3 p-3 hover:bg-white/[0.02]">
              {/* Thumbnail */}
              <div className="w-16 h-10 rounded bg-[#0f172a] overflow-hidden flex-shrink-0">
                {v.thumbnail_url ? (
                  <img src={v.thumbnail_url} alt="" className="w-full h-full object-cover" />
                ) : (
                  <div className="w-full h-full flex items-center justify-center">
                    <Film className="w-4 h-4 text-slate-600" />
                  </div>
                )}
              </div>

              <div className="flex-1 min-w-0">
                <p className="text-sm text-white truncate">{v.title}</p>
                <div className="flex items-center gap-2 mt-0.5">
                  <Badge niche={v.niche}>{NICHE_LABELS[v.niche] || v.niche}</Badge>
                  <Badge variant={v.format === "long" ? "info" : "default"}>{v.format}</Badge>
                </div>
              </div>

              <div className="text-right flex-shrink-0">
                {v.status === "success" ? (
                  <CheckCircle className="w-4 h-4 text-green-400" />
                ) : (
                  <XCircle className="w-4 h-4 text-red-400" />
                )}
                <p className="text-[10px] text-slate-500 mt-0.5">
                  {v.duration_seconds ? `${Math.round(v.duration_seconds)}s` : ""}
                </p>
              </div>
            </div>
          ))}
          {videos.length === 0 && (
            <div className="p-8 text-center text-slate-500 text-sm">No videos generated yet</div>
          )}
        </div>
      </div>
    </div>
  );
}
