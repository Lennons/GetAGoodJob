"""
BOSS 直聘浏览器自动化 — JS 注入脚本 & 辅助函数。
从 automation_engine.py 提取，保持模块整洁。
"""

from __future__ import annotations

import json
import re
from typing import Any, Optional

# ── Regex patterns ─────────────────────────────────

from app.services.logger import get_logger

_logger = get_logger("engine")

RISK_PATTERNS = re.compile(
    r"(验证码|账号异常|请完成验证|滑块验证|行为验证|请稍后再试|"
    r"今日沟通次数已达上限|操作太频繁|"
    r"请先登录|当前登录状态已失效|登录失效|登录状态失效|重新登录|登录过期|登录超时|"
    r"请重新登录|身份过期|身份认证失败)",
    re.IGNORECASE,
)

LOGIN_URL_PATTERNS = re.compile(
    r"(/web/geek/login|/account/login|/login\b)",
    re.IGNORECASE,
)

LOGIN_PAGE_DETECT_JS = """(() => {
  const inputs = document.querySelectorAll('input[placeholder*="手机"], input[placeholder*="验证码"]');
  const text = (document.body.innerText || '').slice(0, 200);
  const hasLogin = inputs.length > 0 && (text.includes('登录') || text.includes('扫码') || text.includes('验证码登录'));
  return {url: location.href, hasLoginForm: hasLogin, inputs: inputs.length};
})()"""

HARD_DAILY_LIMIT = 80
MAX_SESSION_SEC = 25 * 60
LONG_BREAK_EVERY_N = 8
LONG_BREAK_MIN_SEC = 45
LONG_BREAK_MAX_SEC = 120
TARGET_JOBS_URL = "https://www.zhipin.com/web/geek/jobs?city=101040100"
TARGET_JOB_KEYWORD = "产品经理"
DEFAULT_CITY = "重庆"
MAX_EMPTY_SCROLL_ROUNDS = 5

# ── JS snippets ────────────────────────────────────

def _select_recommended_job_tab_js(label: str) -> str:
    target = json.dumps(label, ensure_ascii=False)
    return f"""
(() => {{
  const target = {target};
  const normalize = (text) => String(text || '').replace(/（/g, '(').replace(/）/g, ')').replace(/\\s+/g, '').trim();
  const visible = (el) => !!(el && (el.offsetWidth || el.offsetHeight || el.getClientRects().length));
  const nodes = Array.from(document.querySelectorAll('.c-expect-select a, .expect-list a, a.expect-item'));
  const matched = nodes.find((el) => {{
    if (!visible(el)) return false;
    const text = normalize(el.textContent);
    return text === normalize(target);
  }});
  if (!matched) return {{ ok: false, reason: 'not_found', target }};
  const clickable = matched.closest('a, button, [role="button"]') || matched;
  clickable.scrollIntoView?.({{ block: 'center', inline: 'center' }});
  clickable.click();
  return {{ ok: true, target, text: matched.textContent.trim(), url: location.href }};
}})()
"""

def _open_city_dialog_js() -> str:
    return """
(() => {
  const visible = (el) => !!(el && (el.offsetWidth || el.offsetHeight || el.getClientRects().length));
  const openDialog = Array.from(document.querySelectorAll('.city-select-dialog, .dialog-wrap.city-select-dialog')).find(visible);
  if (openDialog) {
    return { ok: true, alreadyOpen: true };
  }
  const el = Array.from(document.querySelectorAll('.city-label, .cur-city-label')).find(visible);
  if (!el) return { ok: false, reason: 'city_filter_not_found' };
  const clickable = el.closest('.city-label, button, a, [role="button"]') || el;
  clickable.scrollIntoView?.({ block: 'center', inline: 'center' });
  clickable.click();
  return { ok: true, text: clickable.textContent.trim() };
})()
"""

def _select_city_option_js(city: str) -> str:
    city_json = json.dumps(city, ensure_ascii=False)
    return f"""
(() => {{
  const city = {city_json};
  const normalize = (text) => String(text || '').replace(/\\s+/g, '').trim();
  const visible = (el) => !!(el && (el.offsetWidth || el.offsetHeight || el.getClientRects().length));
  const nodes = Array.from(document.querySelectorAll('.city-select-dialog li, .dialog-wrap.city-select-dialog li, .dialog-wrap li'));
  const matched = nodes.find((el) => visible(el) && normalize(el.textContent) === normalize(city));
  if (!matched) return {{ ok: false, reason: 'city_not_found', city }};
  matched.scrollIntoView?.({{ block: 'center', inline: 'center' }});
  matched.click();
  return {{ ok: true, city, text: matched.textContent.trim() }};
}})()
"""

