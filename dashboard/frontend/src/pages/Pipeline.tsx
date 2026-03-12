import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Play, Loader2, Lightbulb, ScrollText } from "lucide-react";
import { api } from "../lib/api";
import type { PipelineState } from "../lib/types";
import { NICHE_LABELS } from "../lib/types";
import { formatDistanceToNow } from "date-fns";

export function Pipeline() {
  const [niche, setNiche] = useState("ai_trading");
  const [format, setFormat] = useState("short");
  const [dryRun, setDryRun] = useState(true);
  const [pipeline, setPipeline] = useState<PipelineState | null>(null);
  const [triggering, setTriggering] = useState(false);
  const [suggestedTopic, setSuggestedTopic] = useState("");
  const [suggesting, setSuggesting] = useState(false);
  const [message, setMessage] = useState("");

  const pollStatus = async () => {
    try {
      const s = await api.getPipelineStatus();
      setPipeline(s);
    } catch { /* ignore */ }
  };

  useEffect(() => {
    pollStatus();
    const interval = setInterval(pollStatus, 3000);
    return () => clearInterval(interval);
  }, []);

  const handleTrigger = async () => {
    setTriggering(true);
    setMessage("");
    try {
      await api.triggerPipeline({ niche, format, dry_run: dryRun });
      setMessage("Pipeline triggered! Watch the Logs page for progress.");
      pollStatus();
    } catch (e: unknown) {
      setMessage(`Error: ${e instanceof Error ? e.message : "Unknown error"}`);
    }
    setTriggering(false);
  };

  const handleSuggestTopic = async () => {
    setSuggesting(true);
    setSuggestedTopic("");
    try {
      const result = await api.suggestTopic(niche);
      setSuggestedTopic(result.topic);
    } catch {
      setSuggestedTopic("Failed to suggest topic");
    }
    setSuggesting(false);
  };

  const isRunning = pipeline?.running;

  return (
    <div className="space-y-6 max-w-2xl">
      <h2 className="text-lg font-semibold text-white">Pipeline Control</h2>

      {/* Running Status */}
      {isRunning && (
        <div className="bg-purple-500/10 border border-purple-500/30 rounded-xl p-4">
          <div className="flex items-center gap-3">
            <Loader2 className="w-5 h-5 text-purple-400 animate-spin" />
            <div>
              <p className="text-sm text-purple-300 font-medium">
                Pipeline Running: {NICHE_LABELS[pipeline!.current_niche!] || pipeline!.current_niche} / {pipeline!.current_format}
              </p>
              {pipeline!.started_at && (
                <p className="text-xs text-purple-400">
                  Started {formatDistanceToNow(new Date(pipeline!.started_at))} ago
                </p>
              )}
            </div>
            <Link to="/logs" className="ml-auto flex items-center gap-1 text-xs text-purple-300 hover:text-purple-200 bg-purple-500/20 px-2.5 py-1 rounded-lg">
              <ScrollText className="w-3.5 h-3.5" /> View Logs
            </Link>
          </div>
        </div>
      )}

      {/* Last Result */}
      {pipeline?.last_result && !isRunning && (
        <div className={`border rounded-xl p-4 ${
          (pipeline.last_result as Record<string, unknown>).status === "success"
            ? "bg-green-500/10 border-green-500/30"
            : "bg-red-500/10 border-red-500/30"
        }`}>
          <p className="text-sm font-medium">
            Last Run: {String((pipeline.last_result as Record<string, unknown>).status) === "success" ? "Success" : "Failed"}
          </p>
          {(pipeline.last_result as Record<string, unknown>).title ? (
            <p className="text-xs text-slate-400 mt-1">{String((pipeline.last_result as Record<string, unknown>).title)}</p>
          ) : null}
        </div>
      )}

      {/* Trigger Form */}
      <div className="bg-[#1e293b] rounded-xl border border-[#334155] p-6 space-y-5">
        {/* Niche */}
        <div>
          <label className="block text-sm text-slate-400 mb-2">Niche</label>
          <div className="grid grid-cols-3 gap-2">
            {Object.entries(NICHE_LABELS).map(([key, label]) => (
              <button
                key={key}
                onClick={() => setNiche(key)}
                className={`px-3 py-2.5 rounded-lg text-sm border transition-colors ${
                  niche === key
                    ? "border-purple-500 bg-purple-500/20 text-purple-300"
                    : "border-[#334155] text-slate-400 hover:border-slate-500"
                }`}
              >
                {label}
              </button>
            ))}
          </div>
        </div>

        {/* Format */}
        <div>
          <label className="block text-sm text-slate-400 mb-2">Format</label>
          <div className="grid grid-cols-2 gap-2">
            {[
              { key: "short", label: "Short-form", desc: "Shorts + TikTok + Reels" },
              { key: "long", label: "Long-form", desc: "YouTube (8+ min)" },
            ].map(({ key, label, desc }) => (
              <button
                key={key}
                onClick={() => setFormat(key)}
                className={`px-3 py-2.5 rounded-lg text-left border transition-colors ${
                  format === key
                    ? "border-purple-500 bg-purple-500/20 text-purple-300"
                    : "border-[#334155] text-slate-400 hover:border-slate-500"
                }`}
              >
                <span className="text-sm font-medium">{label}</span>
                <span className="block text-[11px] opacity-60">{desc}</span>
              </button>
            ))}
          </div>
        </div>

        {/* Dry Run Toggle */}
        <div className="flex items-center justify-between">
          <div>
            <p className="text-sm text-slate-300">Dry Run</p>
            <p className="text-xs text-slate-500">Generate video but don't upload to platforms</p>
          </div>
          <button
            onClick={() => setDryRun(!dryRun)}
            className={`relative w-11 h-6 rounded-full transition-colors ${dryRun ? "bg-purple-600" : "bg-slate-600"}`}
          >
            <div className={`absolute top-0.5 w-5 h-5 bg-white rounded-full transition-transform ${dryRun ? "left-5.5 translate-x-0" : "left-0.5"}`}
              style={{ left: dryRun ? "22px" : "2px" }} />
          </button>
        </div>

        {/* Suggest Topic */}
        <div>
          <button
            onClick={handleSuggestTopic}
            disabled={suggesting}
            className="flex items-center gap-1.5 text-sm text-purple-400 hover:text-purple-300"
          >
            <Lightbulb className="w-3.5 h-3.5" />
            {suggesting ? "Generating..." : "Suggest Topic"}
          </button>
          {suggestedTopic && (
            <p className="mt-2 text-sm text-slate-300 bg-[#0f172a] rounded-lg px-3 py-2">
              {suggestedTopic}
            </p>
          )}
        </div>

        {/* Trigger Button */}
        <button
          onClick={handleTrigger}
          disabled={isRunning || triggering}
          className="w-full flex items-center justify-center gap-2 bg-purple-600 hover:bg-purple-700 disabled:opacity-50 text-white rounded-xl py-3 text-sm font-medium transition-colors"
        >
          {triggering ? (
            <Loader2 className="w-4 h-4 animate-spin" />
          ) : (
            <Play className="w-4 h-4" fill="currentColor" />
          )}
          {isRunning ? "Pipeline Running..." : triggering ? "Triggering..." : "Generate Video"}
        </button>

        {message && (
          <p className={`text-sm ${message.startsWith("Error") ? "text-red-400" : "text-green-400"}`}>
            {message}
          </p>
        )}
      </div>
    </div>
  );
}
