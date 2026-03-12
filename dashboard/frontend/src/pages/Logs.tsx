import { useRef, useEffect, useState } from "react";
import { ScrollText, Wifi, WifiOff, Trash2, ArrowDown } from "lucide-react";
import { useLiveLogs } from "../hooks/use-websocket";

export function Logs() {
  const { logs, connected, clearLogs } = useLiveLogs();
  const [autoScroll, setAutoScroll] = useState(true);
  const [filter, setFilter] = useState<"all" | "info" | "error">("all");
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (autoScroll && containerRef.current) {
      containerRef.current.scrollTop = containerRef.current.scrollHeight;
    }
  }, [logs, autoScroll]);

  const filteredLogs = logs.filter((log) => {
    if (filter === "all") return true;
    if (filter === "error") return /error|fail|exception/i.test(log.message);
    if (filter === "info") return /\[/.test(log.message);
    return true;
  });

  const getLineColor = (msg: string) => {
    if (/error|fail|exception/i.test(msg)) return "text-red-400";
    if (/ok|success|complete|generated|uploaded/i.test(msg)) return "text-green-400";
    if (/retry|warn|skip/i.test(msg)) return "text-amber-400";
    if (/\[\d+\/\d+\]/.test(msg)) return "text-blue-400";
    return "text-slate-300";
  };

  return (
    <div className="space-y-4 h-[calc(100vh-8rem)] flex flex-col">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold text-white flex items-center gap-2">
          <ScrollText className="w-5 h-5 text-purple-400" /> Live Logs
        </h2>
        <div className="flex items-center gap-3">
          {/* Connection Status */}
          <div className="flex items-center gap-1.5">
            {connected ? (
              <>
                <Wifi className="w-3.5 h-3.5 text-green-400" />
                <span className="text-xs text-green-400">Connected</span>
              </>
            ) : (
              <>
                <WifiOff className="w-3.5 h-3.5 text-red-400" />
                <span className="text-xs text-red-400">Disconnected</span>
              </>
            )}
          </div>

          {/* Filter */}
          <select
            value={filter}
            onChange={(e) => setFilter(e.target.value as typeof filter)}
            className="bg-[#1e293b] border border-[#334155] rounded-lg px-2 py-1 text-xs text-slate-300 focus:outline-none"
          >
            <option value="all">All</option>
            <option value="info">Info</option>
            <option value="error">Errors</option>
          </select>

          <button onClick={() => setAutoScroll(!autoScroll)}
            className={`p-1.5 rounded-lg border text-xs ${autoScroll ? "border-purple-500/50 text-purple-300" : "border-[#334155] text-slate-500"}`}>
            <ArrowDown className="w-3.5 h-3.5" />
          </button>

          <button onClick={clearLogs} className="p-1.5 rounded-lg border border-[#334155] text-slate-500 hover:text-white">
            <Trash2 className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>

      {/* Log Output */}
      <div
        ref={containerRef}
        className="flex-1 bg-[#0c1222] rounded-xl border border-[#334155] p-4 overflow-auto font-mono text-xs leading-relaxed"
      >
        {filteredLogs.length === 0 ? (
          <div className="text-slate-600 text-center py-12">
            {connected ? "Waiting for log output..." : "Connecting to log stream..."}
          </div>
        ) : (
          filteredLogs.map((log, i) => (
            <div key={i} className="flex gap-3 hover:bg-white/[0.02] px-1 py-0.5 rounded">
              <span className="text-slate-600 flex-shrink-0 select-none">
                {new Date(log.timestamp).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" })}
              </span>
              <span className={getLineColor(log.message)}>{log.message}</span>
            </div>
          ))
        )}
      </div>

      <div className="text-xs text-slate-600 text-center">
        {filteredLogs.length} log entries {filter !== "all" && `(filtered from ${logs.length})`}
      </div>
    </div>
  );
}