def _norm_title(value: Any) -> str:
    return re.sub(r"[\s（）()【】\\[\\]·,，/\\-—_]+", "", str(value or "")).lower()

def _same_job_title(left: Any, right: Any) -> bool:
    a = _norm_title(left)
    b = _norm_title(right)
    if not a or not b:
        return True
    return a in b or b in a


def _select_job_card_js(source_key: str, url: str) -> str:
    source_json = json.dumps(source_key or "", ensure_ascii=False)
    url_json = json.dumps(url or "", ensure_ascii=False)
    return f"""
(() => {{
  const sourceKey = {source_json};
  const targetUrl = {url_json};
  const cleanUrl = (value) => String(value || '').split('?')[0];
  const visible = (el) => !!(el && (el.offsetWidth || el.offsetHeight || el.getClientRects().length));
  const links = Array.from(document.querySelectorAll('a.job-name[href*="/job_detail/"], a[href*="/job_detail/"]')).filter(visible);
  const matched = links.find((a) => cleanUrl(a.href) === cleanUrl(sourceKey) || cleanUrl(a.href) === cleanUrl(targetUrl));
  if (!matched) return {{ ok: false, reason: 'job_card_not_found', sourceKey, targetUrl }};
  matched.scrollIntoView?.({{ block: 'center', inline: 'center' }});
  matched.click();
  return {{ ok: true, title: matched.textContent.trim(), href: matched.href }};
}})()
"""


def _skip_evaluation(reason: str, *, score: int = 0, risks: Optional[list] = None) -> dict:
    return {
        "score": score,
        "decision": "skip",
        "status": "skipped",
        "reasons": [reason],
        "risks": risks or [],
        "best_resume_angle": "",
        "initial_message": "",
    }


def _looks_like_initial_message(value: Any) -> bool:
    text = str(value or "").strip()
    if not text:
        return False
    return bool(re.search(r"^(您好|你好|Hi|Hello)|我对.+感兴趣|期待沟通|方便的话", text, re.IGNORECASE))


def _mark_evaluation_skipped(evaluation: Optional[dict], reason: str) -> dict:
    result = dict(evaluation or {})
    # AI reasons first, technical/skip-line reason last
    reasons = []
    for item in result.get("reasons") or []:
        if item and item not in reasons and not _looks_like_initial_message(item):
            reasons.append(item)
    if reason and reason not in reasons:
        reasons.append(reason)
    result["decision"] = "skip"
    result["status"] = "skipped"
    result["reasons"] = reasons
    result["initial_message"] = ""
    return result


EXTRACT_JOB_LIST_JS = """
(() => {
  const visible = (el) => !!(el && (el.offsetWidth || el.offsetHeight || el.getClientRects().length));
  const clean = (text) => String(text || '').replace(/\\s+/g, ' ').trim();
  const jobs = [];
  const seen = new Set();
  const cards = Array.from(document.querySelectorAll('.job-card-box')).filter(visible);
  for (const card of cards) {
    const a = card.querySelector('a.job-name[href*="job_detail"], a[href*="/job_detail/"]');
    if (!a) continue;
    const href = a.href;
    if (!href || seen.has(href) || href.includes('#') || !href.includes('/job_detail/')) continue;
    seen.add(href);
    const title = clean(a.textContent);
    const salary = clean(card.querySelector('.job-salary, [class*="salary"]')?.textContent);
    const company = clean(card.querySelector('.boss-name, .company-name, [class*="company-name"], [class*="brand"]')?.textContent);
    const city = clean(card.querySelector('.company-location, [class*="location"], [class*="area"]')?.textContent);
    const tags = Array.from(card.querySelectorAll('.tag-list li')).map((li) => clean(li.textContent)).filter(Boolean);
    const text = clean(card.innerText);
    jobs.push({
      source_key: href.split('?')[0],
      url: href,
      title,
      salary,
      company,
      city,
      description: text,
      raw: { card_text: text, tags }
    });
  }
  return jobs;
})()
"""

