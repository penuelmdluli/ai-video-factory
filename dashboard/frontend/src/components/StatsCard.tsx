import type { ReactNode } from "react";

interface Props {
  label: string;
  value: string | number;
  icon: ReactNode;
  trend?: string;
  color?: string;
}

export function StatsCard({ label, value, icon, trend, color = "purple" }: Props) {
  const colorMap: Record<string, string> = {
    purple: "bg-purple-500/10 text-purple-400",
    green: "bg-green-500/10 text-green-400",
    blue: "bg-blue-500/10 text-blue-400",
    red: "bg-red-500/10 text-red-400",
    amber: "bg-amber-500/10 text-amber-400",
  };

  return (
    <div className="bg-[#1e293b] rounded-xl border border-[#334155] p-4">
      <div className="flex items-center justify-between mb-3">
        <span className="text-xs text-slate-400 uppercase tracking-wider">{label}</span>
        <div className={`w-8 h-8 rounded-lg flex items-center justify-center ${colorMap[color]}`}>
          {icon}
        </div>
      </div>
      <p className="text-2xl font-bold text-white">{value}</p>
      {trend && <p className="text-xs text-slate-400 mt-1">{trend}</p>}
    </div>
  );
}
