import { NavLink } from "react-router-dom";
import {
  LayoutDashboard, Film, Play, Calendar, Upload, Heart,
  Settings, ScrollText, LogOut,
} from "lucide-react";

const links = [
  { to: "/", icon: LayoutDashboard, label: "Dashboard" },
  { to: "/videos", icon: Film, label: "Videos" },
  { to: "/pipeline", icon: Play, label: "Pipeline" },
  { to: "/schedule", icon: Calendar, label: "Schedule" },
  { to: "/uploads", icon: Upload, label: "Uploads" },
  { to: "/health", icon: Heart, label: "Health" },
  { to: "/settings", icon: Settings, label: "Settings" },
  { to: "/logs", icon: ScrollText, label: "Logs" },
];

export function Sidebar() {
  return (
    <aside className="w-56 min-h-screen bg-[#1e293b] border-r border-[#334155] flex flex-col">
      <div className="p-4 border-b border-[#334155]">
        <h1 className="text-lg font-bold text-white flex items-center gap-2">
          <Play className="w-5 h-5 text-purple-400" fill="currentColor" />
          Video Factory
        </h1>
        <p className="text-xs text-slate-400 mt-0.5">AI Video Dashboard</p>
      </div>

      <nav className="flex-1 p-2 space-y-0.5">
        {links.map(({ to, icon: Icon, label }) => (
          <NavLink
            key={to}
            to={to}
            end={to === "/"}
            className={({ isActive }) =>
              `flex items-center gap-3 px-3 py-2 rounded-lg text-sm transition-colors ${
                isActive
                  ? "bg-purple-500/20 text-purple-300"
                  : "text-slate-400 hover:text-white hover:bg-white/5"
              }`
            }
          >
            <Icon className="w-4 h-4" />
            {label}
          </NavLink>
        ))}
      </nav>

      <div className="p-2 border-t border-[#334155]">
        <button
          onClick={() => {
            localStorage.removeItem("avf_token");
            window.location.href = "/login";
          }}
          className="flex items-center gap-3 px-3 py-2 rounded-lg text-sm text-slate-400 hover:text-white hover:bg-white/5 w-full"
        >
          <LogOut className="w-4 h-4" />
          Logout
        </button>
      </div>
    </aside>
  );
}