SCROLL_JOB_LIST_JS = """
(() => {
  const visible = (el) => !!(el && (el.offsetWidth || el.offsetHeight || el.getClientRects().length));
  const cards = Array.from(document.querySelectorAll('.job-card-box')).filter(visible);
  const candidates = [
    document.querySelector('.job-list-container'),
    document.querySelector('.recommend-result-job'),
    document.querySelector('.recommend-result-inner'),
    document.scrollingElement,
    document.documentElement,
    document.body,
  ].filter(Boolean);
  for (const el of candidates) {
    try {
      const amount = Math.max(el.clientHeight || 0, 900);
      if (typeof el.scrollBy === 'function') {
        el.scrollBy({ top: amount, behavior: 'smooth' });
      } else {
        el.scrollTop = (el.scrollTop || 0) + amount;
      }
    } catch (e) {}
  }
  try { window.scrollBy({ top: 900, behavior: 'smooth' }); } catch (e) {}
  return { cardCount: cards.length, y: window.scrollY };
})()
"""

SEARCH_AND_SUBMIT_JS = """
(() => {
  const visible = (el) => !!(el && (el.offsetWidth || el.offsetHeight || el.getClientRects().length));
  const keyword = "KEYWORD_PLACEHOLDER";
  let input = document.querySelector('.c-search-input input, .job-search-form input, .expect-search-inner input[type="text"]');
  if (!input || !visible(input)) {
    input = Array.from(document.querySelectorAll('input[type="text"], input:not([type])')).find(
      (el) => visible(el) && /搜索|职位|公司|岗位/.test(el.placeholder || '')
    );
  }
  if (!input || !visible(input)) return { ok: false, reason: 'search_input_not_found', keyword };
  input.focus();
  input.value = '';
  input.dispatchEvent(new Event('focus', { bubbles: true }));
  const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value');
  if (setter && setter.set) { setter.set.call(input, keyword); }
  else { input.value = keyword; }
  input.dispatchEvent(new Event('input', { bubbles: true }));
  input.dispatchEvent(new Event('change', { bubbles: true }));
  input.dispatchEvent(new KeyboardEvent('keyup', { key: 'Unidentified', bubbles: true }));
  input.focus();
  return { ok: true, keyword, filled: true };
})()
"""

def _target_list_state_js(label: str, keyword: str) -> str:
    label_json = json.dumps(label, ensure_ascii=False)
    keyword_json = json.dumps(keyword, ensure_ascii=False)
    city_json = json.dumps(city, ensure_ascii=False)
    return f"""
(() => {{
  const label = {label_json};
  const keyword = {keyword_json};
  const city = {city_json};
  const findVmByName = (name) => {{
    const root = document.querySelector('#wrap')?.__vue__;
    const stack = root ? [root] : [];
    while (stack.length) {{
      const vm = stack.shift();
      if (vm?.$options?.name === name) return vm;
      stack.push(...(vm?.$children || []));
    }}
    return null;
  }};
  const normalize = (text) => String(text || '').replace(/（/g, '(').replace(/）/g, ')').replace(/\\s+/g, '').trim();
  const visible = (el) => !!(el && (el.offsetWidth || el.offsetHeight || el.getClientRects().length));
  const expectVm = findVmByName('vue-component-80-ExpectSelect') || document.querySelector('.c-expect-select')?.__vue__;
  const pageVm = findVmByName('PageJobs');
  const expectedId = expectVm?.encryptExpectId || expectVm?.expectList?.[0]?.encryptId || '';
  const pageExpectId = pageVm?.formData?.encryptExpectId || pageVm?.catchExpectId || '';
  const currentJobTab = expectVm?.currentJobTab || '';
  const recommend = document.querySelector('.c-expect-select a.synthesis, a.synthesis');
  const recommendActive = !!(recommend && /active|selected|current|cur/.test(String(recommend.className || '')));
  const expectNodes = Array.from(document.querySelectorAll('.c-expect-select a, .expect-list a, a.expect-item')).filter(visible);
  const expectActive = expectNodes.some((el) => normalize(el.textContent) === normalize(label) && /active|selected|current|cur/.test(String(el.className || '')));
  const cityLabel = normalize(document.querySelector('.cur-city-label')?.textContent || document.querySelector('.city-label')?.textContent || '');
  const citySelected = cityLabel === normalize(city);
  const topText = Array.from(document.querySelectorAll('.expect-and-search, .c-expect-select, .expect-list'))
    .filter(visible)
    .map((el) => normalize(el.innerText || el.textContent))
    .join('|');
  const cards = Array.from(document.querySelectorAll('.job-card-box')).filter(visible);
  const sampleTitles = cards.slice(0, 8).map((card) => normalize(card.querySelector('a.job-name')?.textContent || card.innerText));
  const sampleCards = cards.slice(0, 8).map((card) => normalize(card.innerText));
  const productLikeCount = sampleTitles.filter((title) => title.includes(keyword.replace(/\\s+/g, ''))).length;
  const cityLikeCount = sampleCards.filter((text) => text.includes('重庆')).length;
  const strictExpectActive = currentJobTab === 'expect' && !!expectedId && pageExpectId === expectedId && expectActive && citySelected;
  const visibleExpectActive = expectActive && citySelected && topText.includes(normalize(label)) && productLikeCount > 0;
  const targetListVisible = topText.includes(normalize(label)) && productLikeCount > 0;
  return {{
    ok: cards.length > 0 && citySelected && (strictExpectActive || (visibleExpectActive && targetListVisible)),
    url: location.href,
    topText,
    cityLabel,
    citySelected,
    cardCount: cards.length,
    productLikeCount,
    cityLikeCount,
    sampleTitles,
    currentJobTab,
    expectedId,
    pageExpectId,
    expectActive,
    recommendActive,
    strictExpectActive,
    visibleExpectActive,
    targetListVisible,
  }};
}})()
"""

