# CME Futures Research Agent

**Quantitative research & risk-framing desk for the CME micro-futures trading challenge.**

Research tool · Risk-framing engine · **Not** a signal generator

Python · FastAPI · React · Vite · yfinance

---

## What it does

Analyzes a **49-instrument universe** across **7 sectors** (equity, rates, metals,
energy, agriculture, FX, crypto) and turns raw market data into structured,
risk-framed research:

| Output | What it tells you |
|---|---|
| Market context header | One-line read of the whole tape + per-sector avg move, leader / laggard / divergence |
| Per-asset snapshot | Price, day range, % change, SMA 20/50/200, RSI, ATR, swing levels, technical consensus |
| Signal state | `BULLISH` / `BEARISH` / `NO EDGE` - *no edge is a legitimate output* |
| Position framework | Entry zone, stop, target, R:R, invalidation - computed only when a setup exists |
| Sizing | $ risk/contract, max contracts under the **2% rule**, suggested size (60% of max) |
| Risk checks | Daily-loss-limit gate, stale-data flags, imminent-macro-event awareness |
| Backtest | Historical walk of the setup - **every rate carries its sample size** |

> **Honesty first:** this is a *research and risk-framing tool*, not a signal
> generator. Data is delayed (yfinance), and 2% risk per trade is enforced by the
> engine - it shows you the math rather than breaching the rule.

---

## Quick start

### Install & run

```bash
pip install -r requirements.txt
python run.py
```

Open **http://127.0.0.1:8000**.

### One-click launcher (Windows)

```powershell
.\run-agent.ps1            # start server + open browser
.\run-agent.ps1 -NoBrowser # start server only
.\run-agent.ps1 -Port 9000 # different port
```

---

## Frontend (React + Vite)

A production build lives in `cme_agent/dist/` and is served automatically by
FastAPI - no extra step needed to use the dashboard.

To develop with hot reload:

```bash
cd cme_agent/frontend
npm install
npm run dev      # http://127.0.0.1:5173 - proxies /api to the backend
```

Rebuild the production bundle after a UI change:

```bash
cd cme_agent/frontend && npm run build
```

---

## Asset universe

**CORE - position framework by default:** `MES` · `MGC` · `MCL` · `ZN`

**EXTENDED WATCHLIST - report-only (never sized unless explicitly requested):**

- Equity: MNQ, MYM, M2K, NQ, Nikkei 225
- Rates: ZT, ZF, ZB, TN, UB, SOFR 1M/3M, Fed Funds
- Metals: Micro Silver, Platinum, Copper (full + micro), Palladium
- Energy: Micro Nat Gas, Nat Gas, Brent, RBOB, ULSD
- Agriculture: Wheat, KC Wheat, Corn, Soybeans, Soybean Oil/Meal, Hogs, Cattle
- FX: EUR / GBP / JPY / AUD / CAD USD (micro + full)
- Crypto: Micro Bitcoin, Micro Ether, Bitcoin

---

## API reference

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/analyze/{sym}?size=false` | Full analysis; `size=true` forces a watchlist framework |
| `GET` | `/api/analyze/all?include_watchlist=false` | Core (fast) or full-universe scan |
| `GET` | `/api/universe` | Grouped instrument list with contract specs |
| `GET` | `/api/market-context` | Cross-asset header (one-line read + sector moves) |
| `GET` | `/api/scan` | Lightweight full-universe snapshot + context |
| `GET` | `/api/backtest/{sym}` | `period=3y&r_multiple=2&stop_atr=1.5&max_hold=20` |
| `GET` | `/api/chart/{sym}?period=6mo` | Daily bars + SMA/RSI for charting |
| `GET` / `POST` | `/api/config` | Read / update risk & account config |
| `GET` | `/api/session` / `POST /api/session/reset` | Session P&L state |
| `POST` | `/api/trade` | Log a closed trade `{symbol, entry, exit, contracts, side}` |
| `GET` / `POST` | `/api/calendar` | Macro-event calendar |

---

## Position framework (per-direction)

The engine builds an **entry zone** rather than chasing a single price, and sizes
every stop from **ATR** (capped 0.5-2.5x) against the **nearest swing level**.

| | BULLISH (long) | BEARISH (short) |
|---|---|---|
| Entry zone | price to price - 0.25 ATR (buy the pullback) | price to price + 0.25 ATR (sell the bounce) |
| Stop | entry - 1.5 ATR (below entry) | entry + 1.5 ATR (above entry) |
| Target | nearest swing high above, else +2R | nearest swing low below, else -2R |
| R:R | `(target - entry) / (entry - stop)` | `(entry - target) / (stop - entry)` |
| NO EDGE | flat only, `position: null` | flat only, `position: null` |

---

## Risk rules (enforced, not suggested)

- **2% of account per trade** by default (`risk_percent=0.02`, budget $480 for a
  $24k account). The engine **refuses** any size that breaches it - it shows the
  math instead of silently violating the rule.
- **Suggested size = 60%** of the 2%-allowed max, leaving room to scale / for error.
- **Daily loss limit (default $500):** crossing it warns and recommends no new
  positions; the UI surfaces a live progress bar.
- **Watchlist = report-only.** Never sized unless you explicitly request sizing.
- **Stale data is flagged**, never disguised as live.

---

## Data source & honesty rules

- **yfinance (Yahoo Finance)** - *delayed*, not a live feed. Every pull is
  timestamped; intraday quotes older than 15 min are flagged `STALE`.
- **Macro calendar** = known FOMC 2026 fixtures + NFP (first Friday) + EIA
  (Wednesdays) + events you add via the UI or `data/calendar.json`. Exact release
  times are **not certified** - verify against an official source.
- **Built-in backtest** uses daily bars, ideal fills, no costs/slippage. Rates are
  labeled *anecdotal-quality* and always carry their sample size.
- **Performance:** first full-universe scan pulls ~1y daily bars for 49 tickers
  (~80s cold), then caches (full ~11s, core near-instant).
- Config / session / calendar persist in `cme_agent/data/*.json`.

---

## Project layout

```
D:\cme
├── run.py                        # uvicorn entry point
├── run-agent.ps1                 # one-click Windows launcher
├── requirements.txt
├── decision.md                   # engineering decision log
└── cme_agent/
    ├── main.py                   # FastAPI app + routes
    ├── analysis.py               # signal synthesis + position framework + risk
    ├── indicators.py             # SMA / RSI / MACD / ATR / swing helpers
    ├── config.py                 # contract specs + account/risk config
    ├── data.py                   # yfinance fetch, cache, market context
    ├── backtest.py               # historical setup walkthrough
    ├── dist/                     # built React bundle (served by FastAPI)
    ├── static/                   # legacy vanilla frontend
    └── frontend/                 # React + Vite source
```

---

## Further reading

- **`decision.md`** - the full engineering decision log (18 entries): why each
  choice was made, and the real bugs found along the way.

---

> **Not licensed investment advice.** All output is probabilistic competition
> research and must be treated as such.
