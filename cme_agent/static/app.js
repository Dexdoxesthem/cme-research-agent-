/* CME Futures Research Agent — frontend logic (vanilla JS, no build step) */

const $ = (sel) => document.querySelector(sel);

async function api(path, opts = {}) {
  const res = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...opts,
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || res.statusText);
  }
  return res.json();
}

function fmt(x, d = 2) {
  if (x === null || x === undefined) return "—";
  return Number(x).toFixed(d);
}

function setPill(el, state, text) {
  el.className = `pill ${state}`;
  el.textContent = text;
}

/* ---------------- Config ---------------- */
async function loadConfig() {
  const c = await api("/api/config");
  $("#cfgAccount").value = c.account_size;
  $("#cfgRiskPct").value = (c.risk_percent * 100).toFixed(1);
  $("#cfgDailyLimit").value = c.daily_loss_limit;
  $("#cfgRatio").value = c.suggested_size_ratio;
  $("#budgetLine").textContent = `$${c.risk_budget.toFixed(0)}`;
}

async function saveConfig() {
  const body = {
    account_size: parseFloat($("#cfgAccount").value),
    risk_percent: parseFloat($("#cfgRiskPct").value) / 100,
    daily_loss_limit: parseFloat($("#cfgDailyLimit").value),
    suggested_size_ratio: parseFloat($("#cfgRatio").value),
  };
  const c = await api("/api/config", {
    method: "POST",
    body: JSON.stringify(body),
  });
  $("#budgetLine").textContent = `$${c.risk_budget.toFixed(0)}`;
  flash("Config saved");
}

/* ---------------- Session / P&L ---------------- */
async function loadSession() {
  const s = await api("/api/session");
  const pnl = s.realized_pnl || 0;
  const el = $("#sessionPnl");
  el.textContent = (pnl >= 0 ? "+" : "") + pnl.toFixed(0);
  el.className = "pnl-big " + (pnl > 0 ? "pos" : pnl < 0 ? "neg" : "");

  const c = await api("/api/config");
  const limit = c.daily_loss_limit;
  const frac = Math.min(1, Math.max(0, (-pnl) / limit));
  $("#lossBar").style.width = (frac * 100).toFixed(0) + "%";
  $("#sessionMeta").textContent =
    `${s.trades.length} trade(s) logged · daily loss limit $${limit}`;

  const logEl = $("#tradeLog");
  logEl.innerHTML = "";
  s.trades.slice().reverse().forEach((t) => {
    const div = document.createElement("div");
    div.className = "log-item";
    div.innerHTML =
      `${t.time} ${t.symbol} ${t.side} ${t.contracts} @ ${t.entry}→${t.exit} ` +
      `<span class="${t.pnl >= 0 ? "pos" : "neg"}">${t.pnl >= 0 ? "+" : ""}${t.pnl}</span>`;
    logEl.appendChild(div);
  });
}

/* ---------------- Calendar ---------------- */
async function loadCalendar() {
  const cal = await api("/api/calendar");
  const el = $("#calendarList");
  el.innerHTML = "";
  if (!cal.upcoming.length) {
    el.innerHTML = `<div class="log-item">No scheduled high-impact events in next 72h.</div>`;
    return;
  }
  cal.upcoming.forEach((e) => {
    const div = document.createElement("div");
    div.className = "log-item";
    const imp = e.impact === "high" ? "bad" : e.impact === "medium" ? "warn" : "";
    div.innerHTML = `<span class="${imp}">${e.date}</span> · ${e.name}`;
    el.appendChild(div);
  });
}

async function addCalendarEvent() {
  const date = $("#calDate").value.trim();
  const name = $("#calName").value.trim();
  if (!date || !name) return alert("date + name required");
  await api("/api/calendar", { method: "POST", body: JSON.stringify({
    date, name, impact: $("#calImpact").value,
  })});
  $("#calDate").value = ""; $("#calName").value = "";
  loadCalendar();
  flash("Event added");
}

/* ---------------- Rendering helpers ---------------- */
function esc(s) {
  const d = document.createElement("div");
  d.textContent = String(s ?? "");
  return d.innerHTML;
}

function kvGrid(pairs) {
  return `<div class="kv-grid">${pairs
    .map(([k, v]) => `<div class="kv-cell"><div class="k">${esc(k)}</div><div class="v">${esc(v)}</div></div>`)
    .join("")}</div>`;
}

function signalClass(sig) {
  if (sig.includes("BULLISH")) return "bull";
  if (sig.includes("BEARISH")) return "bear";
  return "flat";
}

