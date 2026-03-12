import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Play, Lock } from "lucide-react";
import { api } from "../lib/api";

export function Login() {
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError("");
    try {
      const { token } = await api.login(password);
      localStorage.setItem("avf_token", token);
      navigate("/");
    } catch {
      setError("Invalid password");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-[#0f172a]">
      <div className="w-full max-w-sm">
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-14 h-14 rounded-2xl bg-purple-500/20 mb-4">
            <Play className="w-7 h-7 text-purple-400" fill="currentColor" />
          </div>
          <h1 className="text-2xl font-bold text-white">Video Factory</h1>
          <p className="text-sm text-slate-400 mt-1">AI Video Dashboard</p>
        </div>

        <form onSubmit={handleSubmit} className="bg-[#1e293b] rounded-xl border border-[#334155] p-6 space-y-4">
          <div>
            <label className="block text-sm text-slate-400 mb-1.5">Password</label>
            <div className="relative">
              <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500" />
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="Enter dashboard password"
                className="w-full bg-[#0f172a] border border-[#334155] rounded-lg pl-10 pr-4 py-2.5 text-sm text-white placeholder-slate-500 focus:outline-none focus:border-purple-500"
                autoFocus
              />
            </div>
          </div>

          {error && <p className="text-sm text-red-400">{error}</p>}

          <button
            type="submit"
            disabled={loading || !password}
            className="w-full bg-purple-600 hover:bg-purple-700 disabled:opacity-50 text-white rounded-lg py-2.5 text-sm font-medium transition-colors"
          >
            {loading ? "Signing in..." : "Sign In"}
          </button>
        </form>
      </div>
    </div>
  );
}