EXTRACT_JOB_DETAIL_JS = """
(() => {
  const get = (sel) => { const el = document.querySelector(sel); return el ? el.textContent.trim() : ''; };

  let title = get('.job-name') || get('[class*="job-name"]') || get('.name');
  if (!title || title.length > 80) title = get('h1') || (document.title||'').split('招聘')[0] || '';
  title = title.replace(/\\n\\s+/g, ' ').trim().slice(0, 120);

  let company = get('.company-name') || get('[class*="company-name"]');
  if (!company || company === title) {
    const links = document.querySelectorAll('a[href*="company"]');
    for (const a of links) { const t = a.textContent.trim(); if (t && t.length < 60 && t !== title) { company = t; break; } }
  }
  company = company.replace(/\\n\\s+/g, ' ').trim().slice(0, 120);

  let salary = get('.salary') || get('[class*="salary"]');
  salary = salary.replace(/\\n\\s+/g, ' ').trim().slice(0, 80);

  let city = get('[class*="location"]') || get('[class*="area"]') || '';
  city = city.replace(/\\n\\s+/g, ' ').trim().slice(0, 40);

  // Description: try EVERY possible BOSS container
  let desc = '';
  const selList = [
    '.job-sec-text', '.job-detail', '.detail-content', '.job_detail',
    '[class*="job-sec"]', '[class*="job-detail"]', '[class*="detail-content"]',
    '[class*="job_detail"]', '[class*="description"]', '[class*="job-description"]',
    '.job-desc', '[class*="job-desc"]', '.job-content', '[class*="job-content"]',
    '.job-requirement', '[class*="requirement"]',
  ];
  for (const sel of selList) {
    try {
      const el = document.querySelector(sel);
      if (el && el.innerText && el.innerText.length > 50) { desc = el.innerText; break; }
    } catch(e) {}
  }
  // If still no desc, try finding the largest text block on the page
  if (!desc || desc.length < 50) {
    const blocks = Array.from(document.querySelectorAll('div, section, article'))
      .filter(d => d.innerText && d.innerText.length > 100 && d.innerText.length < 10000)
      .sort((a,b) => b.innerText.length - a.innerText.length);
    if (blocks.length > 0) desc = blocks[0].innerText;
  }
  if (!desc || desc.length < 50) desc = document.body?.innerText || '';
  desc = desc.slice(0, 8000);

  return {
    source_key: location.href.split('?')[0], url: location.href,
    title, company, salary, city,
    description: desc,
    raw: { pageTitle: document.title }
  };
})()
"""

