"""FastAPI application: CME Futures Research Agent backend."""
from __future__ import annotations

import json
import math
import threading
from pathlib import Path

import pandas as pd
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from typing import Optional, List

from . import backtest as bt
from .analysis import analyze_all, analyze_symbol
from .config import (CONTRACTS, CORE_SYMBOLS, GROUP_LABELS, load_calendar,
                     load_config, load_session, log_trade,
                     reset_session_if_new_day, save_calendar, save_config)
from .data import (market_context, scan_universe, clear_universe_cache,
                   upcoming_events)


def _finite(obj):
    """Recursively replace non-finite floats (NaN/Inf) with None so they
    can be encoded as strict JSON (Starlette uses allow_nan=False)."""
    if isinstance(obj, dict):
        return {k: _finite(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_finite(v) for v in obj]
    if isinstance(obj, float) and not math.isfinite(obj):
        return None
    return obj


class SafeJSONResponse(JSONResponse):
    def render(self, content):
        return json.dumps(_finite(content), ensure_ascii=False, allow_nan=False,
                          indent=None, separators=(",", ":")).encode("utf-8")


app = FastAPI(title="CME Futures Research Agent", version="1.0.0",
              default_response_class=SafeJSONResponse,
              redirect_slashes=False)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_methods=["*"], allow_headers=["*"],
)


@app.middleware("http")
async def normalize_api_path(request, call_next):
    query_path = request.query_params.get("__path")
    matched_path = request.headers.get("x-matched-path")

    if query_path:
        request.scope["path"] = query_path.split("?")[0]
    elif matched_path and matched_path != "/api/index" and not matched_path.startswith("/404"):
        request.scope["path"] = matched_path.split("?")[0]

    path = request.scope.get("path", "")
    if not path.startswith("/api") and not path.startswith("/assets") and path != "/" and "." not in path:
        request.scope["path"] = f"/api{path}"
    return await call_next(request)

DIST_DIR = Path(__file__).resolve().parent / "dist"
assets_dir = DIST_DIR / "assets"
if assets_dir.is_dir():
    app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

_lock = threading.Lock()


class ConfigUpdate(BaseModel):
    account_size: Optional[float] = None
    risk_percent: Optional[float] = None
    daily_loss_limit: Optional[float] = None
    risk_per_trade_override: Optional[float] = None
    suggested_size_ratio: Optional[float] = None


class CalendarEvent(BaseModel):
    date: str = Field(..., description="ISO date or datetime, e.g. 2026-09-16 14:00")
    name: str
    impact: str = "high"


class TradeLog(BaseModel):
    symbol: str
    entry: float
    exit: float
    contracts: int = 1
    side: str = "long"


@app.get("/")
def index():
    index_file = DIST_DIR / "index.html"
    if index_file.is_file():
        return FileResponse(index_file)
    return {"status": "ok", "name": "CME Futures Research Agent", "version": "1.0.0"}


@app.get("/api")
def api_root():
    return {"status": "ok", "name": "CME Futures Research Agent API", "version": "1.0.0"}


@app.get("/api/health")
def health():
    return {"ok": True, "instruments": list(CONTRACTS.keys())}


@app.get("/api/config")
def get_config():
    cfg = load_config()
    cfg["risk_budget"] = round(float(cfg["account_size"]) * float(cfg["risk_percent"]), 2)
    return cfg


@app.post("/api/config")
def update_config(body: ConfigUpdate):
    cfg = load_config()
    for k, v in body.model_dump(exclude_none=True).items():
        if k == "risk_percent" and (v <= 0 or v > 0.1):
            raise HTTPException(400, "risk_percent must be in (0, 0.10]")
        cfg[k] = v
    save_config(cfg)
    cfg["risk_budget"] = round(float(cfg["account_size"]) * float(cfg["risk_percent"]), 2)
    return cfg


@app.get("/api/session")
def get_session():
    return reset_session_if_new_day()


@app.post("/api/session/reset")
def reset_session():
    from datetime import date
    from .config import save_session
    save_session({"trades": [], "date": date.today().isoformat(), "realized_pnl": 0.0})
    return {"ok": True}


@app.post("/api/trade")
def record_trade(body: TradeLog):
    if body.symbol.upper() not in CONTRACTS:
        raise HTTPException(400, f"unknown symbol {body.symbol}")
    if body.contracts < 1:
        raise HTTPException(400, "contracts must be >= 1")
    with _lock:
        return log_trade(body.entry, body.exit, body.contracts, body.side, body.symbol)


@app.get("/api/analyze/all")
def analyze_all_endpoint(include_watchlist: bool = False):
    return analyze_all(include_watchlist=include_watchlist)


