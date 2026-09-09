# Decision Log — CME Futures Research Agent

Status: internal engineering record. Not documentation of the tool's usage, not
connected to any other doc. Chronological record of the project: what was built,
what decisions were made, and why each one was taken.

---

## 1. Why this project exists

The trader competes in a CME micro-futures trading challenge with a $24,000 account.
A system prompt was provided defining an agent that produces structured,
data-grounded research (not signals) across micro contracts. The prompt requires:
max 2% risk per trade, a daily loss limit, honest data labeling, sample-size-annotated
statistics, and a "NO EDGE / STAY FLAT" state that is a legitimate output.

Decision: build a standalone local Python tool with a web front end that operationalizes
that prompt — because a research agent that cannot pull, timestamp, and size against
live-ish data is not useful, and the manual prompt-only workflow would be slow and
error-prone.

---

## 2. Tech stack selection

Decision: FastAPI backend, served with Uvicorn, pandas/numpy/yfinance for data and
math. First frontend pass was a vanilla HTML/JS/CSS SPA; later replaced with React + Vite.

Why:
- FastAPI is modern, type-safe, and trivial to expose as REST endpoints that both the
  front end and a CLI/script can call.
- yfinance is free, needs no API key, and covers the full futures universe we need.
  It is delayed data — accepted knowingly and flagged everywhere (see honesty rules).
- Vanilla JS was chosen first to keep the front end dependency-free. It was rebuilt in
  React only after the user explicitly asked for a framework rebuild.
- Recharts was added for the price/MA/RSI charts (React-native, no build friction).
- Node 24 / npm 11 were already installed, so Vite + React was low-friction.

---

## 3. Contract spec model — "tick-driven", not "point-driven"

Decision: every contract is defined by `tick_size` and `tick_value`; the per-point
value is derived (`tick_value / tick_size`).

Why: The user's spec contained an internal inconsistency for MCL (it said both
"$1/tick (0.01)" and "$10/full point", which are mathematically incompatible — 0.01
at $1/tick implies $100/point). Rather than silently pick a "correct" number, the
model treats the directly stated tick value as authoritative and derives the point
value. This is internally consistent across all four core contracts:
- MES: 0.25 / $1.25 → $5/pt
- MGC: 0.10 / $1.00 → $10/pt
- MCL: 0.01 / $1.00 → $100/pt (derived; the "$10 equivalent" line in the prompt was inconsistent and not used)
- ZN: 1/64 / $15.625 → $1,000/pt

The derivation is stored as a property, so any tick/point math anywhere in the app
(sizing, PnL logging, stop distances) uses one source of truth.

---

## 4. Account / risk defaults

Decision: defaults match the prompt exactly — $24,000 account, 2% risk ($480 budget),
$500 daily loss limit, suggested size = 60% of the 2%-allowed max.

Why:
- The prompt is explicit about these numbers and about never breaching the 2% rule.
- "Suggested < max" (60%) is deliberate: the prompt's own guidance says cap initial
  size below the max to leave room for scaling and error. Never suggesting full max
  is a hard rule enforced in `build_position`.
- Config is persisted to JSON so the user can override (account size, risk %, daily
  loss limit, size ratio) without touching code. `risk_percent` is validated to
  (0, 0.10] to stop nonsense values.

---

## 5. Data layer design

