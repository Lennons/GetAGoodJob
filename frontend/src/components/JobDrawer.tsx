import type { Job } from "../types";

function statusTag(s: string) {
  if (["sent", "chat_started"].includes(s)) return "tag-sent";
  if (["skipped", "skip"].includes(s)) return "tag-skip";
  if (s === "error") return "tag-err";
  if (s === "evaluated") return "tag-eval";
  return "";
}

function cleanReason(r: string) {
  return String(r || "").replace(/:\s*['"]?\w+_not_found['"]?/g, "").replace(/:\s*'NoneType'.*/g, "").replace(/:\s*name\s+'re'.*/g, "").replace(/:\s*job_card_not_found/g, "").replace(/：\s*job_card_not_found/g, "");
}

export default function JobDrawer({ job, onClose }: { job: Job | null; onClose: () => void }) {
  if (!job) return null;
  const s = job.status || job.decision || "";
  const ts = job.created_at ? job.created_at.slice(0, 16).replace("T", " ") : "−";

  return (
    <>
      <div className={`drawer-overlay${job ? " open" : ""}`} onClick={onClose} />
      <div className={`drawer${job ? " open" : ""}`}>
        <div className="drawer-header">
          <h3>{job.title || "岗位详情"}</h3>
          <button className="drawer-close" onClick={onClose}>&times;</button>
        </div>
        <div className="drawer-body">
          <div className="job-detail-score">{job.score} <span style={{ fontSize: 14, color: "var(--text-secondary)" }}>分</span></div>
          <div className="job-detail-meta">
            <span className={`tag ${statusTag(s)}`}>{s || "−"}</span>
            <span style={{ fontSize: 12, color: "var(--text-secondary)" }}>{job.company || "−"}</span>
            <span style={{ fontSize: 12, color: "var(--text-secondary)" }}>{job.city || ""} · {job.salary || ""}</span>
            <span style={{ fontSize: 12, color: "var(--text-muted)" }}>采集于 {ts}</span>
          </div>
          {job.url && <a href={job.url} target="_blank" rel="noreferrer" style={{ fontSize: 12, color: "var(--primary)" }}>在 BOSS 直聘查看 →</a>}
          {(job.reasons || []).filter(r => r).length > 0 && (
            <div className="job-detail-section">
              <h4>跳过原因</h4>
              {job.reasons.filter(r => r).map((r, i) => <div key={i} className="job-detail-reason">{cleanReason(r)}</div>)}
            </div>
          )}
          {(job.risks || []).filter(r => r).length > 0 && (
            <div className="job-detail-section">
              <h4>风险提示</h4>
              {job.risks.filter(r => r).map((r, i) => <div key={i} className="job-detail-risk">{cleanReason(r)}</div>)}
            </div>
          )}
          {job.initial_message && (
            <div className="job-detail-section">
              <h4>AI 开场白</h4>
              <div className="job-detail-msg">{job.initial_message}</div>
            </div>
          )}
          {job.description && (
            <div className="job-detail-section">
              <h4>职位描述</h4>
              <div className="job-detail-desc">{job.description}</div>
            </div>
          )}
        </div>
      </div>
    </>
  );
}