@app.get("/api/analyze/{symbol}")
def analyze(symbol: str, size: bool = False):
    sym = symbol.upper()
    if sym not in CONTRACTS:
        raise HTTPException(404, f"unknown instrument {sym}. Valid: {list(CONTRACTS.keys())}")
    light = not CONTRACTS[sym].core and not size
    return analyze_symbol(sym, allow_size=size, light=light)


@app.get("/api/universe")
def universe():
    """Full universe grouped by sector with contract specs."""
    out = {}
    for g in GROUP_LABELS:
        members = []
        for sym in sorted(CONTRACTS.keys(), key=lambda s: (not CONTRACTS[s].core, s)):
            c = CONTRACTS[sym]
            if c.group != g:
                continue
            members.append({
                "symbol": c.symbol, "name": c.name, "core": c.core,
                "sizeable": c.sizeable, "tick_size": c.tick_size,
                "tick_value": c.tick_value, "point_value": c.point_value,
                "yahoo_ticker": c.yahoo_ticker, "description": c.description,
            })
        if members:
            out[g] = {"label": GROUP_LABELS[g], "members": members}
    return out


@app.get("/api/scan")
def scan(force: bool = False):
    """Full-universe lightweight snapshot + market context header."""
    rows = scan_universe(force=force)
    ctx = market_context(rows)
    return {"snapshot": rows, "context": ctx, "core": CORE_SYMBOLS}


@app.get("/api/market-context")
def market_context_endpoint(force: bool = False):
    rows = scan_universe(force=force)
    return market_context(rows)


@app.get("/api/cache/clear")
def cache_clear():
    clear_universe_cache()
    return {"ok": True}


@app.get("/api/backtest/{symbol}")
def backtest(symbol: str, period: str = "3y", r_multiple: float = 2.0,
             stop_atr: float = 1.5, max_hold: int = 20):
    sym = symbol.upper()
    if sym not in CONTRACTS:
        raise HTTPException(404, f"unknown instrument {sym}")
    return bt.run_backtest(sym, period=period, r_multiple=r_multiple,
                           stop_atr=stop_atr, max_hold=max_hold)


@app.get("/api/chart/{symbol}")
def chart(symbol: str, period: str = "6mo"):
    """Daily bars with SMA20/50/200 + RSI for charting."""
    sym = symbol.upper()
    if sym not in CONTRACTS:
        raise HTTPException(404, f"unknown instrument {sym}")
    from .data import fetch_history
    from .indicators import build_indicators
    df = fetch_history(sym, period=period, interval="1d")
    if df is None or df.empty:
        raise HTTPException(502, "no chart data available")
    df = build_indicators(df).tail(130)
    out = []
    for idx, row in df.iterrows():
        out.append({
            "date": idx.date().isoformat(),
            "open": round(float(row["Open"]), 2),
            "high": round(float(row["High"]), 2),
            "low": round(float(row["Low"]), 2),
            "close": round(float(row["Close"]), 2),
            "volume": int(row.get("Volume", 0)) if not pd.isna(row.get("Volume", 0)) else 0,
            "ma20": round(float(row["SMA20"]), 2) if pd.notna(row["SMA20"]) else None,
            "ma50": round(float(row["SMA50"]), 2) if pd.notna(row["SMA50"]) else None,
            "ma200": round(float(row["SMA200"]), 2) if pd.notna(row["SMA200"]) else None,
            "rsi14": round(float(row["RSI14"]), 1) if pd.notna(row["RSI14"]) else None,
        })
    return {"symbol": sym, "bars": out}


@app.get("/api/calendar")
def calendar(hours: int = 72):
    return {"upcoming": upcoming_events(hours=hours), "config": load_calendar()}


@app.post("/api/calendar")
def add_event(body: CalendarEvent):
    cal = load_calendar()
    cal.setdefault("events", []).append(body.model_dump())
    save_calendar(cal)
    return {"ok": True, "events": cal["events"]}


@app.get("/api/contracts")
def contracts():
    return {k: {"name": v.name, "tick_size": v.tick_size, "tick_value": v.tick_value,
                "point_value": v.point_value, "yahoo_ticker": v.yahoo_ticker,
                "description": v.description}
            for k, v in CONTRACTS.items()}


@app.get("/{full_path:path}")
def spa_fallback(full_path: str):
    if full_path.startswith("api/") or full_path == "api":
        raise HTTPException(status_code=404, detail=f"API endpoint not found: /{full_path}")
    candidate = DIST_DIR / full_path
    if full_path and candidate.is_file():
        return FileResponse(candidate)
    index_file = DIST_DIR / "index.html"
    if index_file.is_file():
        return FileResponse(index_file)
    return {"status": "ok", "name": "CME Futures Research Agent", "version": "1.0.0"}
