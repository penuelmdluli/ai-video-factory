import { useEffect, useState } from "react";
import { Calendar, Save, Loader2 } from "lucide-react";
import { api } from "../lib/api";
import type { Schedule as ScheduleType } from "../lib/types";

export function Schedule() {
  const [schedule, setSchedule] = useState<ScheduleType>({});
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.getSchedule().then((s) => { setSchedule(s); setLoading(false); }).catch(() => setLoading(false));
  }, []);

  const handleChange = (niche: string, field: "long_form" | "shorts", value: number) => {
    setSchedule((prev) => ({
      ...prev,
      [niche]: { ...prev[niche], [field]: Math.max(0, Math.min(5, value)) },
    }));
  };

  const handleSave = async () => {
    setSaving(true);
    setMessage("");
    try {
      const payload: Record<string, { long_form: number; shorts: number }> = {};
      for (const [key, val] of Object.entries(schedule)) {
        payload[key] = { long_form: val.long_form, shorts: val.shorts };
      }
      await api.updateSchedule(payload);
      setMessage("Schedule saved!");
      setTimeout(() => setMessage(""), 3000);
    } catch {
      setMessage("Failed to save");
    }
    setSaving(false);
  };

  const totalPerDay = Object.values(schedule).reduce((sum, v) => sum + v.long_form + v.shorts, 0);

  if (loading) return <div className="text-center py-12 text-slate-500">Loading...</div>;

  return (
    <div className="space-y-6 max-w-2xl">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold text-white flex items-center gap-2">
          <Calendar className="w-5 h-5 text-purple-400" /> Schedule
        </h2>
        <button
          onClick={handleSave}
          disabled={saving}
          className="flex items-center gap-1.5 px-3 py-1.5 bg-purple-600 hover:bg-purple-700 disabled:opacity-50 text-white rounded-lg text-sm"
        >
          {saving ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Save className="w-3.5 h-3.5" />}
          Save
        </button>
      </div>

      {message && <p className={`text-sm ${message.includes("Failed") ? "text-red-400" : "text-green-400"}`}>{message}</p>}

      <div className="bg-[#1e293b] rounded-xl border border-[#334155] overflow-hidden">
        <table className="w-full">
          <thead>
            <tr className="border-b border-[#334155]">
              <th className="text-left text-xs text-slate-500 uppercase tracking-wider p-4">Niche</th>
              <th className="text-center text-xs text-slate-500 uppercase tracking-wider p-4">Long-form / day</th>
              <th className="text-center text-xs text-slate-500 uppercase tracking-wider p-4">Shorts / day</th>
              <th className="text-center text-xs text-slate-500 uppercase tracking-wider p-4">Total</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-[#334155]">
            {Object.entries(schedule).map(([key, val]) => (
              <tr key={key}>
                <td className="p-4">
                  <p className="text-sm text-white font-medium">{val.name}</p>
                  <p className="text-xs text-slate-500">{key}</p>
                </td>
                <td className="p-4 text-center">
                  <input
                    type="number"
                    value={val.long_form}
                    onChange={(e) => handleChange(key, "long_form", parseInt(e.target.value) || 0)}
                    min={0} max={5}
                    className="w-16 bg-[#0f172a] border border-[#334155] rounded-lg px-2 py-1.5 text-center text-sm text-white focus:outline-none focus:border-purple-500"
                  />
                </td>
                <td className="p-4 text-center">
                  <input
                    type="number"
                    value={val.shorts}
                    onChange={(e) => handleChange(key, "shorts", parseInt(e.target.value) || 0)}
                    min={0} max={5}
                    className="w-16 bg-[#0f172a] border border-[#334155] rounded-lg px-2 py-1.5 text-center text-sm text-white focus:outline-none focus:border-purple-500"
                  />
                </td>
                <td className="p-4 text-center">
                  <span className="text-sm text-slate-300 font-medium">{val.long_form + val.shorts}</span>
                </td>
              </tr>
            ))}
          </tbody>
          <tfoot>
            <tr className="border-t border-[#334155] bg-[#0f172a]/50">
              <td className="p-4 text-sm text-slate-400 font-medium">Grand Total</td>
              <td colSpan={2} />
              <td className="p-4 text-center text-sm text-white font-bold">{totalPerDay} / day</td>
            </tr>
          </tfoot>
        </table>
      </div>

      {/* Cron Info */}
      <div className="bg-[#1e293b] rounded-xl border border-[#334155] p-4">
        <h3 className="text-sm font-medium text-slate-300 mb-2">Cron Schedule</h3>
        <p className="text-xs text-slate-500">
          Cloudflare Worker triggers the pipeline at <span className="text-slate-300">6:00 AM UTC</span> and <span className="text-slate-300">4:00 PM UTC</span> daily.
        </p>
      </div>
    </div>
  );
}
