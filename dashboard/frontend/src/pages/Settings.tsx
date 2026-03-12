import { useEffect, useState } from "react";
import { Settings as SettingsIcon, Key, Mic, Palette, Boxes } from "lucide-react";
import { api } from "../lib/api";
import { Badge } from "../components/Badge";

type Tab = "keys" | "voice" | "effects" | "niches";

export function Settings() {
  const [tab, setTab] = useState<Tab>("keys");
  const [settings, setSettings] = useState<Record<string, unknown> | null>(null);
  const [niches, setNiches] = useState<Record<string, unknown> | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      api.getSettings().then(setSettings),
      api.getNiches().then(setNiches),
    ]).finally(() => setLoading(false));
  }, []);

  if (loading) return <div className="text-center py-12 text-slate-500">Loading...</div>;

  const apiKeys = (settings?.api_keys || {}) as Record<string, { set: boolean; masked: string }>;
  const voice = (settings?.voice || {}) as Record<string, string>;
  const features = (settings?.features || {}) as Record<string, boolean>;

  const tabs: { key: Tab; label: string; icon: React.ReactNode }[] = [
    { key: "keys", label: "API Keys", icon: <Key className="w-3.5 h-3.5" /> },
    { key: "voice", label: "Voice", icon: <Mic className="w-3.5 h-3.5" /> },
    { key: "effects", label: "Effects", icon: <Palette className="w-3.5 h-3.5" /> },
    { key: "niches", label: "Niches", icon: <Boxes className="w-3.5 h-3.5" /> },
  ];

  return (
    <div className="space-y-6">
      <h2 className="text-lg font-semibold text-white flex items-center gap-2">
        <SettingsIcon className="w-5 h-5 text-purple-400" /> Settings
      </h2>

      {/* Tabs */}
      <div className="flex gap-1 bg-[#1e293b] rounded-lg p-1 border border-[#334155] w-fit">
        {tabs.map((t) => (
          <button
            key={t.key}
            onClick={() => setTab(t.key)}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md text-sm transition-colors ${
              tab === t.key ? "bg-purple-500/20 text-purple-300" : "text-slate-400 hover:text-white"
            }`}
          >
            {t.icon} {t.label}
          </button>
        ))}
      </div>

      {/* Tab Content */}
      <div className="bg-[#1e293b] rounded-xl border border-[#334155] p-6">
        {tab === "keys" && (
          <div className="space-y-3">
            <p className="text-xs text-slate-500 mb-4">API keys are configured in the .env file. Values shown are masked for security.</p>
            {Object.entries(apiKeys).map(([key, val]) => (
              <div key={key} className="flex items-center justify-between bg-[#0f172a] rounded-lg px-4 py-3">
                <div>
                  <p className="text-sm text-white capitalize">{key.replace("_", " ")}</p>
                  <p className="text-xs text-slate-500 font-mono">{val.masked || "Not set"}</p>
                </div>
                <Badge variant={val.set ? "success" : "error"}>
                  {val.set ? "Set" : "Not Set"}
                </Badge>
              </div>
            ))}
          </div>
        )}

        {tab === "voice" && (
          <div className="space-y-3">
            <div className="bg-[#0f172a] rounded-lg px-4 py-3">
              <p className="text-xs text-slate-500">YouTube Long-form Engine</p>
              <p className="text-sm text-white mt-0.5">{voice.youtube_long}</p>
            </div>
            <div className="bg-[#0f172a] rounded-lg px-4 py-3">
              <p className="text-xs text-slate-500">Shorts Engine</p>
              <p className="text-sm text-white mt-0.5">{voice.shorts}</p>
            </div>
            <div className="bg-[#0f172a] rounded-lg px-4 py-3">
              <p className="text-xs text-slate-500">Edge-TTS Default Voice</p>
              <p className="text-sm text-white mt-0.5">{voice.edge_default}</p>
            </div>
            <div className="bg-[#0f172a] rounded-lg px-4 py-3">
              <p className="text-xs text-slate-500">ElevenLabs Voice ID</p>
              <p className="text-sm text-white font-mono mt-0.5">{voice.elevenlabs_voice_id}</p>
            </div>
          </div>
        )}

        {tab === "effects" && (
          <div className="space-y-3">
            {Object.entries(features).map(([key, enabled]) => (
              <div key={key} className="flex items-center justify-between bg-[#0f172a] rounded-lg px-4 py-3">
                <p className="text-sm text-white capitalize">{key.replace("_", " ")}</p>
                <Badge variant={enabled ? "success" : "default"}>
                  {enabled ? "Enabled" : "Disabled"}
                </Badge>
              </div>
            ))}
            <div className="bg-[#0f172a] rounded-lg px-4 py-3">
              <p className="text-xs text-slate-500">Caption Font Size</p>
              <p className="text-sm text-white mt-0.5">{String((settings?.captions as Record<string, unknown>)?.font_size ?? "")}px</p>
            </div>
            <div className="bg-[#0f172a] rounded-lg px-4 py-3">
              <p className="text-xs text-slate-500">Caption Max Words</p>
              <p className="text-sm text-white mt-0.5">{String((settings?.captions as Record<string, unknown>)?.max_words ?? "")} words</p>
            </div>
          </div>
        )}

        {tab === "niches" && niches && (
          <div className="space-y-4">
            {Object.entries(niches).map(([key, val]) => {
              const niche = val as Record<string, unknown>;
              return (
                <div key={key} className="bg-[#0f172a] rounded-lg p-4">
                  <div className="flex items-center justify-between mb-2">
                    <p className="text-sm text-white font-medium">{niche.name as string}</p>
                    <span className="text-xs text-slate-500">{key}</span>
                  </div>
                  <div className="grid grid-cols-2 gap-2 text-xs">
                    <div>
                      <span className="text-slate-500">CPM:</span>
                      <span className="text-white ml-1">${niche.cpm_estimate as number}</span>
                    </div>
                    <div>
                      <span className="text-slate-500">Topics:</span>
                      <span className="text-white ml-1">{niche.topics_count as number}</span>
                    </div>
                    <div>
                      <span className="text-slate-500">Charts:</span>
                      <Badge variant={(niche.generate_charts as boolean) ? "success" : "default"}>
                        {(niche.generate_charts as boolean) ? "Yes" : "No"}
                      </Badge>
                    </div>
                    <div>
                      <span className="text-slate-500">Voice:</span>
                      <span className="text-white ml-1 font-mono text-[10px]">{niche.edge_voice as string}</span>
                    </div>
                  </div>
                  {(niche.hashtags as string[])?.length > 0 && (
                    <div className="flex flex-wrap gap-1 mt-2">
                      {(niche.hashtags as string[]).slice(0, 6).map((h) => (
                        <span key={h} className="text-[10px] text-purple-400 bg-purple-500/10 px-1.5 py-0.5 rounded">{h}</span>
                      ))}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