/* ---------------- Analysis rendering ---------------- */
function renderResult(r) {
  if (r.data && r.data.error) {
    return `<div class="error-box">${esc(r.data.error)}</div>`;
  }
  const d = r.data;
  const flags = (r.risk_flags || [])
    .map((f) => `<div class="flag ${f.toLowerCase().includes("loss limit") || f.toLowerCase().includes("failure") ? "bad" : f.toLowerCase().includes("stale") ? "warn" : "warn"}">${esc(f)}</div>`)
    .join("");

  let whyHtml = `<div class="sec"><h3>Why</h3><ul>` +
    r.why.map((w) => `<li>${esc(w)}</li>`).join("") + `</ul></div>`;

  let snap = kvGrid([
    ["Price", fmt(d.price)],
    ["Day High", fmt(d.day_high)],
    ["Day Low", fmt(d.day_low)],
    ["Day %", d.change_pct === null ? "—" : fmt(d.change_pct, 2) + "%"],
    ["20SMA", fmt(d.ma20)],
    ["50SMA", fmt(d.ma50)],
    ["200SMA", fmt(d.ma200)],
    ["RSI(14)", fmt(d.rsi14, 1)],
    ["ATR(14)", fmt(d.atr14, 3)],
    ["Vol (day)", d.volume ? d.volume.toLocaleString() : "—"],
    ["Rating", d.technical_rating ? d.technical_rating.rating : "—"],
    ["Data", (d.stale ? "STALE · " : "") + new Date(d.fetch_time).toLocaleTimeString()],
  ]);

  let posHtml = "";
  if (r.position) {
    const p = r.position;
    if (p.blocked) {
      posHtml = `<div class="flag bad">POSITION BLOCKED — ${esc(p.reason)}</div>`;
    } else {
      const rows = [
        ["Direction", p.direction.toUpperCase()],
        ["Entry ref", fmt(p.entry_ref)],
        ["Stop", fmt(p.stop)],
        ["Stop distance", `${fmt(p.stop_distance_points)} pts (${p.stop_distance_ticks} ticks)`],
        ["Risk / contract", `$${fmt(p.risk_per_contract, 2)}`],
        ["Risk budget", `$${fmt(p.risk_budget, 0)}`],
        ["Max contracts (2% rule)", p.max_contracts],
        ["Suggested contracts", `${p.suggested_contracts} (${p.suggested_ratio_pct}% of max)`],
        ["Total risk @ suggested", `$${fmt(p.total_risk_suggested, 2)} (${fmt(p.total_risk_pct_account, 2)}% acct)`],
        ["Target", fmt(p.target)],
        ["Reward", `${fmt(p.reward_points)} pts`],
        ["R:R", p.rr],
      ];
      posHtml = `<div class="sec"><h3>Position framework</h3>` +
        `<table><tbody>` +
        rows.map(([k, v]) => `<tr><th>${esc(k)}</th><td class="num">${esc(v)}</td></tr>`).join("") +
        `</tbody></table></div>`;
    }
  }

  let btHtml = "";
  if (r.backtest && r.backtest.note) {
    btHtml = `<div class="sec"><h3>Backtest context</h3><div class="muted">${esc(r.backtest.note)}</div></div>`;
  }

  return `
    <div class="signal-banner ${signalClass(r.signal)}">SIGNAL: ${esc(r.signal)}</div>
    ${flags}
    <div class="sec"><h3>Data snapshot</h3>${snap}</div>
    ${whyHtml}
    ${posHtml}
    ${btHtml}
    <div class="sec"><h3>Invalidation</h3><div>${esc(r.invalidation)}</div></div>
  `;
}

async function analyze(sym) {
  const body = $("#resultBody");
  body.innerHTML = `<div class="muted">Fetching live data for <strong>${sym}</strong>… <span class="spin"></span></div>`;
  try {
    const r = await api(`/api/analyze/${sym}`);
    body.innerHTML = renderResult(r);
    loadSession();
  } catch (e) {
    body.innerHTML = `<div class="error-box">${esc(e.message)}</div>`;
  }
}

