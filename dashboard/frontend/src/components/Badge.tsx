interface Props {
  children: React.ReactNode;
  variant?: "success" | "error" | "warning" | "info" | "default" | "niche";
  niche?: string;
}

const variantClasses: Record<string, string> = {
  success: "bg-green-500/15 text-green-400 border-green-500/30",
  error: "bg-red-500/15 text-red-400 border-red-500/30",
  warning: "bg-amber-500/15 text-amber-400 border-amber-500/30",
  info: "bg-blue-500/15 text-blue-400 border-blue-500/30",
  default: "bg-slate-500/15 text-slate-400 border-slate-500/30",
};

const nicheClasses: Record<string, string> = {
  ai_trading: "bg-green-500/15 text-green-400 border-green-500/30",
  ai_money: "bg-blue-500/15 text-blue-400 border-blue-500/30",
  tech_news: "bg-purple-500/15 text-purple-400 border-purple-500/30",
};

export function Badge({ children, variant = "default", niche }: Props) {
  const cls = niche ? (nicheClasses[niche] || variantClasses.default) : variantClasses[variant];
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded-md text-xs font-medium border ${cls}`}>
      {children}
    </span>
  );
}
