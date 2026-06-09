import { useState } from "react";
import Sidebar from "./components/Sidebar";
import Dashboard from "./pages/Dashboard";
import SettingsPage from "./pages/Settings";
import Datacenter from "./pages/Datacenter";
import type { PageName } from "./types";

export default function App() {
  const [page, setPage] = useState<PageName>("dashboard");
  return (
    <div className="app">
      <Sidebar page={page} onNavigate={setPage} />
      <main className="main">
        {page === "dashboard" && <Dashboard />}
        {page === "settings" && <SettingsPage />}
        {page === "datacenter" && <Datacenter />}
      </main>
    </div>
  );
}