EXTRACT_SELECTED_JOB_DETAIL_JS = """
(() => {
  const clean = (text) => String(text || '').replace(/\\s+/g, ' ').trim();
  const visible = (el) => !!(el && (el.offsetWidth || el.offsetHeight || el.getClientRects().length));
  const panel = Array.from(document.querySelectorAll('.job-detail-container, .job-detail-box, [class*="job-detail"]'))
    .find((el) => visible(el) && clean(el.innerText).length > 80) || document.body;
  const get = (sel) => clean(panel.querySelector(sel)?.textContent || '');
  let title = get('.job-detail-info .job-name') || get('.job-name') || get('h1');
  let salary = get('.job-detail-info .salary') || get('.salary') || get('[class*="salary"]');
  let city = '';
  const detailInfo = panel.querySelector('.job-detail-info');
  if (detailInfo) {
    const lis = Array.from(detailInfo.querySelectorAll('li')).map((li) => clean(li.textContent)).filter(Boolean);
    city = lis.find((x) => /北京|上海|广州|深圳|重庆|成都|杭州|苏州|武汉|西安|南京|天津/.test(x)) || '';
  }
  if (!city) city = get('[class*="location"]') || get('[class*="area"]');
  let company = get('.boss-name') || get('.company-name') || get('[class*="company-name"]');
  let desc = '';
  const descNode = Array.from(panel.querySelectorAll('.job-sec-text, [class*="job-sec"], [class*="job-detail"], [class*="description"], [class*="job-desc"]'))
    .filter((el) => visible(el) && clean(el.innerText).length > 50)
    .sort((a, b) => clean(b.innerText).length - clean(a.innerText).length)[0];
  if (descNode) desc = clean(descNode.innerText);
  if (!desc) desc = clean(panel.innerText);
  return {
    source_key: "",
    url: location.href,
    title: title.slice(0, 120),
    company: company.slice(0, 120),
    salary: salary.slice(0, 80),
    city: city.slice(0, 80),
    description: desc.slice(0, 8000),
    raw: { pageTitle: document.title, from_list_panel: true }
  };
})()
"""

FIND_AND_CLICK_CHAT_BTN_JS = """
(() => {
  const patterns = [/^立即沟通$/, /^立即溝通$/, /^沟通$/, /^开聊$/, /^立即开聊$/, /^感兴趣$/];
  const all = Array.from(document.querySelectorAll('button, a, span[role="button"], div[role="button"]'));
  for (const pat of patterns) {
    const btn = all.find(b => pat.test((b.textContent||'').replace(/\\s/g,'')) && b.offsetParent !== null);
    if (btn) { btn.click(); return {found: true, text: btn.textContent.trim()}; }
  }
  const fb = all.find(b => /沟通|开聊/.test(b.textContent||'') && b.offsetParent !== null);
  if (fb) { fb.click(); return {found: true, text: fb.textContent.trim(), fallback: true}; }
  return {found: false};
})()
"""

WAIT_FOR_CHAT_INPUT_JS = """
(() => {
  const cs = document.querySelectorAll('[class*="dialog"], [class*="chat"], [class*="modal"], [class*="drawer"], body');
  for (const c of cs) {
    if (!c.offsetParent) continue;
    const inp = c.querySelector('[contenteditable="true"], [role="textbox"], textarea');
    if (inp && inp.offsetParent) return true;
  }
  return false;
})()
"""

