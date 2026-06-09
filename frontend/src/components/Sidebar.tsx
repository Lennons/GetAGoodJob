import { useEffect, useState } from "react";
import { api } from "../api";
import type { PageName } from "../types";

const PAGES: { key: PageName; label: string }[] = [
  { key: "dashboard", label: "自动投递" },
  { key: "settings", label: "设置中心" },
  { key: "datacenter", label: "数据中心" },
];

export default function Sidebar({ page, onNavigate }: { page: PageName; onNavigate: (p: PageName) => void }) {
  const [version, setVersion] = useState("?");
  const [cdpConnected, setCdpConnected] = useState(false);

  useEffect(() => {
    api.version().then(v => setVersion(v.version || "?")).catch(() => {});
  }, []);

  useEffect(() => {
    const iv = setInterval(async () => {
      try {
        const r = await api.browserStatus();
        setCdpConnected(!!r.running);
      } catch { setCdpConnected(false); }
    }, 3000);
    return () => clearInterval(iv);
  }, []);

  return (
    <aside className="sidebar">
      <div className="sidebar-brand">
        <h1>工作通</h1>
        <span>BOSS Chat Assistant</span>
      </div>
      <nav className="sidebar-nav">
        {PAGES.map(p => (
          <button
            key={p.key}
            className={`nav-item${page === p.key ? " active" : ""}`}
            onClick={() => onNavigate(p.key)}
          >
            <span className="nav-dot" />
            {p.label}
          </button>
        ))}
      </nav>
      <div className="sidebar-footer">
        <div className="cdp-label">Chrome CDP</div>
        <div className="cdp-val">{cdpConnected ? "已连接" : "未连接"}</div>
        <div className="cdp-hint">Profile 登录态持久化</div>
        <div className="cdp-val" style={{ marginTop: 4, fontSize: 12 }}>v{version}</div>
      </div>
    </aside>
  );
}