async function analyzeAll() {
  const body = $("#resultBody");
  body.innerHTML = `<div class="muted">Analyzing all instruments… <span class="spin"></span></div>`;
  try {
    const res = await api("/api/analyze/all");
    let html = "";
    for (const [sym, r] of Object.entries(res)) {
      html += `<div class="signal-banner ${signalClass(r.signal)}" style="font-size:14px;padding:6px 12px;margin-bottom:6px">` +
        `${sym} — ${esc(r.signal)}</div>`;
    }
    body.innerHTML = html + `<div class="muted" style="margin-top:10px">Select a single instrument for full detail.</div>`;
  } catch (e) {
    body.innerHTML = `<div class="error-box">${esc(e.message)}</div>`;
  }
}

/* ---------------- Backtest rendering ---------------- */
function renderBacktest(b) {
  if (b.error) return `<div class="error-box">${esc(b.error)}</div>`;
  if (!b.sample_size) return `<div class="muted">${esc(b.note || "No setups matched.")}</div>`;
  const cells = kvGrid([
    ["Sample size", b.sample_size],
    ["Win rate", (b.win_rate * 100).toFixed(1) + "%"],
    ["Avg R / trade", b.avg_r],
    ["Expectancy (R)", b.expectancy_r],
    ["Stop hits", (b.stop_hit_pct * 100).toFixed(0) + "%"],
    ["Target hits", (b.target_hit_pct * 100).toFixed(0) + "%"],
    ["Time exits", (b.time_exit_pct * 100).toFixed(0) + "%"],
  ]);
  let side = "";
  if (b.longs) side += `<div class="muted" style="margin-top:6px">Longs: n=${b.longs.n}, win ${(b.longs.win_rate*100).toFixed(1)}%, avgR ${b.longs.avg_r} &nbsp;|&nbsp; Shorts: n=${b.shorts.n}, win ${(b.shorts.win_rate*100).toFixed(1)}%, avgR ${b.shorts.avg_r}</div>`;
  let recent = `<div class="sec"><h3>Recent signals (${b.sample_size} total)</h3><table><thead><tr><th>date</th><th>dir</th><th>entry</th><th>stop</th><th>target</th><th>R</th><th>exit</th></tr></thead><tbody>` +
    b.recent_trades.map((t) =>
      `<tr><td>${t.date}</td><td>${t.direction}</td><td>${fmt(t.entry)}</td><td>${fmt(t.stop)}</td><td>${fmt(t.target)}</td><td>${t.r_outcome}</td><td>${t.exit_reason}</td></tr>`).join("") +
    `</tbody></table></div>`;
  return `<div class="sec">${cells}</div>${side}<div class="muted" style="margin-top:8px">${esc(b.note)}</div>${recent}`;
}

async function runBacktest() {
  const body = $("#btBody");
  const sym = $("#btSym").value;
  const period = $("#btPeriod").value;
  body.innerHTML = `<div class="muted">Running 3y walk of trend+RSI setup… <span class="spin"></span></div>`;
  try {
    const b = await api(`/api/backtest/${sym}?period=${period}`);
    body.innerHTML = renderBacktest(b);
  } catch (e) {
    body.innerHTML = `<div class="error-box">${esc(e.message)}</div>`;
  }
}

/* ---------------- misc ---------------- */
let flashTimer;
function flash(msg) {
  const p = document.createElement("div");
  p.textContent = msg;
  p.style.cssText = "position:fixed;bottom:16px;right:16px;background:var(--panel2);border:1px solid var(--blue);color:var(--text);padding:8px 14px;border-radius:6px;z-index:99";
  document.body.appendChild(p);
  clearTimeout(flashTimer);
  flashTimer = setTimeout(() => p.remove(), 1800);
}

async function refreshAll() {
  setPill($("#dataHealth"), "warn", "refreshing…");
  try {
    await Promise.all([loadConfig(), loadSession(), loadCalendar()]);
    setPill($("#dataHealth"), "ok", "data loaded");
  } catch (e) {
    setPill($("#dataHealth"), "bad", "load error");
    console.error(e);
  }
}

/* ---------------- wiring ---------------- */
document.querySelectorAll(".btn.inst").forEach((b) =>
  b.addEventListener("click", () => analyze(b.dataset.sym)));
$("#btnAll").addEventListener("click", analyzeAll);
$("#btnRefresh").addEventListener("click", refreshAll);
$("#btnSaveCfg").addEventListener("click", saveConfig);
$("#btnResetSession").addEventListener("click", async () => {
  if (confirm("Reset today's session P&L?")) {
    await api("/api/session/reset", { method: "POST" });
    loadSession(); flash("Session reset");
  }
});
$("#btnAddCal").addEventListener("click", addCalendarEvent);
$("#btnBacktest").addEventListener("click", runBacktest);
refreshAll();