Decision: one fetch path returns daily bars (1y, for indicators) + intraday bars (5m,
for today's range and realistic stop placement), plus a fast-quote fallback chain
(fast_info → 5-day history → daily bars).

Why:
- Indicators (SMA20/50/200, RSI, ATR, swings) need a year of daily bars; today's
  high/low/change and live-ish price need intraday. One structure avoids duplicated
  fetch code.
- Every pull is timestamped (`fetched_at`, UTC). Any pull older than 15 minutes for
  intraday use is flagged `stale` and surfaced as a risk flag — this implements the
  prompt's rule that stale data must never be presented as live.

Key bug found and fixed here: yfinance 1.3 returns MultiIndex columns for single
tickers. A `_flatten()` helper normalizes columns. Without it, every column access
broke.

---

## 6. Yahoo ticker mapping

Decision: map each CME contract to its Yahoo futures ticker; the index futures carry
no caret (`ES=F`, not `^ES=F`).

Why:
- The caret form (`^ES=F`) 404s on Yahoo. The no-caret continuous futures symbols
  resolve correctly.
- Micro contracts track their underlying continuous futures price exactly, so MES→ES=F
  etc. is a valid price proxy for research purposes. This is documented in the README
  as "delayed, not a live feed."

---

## 7. Position framework — stop placement (important early bug)

Decision: stops are anchored to intraday swing levels and ATR, with hard caps of
0.5×–2.5× intraday ATR from entry.

Why: The first version anchored stops to the 20-bar DAILY swing low. For MES that
produced a ~438-point stop → $2,190 risk per contract → the 2% rule ($480) refused
any size, making the tool useless. That was correct behavior per the rules but wrong
mechanically: a daily swing low is the wrong stop anchor for a micro intraday trade.
Fixing it with intraday (5m) swings + intraday ATR gave realistic stops (MES: ~17
ticks, $21/contract risk, 13 contracts at 60%).

The cap range (0.5×–2.5× ATR) prevents both absurdly tight stops (whipsawed by noise)
and absurdly wide ones (unaffordable). Entry zone = current price; target = recent
swing high/low or 2R, whichever is closer to a reasonable reward.

---

## 8. Signal synthesis rules

Decision: three states only — BULLISH / BEARISH / NO EDGE. A technical consensus
rating (votes across price-vs-MA, MA alignment, RSI zone, MACD) gates direction.
Trend alignment (price > 20>50>200 or mirror) strengthens it. Imminent high-impact
macro events force direction to 0.

Why:
- The prompt explicitly wants "no edge" to be a valid, frequent output — the tool
  must not force direction on mixed data.
- Using a weighted vote of independent indicators (rather than one signal) reduces
  single-indicator noise and produces a transparent "why" string the trader can audit.
- Gating on macro events is the prompt's own rule: an unpriced CPI/NFP/FOMC is a
  reason to stand down, not to trade.

---

## 9. Backtest engine — sample size is mandatory

Decision: a built-in backtester walks 2–5 years of daily bars for the same setup
(trend + RSI), simulates entry at next open, stop 1.5×ATR, target 2R, capped 20-day
hold, and reports win rate, avg R, expectancy, and side splits.

Why:
- The prompt's STEP 4 requires historical context and forbids stating a win rate
  without a sample size. Every rate in the output carries its `n`.
- The engine exists so the trader gets *some* quantified context rather than nothing;
  it is honestly labeled as ideal-fills/no-costs/no-slippage, i.e. anecdotal-quality,
  not production-grade.

Reality check (and why it's kept): for MES the built-in setup shows ~33% win rate and
negative expectancy on 3y daily data. That is reported without sugar-coating — the
tool is a risk-framing desk, not a hype machine.

---

## 10. Session P&L and daily-loss-limit enforcement

Decision: closed trades are logged (symbol, side, entry, exit, contracts) into a
per-day session file. Realized P&L is tracked. If it hits −$500, the analysis engine
emits a hard warning that no new positions are recommended; at −70% it warns to reduce
size. The UI shows a loss-limit progress bar.

Why: the prompt mandates a daily loss limit gate and proactive "pause new trades"
guidance after two stop-outs / nearing the limit. Persisting to JSON makes the state
survive restarts, and auto-reset on a new trading day prevents stale carry-over.

---

## 11. Macro calendar — honest about its limits

Decision: calendar = known FOMC 2026 fixtures + NFP (first Friday) + EIA (Wednesdays)
+ user-added events from the UI or `calendar.json`. Events are confidence-tagged and
the README states exact release times are not certified.

Why: there is no reliable free, keyless API for the economic calendar. Rather than
fabricate a "live" feed, the tool ships a deterministic subset and lets the user
curate. This satisfies the honesty guardrail: no fabricated data.

---

## 12. FastAPI routing (two real bugs fixed)

1. `/api/analyze/all` was shadowed by `/api/analyze/{symbol}` — the literal route must
   be declared first. Fixed by ordering.
2. The SPA catch-all `/{full_path:path}` was declared before the API routes, so every
   `/api/*` call returned the HTML shell. Moved the catch-all to the very end of the
   route table. This is a class of bug FastAPI route-order is prone to; the openapi
   dump was used to verify final route order.

---

## 13. Frontend rebuild (vanilla → React)

Decision: user requested a framework rebuild. Moved to Vite + React. Production build
outputs to `cme_agent/dist`, which FastAPI serves; dev mode runs Vite on :5173 and
proxies `/api` to the backend.

Why: React gives component structure (config panel, session panel, calendar,
instrument bar, analysis view, backtest panel, market context panel), and Recharts
provides the price/MA/RSI charts the trader needs. Serving the built bundle from
FastAPI keeps deployment one-process (no separate static server).

Also added `/api/chart/{symbol}` to feed the chart — the analysis endpoint returns
aggregates, not 130 bars of history.

---

## 14. PowerShell launcher

Decision: `run-agent.ps1` wraps the whole startup — Python/dep check, optional
frontend rebuild, port-in-use detection, server start with health-check wait, browser
open, log capture.

Why: the user asked for a "running file". It also discovered a real PowerShell quirk:
`Start-Process` refuses identical stdout/stderr redirection paths — fixed with two log
files (`server.log`, `server.err.log`). `run.py` reads `PORT` from the environment so
`-Port` works.

---

## 15. Full-universe expansion (the last system-prompt upgrade)

The prompt grew from 4 core instruments to a 49-instrument universe across 7 sectors,
with a market-context header and cross-asset context. Decisions made:

1. **Core vs watchlist** — `core=True` (MES/MGC/MCL/ZN) get a position framework by
   default; everything else is report-only (`sizeable` flag + "Size this position"
   toggle that re-requests with `size=true`). This implements the prompt rule that the
   watchlist is for context/confirmation, not default sizing.

2. **Yahoo ticker probes** — all 49 tickers were probed before wiring them in. Result:
   M6C=F (micro CAD) does not exist on Yahoo; `MCD=F` resolves and is used instead.
   A few full-size/illiquid instruments (NQ, BZ, SR3, ZQ, etc.) are marked
   `sizeable=False` or context-only.

3. **Group model** — every contract gets a `group` (equity/rates/metals/energy/ag/fx/
   crypto). Sector peers are used for per-asset "leading / lagging / diverging" reads.

4. **Market context engine** — `market_context()` averages sector % moves, classifies
   the tape (risk-on / risk-off / rate-cut pricing / defensive / inflation-hedge /
   quiet), and emits divergences (e.g., "equities + bond prices both up"). This is the
   one-line header the prompt requires before per-asset analysis. Note in code: rising
   T-note FUTURES price = falling yield; FX futures quoted USD-per-foreign-unit.

5. **Performance** — the first full-universe analyze took ~80s (sequential, every
   symbol pulling intraday). Fixes: (a) `light` mode skips the 5m download for
   watchlist symbols, (b) `analyze_all` runs in a thread pool, (c) universe scan
   cached 180s, market-data cache 60s. Cold full scan ~84s → cached ~11s; core-only
   near-instant. The cost is inherent to pulling 1y daily bars for 49 tickers from a
   free feed; documented in the README.

---

## 16. "Single positional indexer is out-of-bounds" — last bug found

Decision: harden every `iloc[-1]`/`iloc[-2]` against short/empty frames.

Why: `data.py` computed `prev_close` with `daily["Close"].iloc[-2]`, which crashes when
yfinance returns only one daily bar (thin/just-listed data or a partial pull).
Fixes:
- `data.py` — `prev_close` falls back to the last close if `< 2` rows exist.
- `analysis.py` — intraday ATR series empty-guarded (falls back to daily ATR); swing
  lookback capped to frame length.
- Verified existing guards elsewhere (light snapshot `len(df)<2` → None, backtest
  `<220` bars → abort, chart → 502 on empty).
- Full 49-symbol sweep after the fix: 0 failures.

---

## 17. Recurring operational decisions (worth remembering)

- **Server restarts:** repeatedly `Stop-Process python` before starting a new one to
  avoid `[Errno 10048] address in use` on 127.0.0.1:8000.
- **Route-order verification:** after adding routes, check `/openapi.json` path order
  — catch-alls must be last, literal routes before parameterized ones.
- **Config/session/calendar persistence:** all state lives in `cme_agent/data/*.json`
  so the app survives restarts and the user can hand-edit.
- **Honesty invariants:** no fabricated data; stale data flagged; every rate carries
  a sample size; watchlist never sized by default; the 2% rule is enforced even if the
  user asks to override — the math is shown instead.

---

## 18. Known limitations (accepted, not fixed)

- yfinance data is delayed, not tick-by-tick live. Intraday ATR/swings are best-effort.
- The economic calendar is user-curated + deterministic fixtures, not a certified feed.
- The built-in backtest uses daily bars with ideal fills and no costs — it is context,
  not a trading simulation.
- Cold full-universe scans take ~80s on a free feed; mitigated by caching and threads.
- MCL's prompt-spec "$10/full point equivalent" conflicts with its stated $1/tick; we
  derive point value from the tick (decision #3).