def _fill_and_send_js(msg: str) -> str:
    """Fill message and click send in BOSS chat. Tries: text button, icon button, Enter, Ctrl+Enter."""
    m = json.dumps(msg, ensure_ascii=False)
    return """( () => {
  const msg = """ + m + """;

  // Find input
  const cs = document.querySelectorAll('[class*="dialog"], [class*="chat"], [class*="modal"], [class*="drawer"], [class*="panel"], body');
  let input = null;
  let container = null;
  for (const c of cs) { if (!c.offsetParent) continue; input = c.querySelector('textarea, [contenteditable="true"], [role="textbox"]'); if (input && input.offsetParent) { container = c; break; } }
  if (!input) return {ok:false,error:'no_input'};

  // Clear and fill
  input.focus();
  if (input.isContentEditable || input.getAttribute('contenteditable')==='true') {
    input.textContent = '';
    input.dispatchEvent(new InputEvent('input',{bubbles:true,inputType:'deleteContent'}));
    input.textContent = msg;
    input.dispatchEvent(new InputEvent('input',{bubbles:true,inputType:'insertText',data:msg}));
  } else {
    input.value = '';
    input.dispatchEvent(new Event('input',{bubbles:true}));
    const s = Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype,'value') || Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value');
    if(s?.set) s.set.call(input, msg); else input.value = msg;
    input.dispatchEvent(new Event('input',{bubbles:true}));
    input.dispatchEvent(new Event('change',{bubbles:true}));
  }

  // Try to find and click send button — multiple strategies
  const allBtns = Array.from(document.querySelectorAll('button, span[role="button"], div[role="button"], a.btn'));
  const visible = (b) => b.offsetParent !== null || b.getClientRects().length > 0;

  // Strategy 1: exact text match
  for (const pat of [/^发送$/, /^Send$/i, /^打招呼$/, /^发送招呼$/, /^确认发送$/]) {
    const btn = allBtns.find(b => pat.test((b.textContent||'').replace(/\\s/g,'')) && visible(b));
    if (btn) { btn.click(); return {ok:true,sent:true,method:'btn',text:btn.textContent.trim()}; }
  }

  // Strategy 2: button near the input with send-related class
  if (container) {
    const nearby = container.querySelectorAll('button, [class*="send"], [class*="btn-send"], [class*="send-btn"]');
    for (const btn of nearby) { if (visible(btn)) { btn.click(); return {ok:true,sent:true,method:'nearby'}; } }
  }

  // Strategy 3: any short-text button with 发/送
  const fb = allBtns.find(b => { const t=(b.textContent||'').replace(/\\s/g,''); return (t.includes('发')||t.includes('送')) && t.length<=8 && visible(b); });
  if (fb) { fb.click(); return {ok:true,sent:true,method:'fuzzy',text:fb.textContent.trim()}; }

  // Strategy 4: any icon-only button (SVG) in the chat footer area
  if (container) {
    const iconBtns = container.querySelectorAll('button');
    for (const btn of iconBtns) {
      if (!visible(btn)) continue;
      const hasIcon = btn.querySelector('svg, img, i, [class*="icon"]');
      const hasNoText = !(btn.textContent||'').trim();
      if (hasIcon || hasNoText) { btn.click(); return {ok:true,sent:true,method:'icon'}; }
    }
  }

  // Strategy 5: Enter key
  input.dispatchEvent(new KeyboardEvent('keydown',{key:'Enter',code:'Enter',keyCode:13,which:13,bubbles:true,cancelable:true}));
  input.dispatchEvent(new KeyboardEvent('keypress',{key:'Enter',code:'Enter',keyCode:13,which:13,bubbles:true,cancelable:true}));
  input.dispatchEvent(new KeyboardEvent('keyup',{key:'Enter',code:'Enter',keyCode:13,which:13,bubbles:true,cancelable:true}));

  // Strategy 6: Ctrl+Enter (some chat UIs)
  input.dispatchEvent(new KeyboardEvent('keydown',{key:'Enter',code:'Enter',keyCode:13,which:13,ctrlKey:true,bubbles:true,cancelable:true}));

  return {ok:true,sent:true,method:'enter'};
})()
"""

def _fill_only_js(msg: str) -> str:
    """Fill chat input character by character with random delays, simulating human typing."""
    m = json.dumps(msg, ensure_ascii=False)
    return """(async () => {
  const msg = """ + m + """;
  const cs = document.querySelectorAll('[class*="dialog"], [class*="chat"], [class*="modal"], [class*="drawer"], body');
  let input = null;
  for (const c of cs) { if (!c.offsetParent) continue; input = c.querySelector('textarea, [contenteditable="true"], [role="textbox"]'); if (input && input.offsetParent) break; }
  if (!input) return false;
  input.focus();
  // Clear first
  if (input.isContentEditable || input.getAttribute('contenteditable')==='true') {
    input.textContent = '';
    input.dispatchEvent(new InputEvent('input',{bubbles:true,inputType:'deleteContent'}));
  } else {
    input.value = '';
    input.dispatchEvent(new Event('input',{bubbles:true}));
  }
  // Type character by character
  for (let i = 0; i < msg.length; i++) {
    const ch = msg[i];
    if (input.isContentEditable || input.getAttribute('contenteditable')==='true') {
      input.textContent += ch;
    } else {
      input.value += ch;
    }
    input.dispatchEvent(new InputEvent('input', {bubbles:true, inputType:'insertText', data:ch}));
    // Random delay 40-160ms per char (~300-400 chars/min, human-like)
    await new Promise(r => setTimeout(r, 40 + Math.random() * 120));
  }
  input.dispatchEvent(new Event('change', {bubbles:true}));
  return true;
})()
"""
