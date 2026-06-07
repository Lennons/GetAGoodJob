/* ═══════════════════════════════════════════════
   工作通 — Frontend (Figma SaaS Dashboard)
   ═══════════════════════════════════════════════ */
const api = async (path, opts = {}) => {
  const r = await fetch(path, { ...opts, headers: { "Content-Type": "application/json", ...(opts.headers || {}) } });
  if (!r.ok) throw new Error(await r.text());
  return r.json();
};
const $ = id => document.getElementById(id);
const $$ = (sel, root) => (root || document).querySelectorAll(sel);

const FIELDS = ["api_base_url","model","daily_chat_limit","cooldown_min_ms","cooldown_max_ms","min_score_to_chat","salary_expectation","target_city","target_job_keyword","target_cities","target_roles","preferred_keywords","blocked_keywords","auto_send_initial","auto_reply","stop_on_risk_prompt","allow_contact_info_in_messages"];
function splitList(v) { return String(v||"").split(/[,，\n]/).map(s=>s.trim()).filter(Boolean); }
function joinList(v) { return Array.isArray(v)?v.join("，"):v||""; }

let timer = null, running = false, batchId = "", lastVer = "", loading = false;

// ── Mode switching ────────────────────────────
function getMode() { const c = document.querySelector('input[name="pw-mode"]:checked'); return c?c.value:"expected"; }
function getSearch() { return $("pw-search-keyword").value.trim(); }

function updateModeUI() {
  const m = getMode();
  $$(".mode-card").forEach(c => c.classList.toggle("selected", c.querySelector("input").value === m));
  $("search-box").style.display = m === "search" ? "flex" : "none";
}
$$(".mode-card").forEach(c => c.addEventListener("click", () => { c.querySelector("input").checked = true; updateModeUI(); }));

// ── Sidebar navigation ────────────────────────
$$(".nav-item").forEach(b => {
  b.addEventListener("click", () => {
    $$(".nav-item").forEach(x => x.classList.remove("active"));
    b.classList.add("active");
    const nav = b.dataset.nav;
    if (nav === "settings") openDrawer();
    else if (nav === "resume") openDrawer();
    else if (nav === "events") { document.querySelector(".card:nth-child(4)").scrollIntoView({behavior:"smooth"}); }
    else if (nav === "jobs") { document.querySelector(".card:nth-child(5)").scrollIntoView({behavior:"smooth"}); }
  });
});

// ── Drawer ────────────────────────────────────
function openDrawer() { $("settings-drawer").classList.add("open"); $("drawer-overlay").classList.add("open"); loadResumes(); }
function closeDrawer() { $("settings-drawer").classList.remove("open"); $("drawer-overlay").classList.remove("open"); }
$("drawer-close").addEventListener("click", closeDrawer);
$("drawer-overlay").addEventListener("click", closeDrawer);

// ── Settings ──────────────────────────────────
async function loadSettings() {
  const s = await api("/api/settings");
  for (const k of FIELDS) { const el = $(k); if (!el) continue;
    if (el.type === "checkbox") el.checked = !!s[k];
    else if (Array.isArray(s[k])) el.value = joinList(s[k]);
    else el.value = s[k] ?? "";
  }
}
async function saveSettings() {
  const p = {};
  for (const k of FIELDS) { const el = $(k); if (!el) continue;
    if (el.type === "checkbox") p[k] = el.checked;
    else if (["target_cities","target_roles","preferred_keywords","blocked_keywords"].includes(k)) p[k] = splitList(el.value);
    else if (["daily_chat_limit","cooldown_min_ms","cooldown_max_ms","min_score_to_chat"].includes(k)) p[k] = Number(el.value || 0);
    else p[k] = el.value;
  }
  await api("/api/settings", { method: "PATCH", body: JSON.stringify(p) });
  await loadSettings(); closeDrawer();
}

// ── Health ────────────────────────────────────
async function checkHealth() {
  try {
    const h = await api("/api/health");
    const connected = h.browser_running;
    $("cdp-status").textContent = connected ? "9223 已连接" : "未连接";
    $("cdp-status").style.color = connected ? "#34D399" : "#94A3B8";
    const statusBadge = $("status-badge");
    if (connected) { statusBadge.className = "badge-status running"; $("status-text").textContent = "浏览器已连接"; }
    else { statusBadge.className = "badge-status idle"; $("status-text").textContent = "就绪"; }
  } catch(e) { $("cdp-status").textContent = "离线"; $("cdp-status").style.color = "#EF4444"; }
}

