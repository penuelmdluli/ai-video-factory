import { BrowserRouter, Routes, Route, Navigate, Outlet } from "react-router-dom";
import { Sidebar } from "./components/Sidebar";
import { Login } from "./pages/Login";
import { Dashboard } from "./pages/Dashboard";
import { Videos } from "./pages/Videos";
import { Pipeline } from "./pages/Pipeline";
import { Schedule } from "./pages/Schedule";
import { Uploads } from "./pages/Uploads";
import { Health } from "./pages/Health";
import { Settings } from "./pages/Settings";
import { Logs } from "./pages/Logs";

function ProtectedLayout() {
  const token = localStorage.getItem("avf_token");
  if (!token) return <Navigate to="/login" replace />;

  return (
    <div className="flex min-h-screen">
      <Sidebar />
      <main className="flex-1 p-6 overflow-auto">
        <Outlet />
      </main>
    </div>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route element={<ProtectedLayout />}>
          <Route path="/" element={<Dashboard />} />
          <Route path="/videos" element={<Videos />} />
          <Route path="/pipeline" element={<Pipeline />} />
          <Route path="/schedule" element={<Schedule />} />
          <Route path="/uploads" element={<Uploads />} />
          <Route path="/health" element={<Health />} />
          <Route path="/settings" element={<Settings />} />
          <Route path="/logs" element={<Logs />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}