// ── Automation ────────────────────────────────
async function pwLaunch() {
  const btn = $("pw-launch"); btn.disabled = true; btn.textContent = "启动中…";
  try { await api("/api/setup/launch-browser", { method: "POST" }); $("progress-last").textContent = "浏览器已启动，请登录 BOSS 直聘"; }
  catch(e) { alert(e.message); }
  finally { btn.disabled = false; btn.textContent = "启动浏览器"; }
}
async function pwStart() {
  if (running) return;
  const mode = getMode(), kw = getSearch();
  if (mode === "search" && !kw) { alert("请输入搜索关键词"); return; }
  try {
    const r = await api("/api/automation/playwright/start", { method: "POST", body: JSON.stringify({ mode, search_keyword: kw }) });
    running = true; batchId = ""; lastVer = ""; $("jobs").innerHTML = "";
    $("status-badge").className = "badge-status running"; $("status-text").textContent = "任务运行中";
    $("progress-subtitle").textContent = "正在初始化…"; $("progress-last").textContent = "任务已启动";
    $("pw-start").disabled = true; timer = setInterval(poll, 1500);
  } catch(e) { alert(e.message); }
}
async function pwStop() {
  try { await api("/api/automation/playwright/stop", { method: "POST" }); stopRunning("手动停止"); }
  catch(e) { alert(e.message); }
}
async function pwCloseBrowser() {
  try { await api("/api/setup/stop-browser", { method: "POST" }); stopRunning("浏览器已断开"); }
  catch(e) { alert(e.message); }
}
function stopRunning(msg) {
  running = false; $("pw-start").disabled = false;
  $("status-badge").className = "badge-status idle"; $("status-text").textContent = msg || "就绪";
  $("progress-subtitle").textContent = msg || "就绪"; $("progress-pct").textContent = "−";
  $("progress-eta").textContent = ""; $("progress-last").textContent = msg || "就绪";
  $("pw-progress-fill").style.width = "0%";
  if (timer) { clearInterval(timer); timer = null; }
}
async function poll() {
  try {
    const d = await api("/api/automation/playwright/status"), s = d.stats || {};
    if (d.batch_id && d.batch_id !== batchId) { batchId = d.batch_id; lastVer = ""; await loadJobs(); }
    $("kpi-sent").textContent = s.sent || 0;
    $("kpi-skipped").textContent = s.skipped || 0;
    $("kpi-errors").textContent = s.errors || 0;
    const done = (s.sent||0)+(s.skipped||0)+(s.errors||0), total = s.total || 0;
    $("kpi-progress").textContent = done ? `${done}/${total}` : "0/0";
    if (d.message) {
      $("progress-subtitle").textContent = d.message;
      $("progress-last").textContent = d.message;
      $("kpi-event").textContent = d.message.slice(0,40);
    }
    if (total > 0) { const pct = Math.min(100, Math.round(done/total*100)); $("pw-progress-fill").style.width = pct+"%"; $("progress-pct").textContent = pct+"%"; }
    if (!d.running && running) { stopRunning(d.status === "completed" ? "完成" : "已停止"); await loadJobs(); }
    await checkVer();
    // Quota
    try { const q = await api("/api/automation/quota"); $("kpi-quota").textContent = `${q.used||0} / ${q.limit||0}`; } catch(e) {}
  } catch(e) {}
}

// ── Jobs ──────────────────────────────────────
async function loadJobs() {
  let url = "/api/jobs?limit=500"; if (batchId) url += "&batch_id=" + encodeURIComponent(batchId);
  const jobs = await api(url);
  const statusTag = s => ["sent","chat_started"].includes(s) ? "tag-sent" : ["skipped","skip"].includes(s) ? "tag-skip" : s === "error" ? "tag-err" : s === "evaluated" ? "tag-eval" : "";
  $("jobs").innerHTML = jobs.map(j => {
    const s = j.status||j.decision||"", reasons = (j.reasons||[]).filter(r=>r).join("；");
    const risks = (j.risks||[]).map(r=>"⚠"+r).join("；"), note = [reasons,risks].filter(Boolean).join(" ").slice(0,120);
    return `<tr><td class="score">${j.score}</td><td><span class="tag ${statusTag(s)}">${s||"−"}</span></td><td><a href="${j.url||'#'}" target="_blank">${(j.title||"岗位").slice(0,40)}</a></td><td>${j.company||"−"}</td><td style="font-size:12px;color:var(--text-secondary)">${note||j.initial_message||""}</td></tr>`;
  }).join("");
  $("job-header-count").textContent = `${jobs.length} 条记录`;
  // Message preview
  const msgs = jobs.filter(j => j.initial_message && j.status !== "skipped").slice(0, 5);
  if (msgs.length) {
    $("msg-preview-hint").textContent = `最近 ${msgs.length} 条开工白`;
    $("msg-preview").innerHTML = msgs.map(j => `<div style="padding:8px 0;border-bottom:1px solid var(--border-light);font-size:12px"><strong style="color:var(--primary)">${(j.title||"").slice(0,30)}</strong><br><span style="color:var(--text-secondary)">${(j.initial_message||"").slice(0,80)}</span></div>`).join("");
  }
}
async function checkVer() {
  if (loading) return;
  let url = "/api/jobs/version"; if (batchId) url += "?batch_id=" + encodeURIComponent(batchId);
  const v = await api(url), token = `${v.batch_id||""}|${v.count||0}|${v.latest_updated_at||""}`;
  if (token === lastVer) return; lastVer = token; loading = true;
  try { await loadJobs(); } finally { loading = false; }
}

// ── Events ────────────────────────────────────
async function loadEvents() {
  try {
    const events = await api("/api/events?limit=20");
    $("events").innerHTML = events.map(e => `<div class="event-item"><span class="event-time">${(e.created_at||"").slice(-8)||"--:--:--"}</span><span class="event-msg">${e.type}: ${JSON.stringify(e.payload||{}).slice(0,80)}</span></div>`).join("");
  } catch(e) {}
}

// ── Resumes ───────────────────────────────────
async function uploadResume(e) { e.preventDefault();
  const inp = $("resume-file"); if (!inp.files?.[0]) return;
  const fd = new FormData(); fd.append("file", inp.files[0]);
  await fetch("/api/resumes/upload", { method: "POST", body: fd }); inp.value = ""; await loadResumes();
}
async function analyzeText() {
  const t = $("resume-text").value.trim(); if (!t) return;
  await api("/api/resumes/text", { method: "POST", body: JSON.stringify({ text:t, filename:"paste.txt" }) });
  $("resume-text").value = ""; await loadResumes();
}
async function activateResume(id) { await api(`/api/resumes/${id}/activate`, { method: "POST" }); await loadResumes(); }
async function loadResumes() {
  const resumes = await api("/api/resumes");
  $("resumes").innerHTML = resumes.map(r => {
    const name = r.analysis?.name || r.filename || "未命名", skills = (r.analysis?.core_skills||[]).slice(0,4).join("、");
    return `<div class="resume-card"><span class="rname">${name}${r.is_active?' <span class="rtag">当前</span>':''}</span><span class="rskills">${skills}</span><button class="btn btn-ghost btn-sm" ${r.is_active?'disabled':''}>${r.is_active?'已设':'启用'}</button></div>`;
  }).join("");
  $$(".resume-card button").forEach((btn,i) => { btn.addEventListener("click", () => activateResume(resumes[i].id)); });
}

// ── Init ──────────────────────────────────────
async function init() { await checkHealth(); await loadSettings(); await loadJobs(); await loadEvents(); }

$("pw-launch").addEventListener("click", () => pwLaunch());
$("pw-start").addEventListener("click", () => pwStart());
$("pw-stop").addEventListener("click", () => pwStop());
$("pw-close-browser").addEventListener("click", () => pwCloseBrowser());
$("save-settings").addEventListener("click", () => saveSettings());
$("upload-form").addEventListener("submit", e => uploadResume(e));
$("analyze-text").addEventListener("click", () => analyzeText());
$("event-mini").addEventListener("click", () => loadEvents());

init(); updateModeUI();
setInterval(checkHealth, 8000);
setInterval(checkVer, 2000);
setInterval(loadEvents, 5000);
