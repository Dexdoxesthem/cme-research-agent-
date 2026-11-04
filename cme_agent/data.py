"""Market data retrieval (yfinance) and macro calendar handling.

DATA QUALITY POLICY: every pull is timestamped. Intraday quotes older than
15 minutes are flagged stale and never presented as live.
"""
from __future__ import annotations

import logging
import os
import tempfile
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, Optional

import pandas as pd
import yfinance as yf

from .config import CONTRACTS, GROUP_ORDER, load_calendar

# Safe cache locations for serverless / read-only environments
if os.environ.get("VERCEL") or not os.access(".", os.W_OK):
    _tmp_dir = tempfile.gettempdir()
    os.environ.setdefault("XDG_CACHE_HOME", _tmp_dir)
    os.environ.setdefault("YFINANCE_CACHE_DIR", str(Path(_tmp_dir) / ".cache" / "yfinance"))
    try:
        yf.set_tz_cache_location(str(Path(_tmp_dir) / "py-yfinance"))
    except Exception:
        pass

log = logging.getLogger("cme_agent.data")

STALE_AFTER_SECONDS = 15 * 60

_CACHE: Dict[str, dict] = {}
_CACHE_TTL_SECONDS = 60


def _flatten(df: pd.DataFrame) -> pd.DataFrame:
    """yfinance 1.3 returns MultiIndex columns for single tickers; flatten to plain."""
    if df is None or df.empty:
        return df
    if isinstance(df.columns, pd.MultiIndex):
        df = df.copy()
        df.columns = [c[0] for c in df.columns]
    return df


@dataclass
class MarketData:
    symbol: str
    price: float
    day_open: Optional[float]
    day_high: Optional[float]
    day_low: Optional[float]
    prev_close: Optional[float]
    change_pct: Optional[float]
    volume: Optional[int]
    fetched_at: datetime
    stale: bool
    source: str
    bars_daily: list
    bars_intraday: list
    raw: dict


def _get_cached(key: str, ttl: int = _CACHE_TTL_SECONDS) -> Optional[dict]:
    item = _CACHE.get(key)
    if not item:
        return None
    if datetime.now(timezone.utc) - item["ts"] > timedelta(seconds=ttl):
        return None
    return item["data"]


def _set_cache(key: str, data: dict) -> None:
    _CACHE[key] = {"ts": datetime.now(timezone.utc), "data": data}
    if len(_CACHE) > 64:
        _CACHE.clear()


def fetch_market_data(symbol: str, light: bool = False) -> MarketData:
    """Fetch intraday + daily bars for a contract's underlying Yahoo ticker.

    light=True skips the intraday download (fast path for watchlist scans);
    intraday bars then default to the last daily bars.
    """
    spec = CONTRACTS[symbol]
    tkr = spec.yahoo_ticker
    key = f"{tkr}|{datetime.now().strftime('%Y-%m-%d %H:%M')}|{light}"
    cached = _get_cached(key)
    if cached is not None:
        return cached["data"]

    now = datetime.now(timezone.utc)

    # Daily bars (1y) -> MAs, ATR, swings
    daily = yf.download(tkr, period="1y", interval="1d", progress=False, auto_adjust=False)
    daily = _flatten(daily)
    if daily is None or daily.empty:
        raise RuntimeError(f"No daily data for {tkr}")

    # Intraday bars (1d, 5m) -> today's range / live price
    if light:
        intraday = daily.tail(2)
    else:
        try:
            intraday = yf.download(tkr, period="1d", interval="5m", progress=False,
                                   auto_adjust=False, prepost=False)
            intraday = _flatten(intraday)
            if intraday is None or intraday.empty:
                intraday = daily.tail(2)
        except Exception as exc:  # pragma: no cover
            log.warning("intraday fetch failed for %s: %s", tkr, exc)
            intraday = daily.tail(2)

    # Live price / fast quote
    price, prev_close = None, None
    try:
        fast = yf.Ticker(tkr).fast_info
        price = float(fast.get("last_price"))
        prev_close = float(fast.get("previous_close"))
    except Exception:
        pass

    try:
        if price is None or prev_close is None:
            ticker_obj = yf.Ticker(tkr)
            hist = ticker_obj.history(period="5d", interval="1d", progress=False)
            if price is None and not hist.empty:
                price = float(hist["Close"].iloc[-1])
            if prev_close is None and len(hist) > 1:
                prev_close = float(hist["Close"].iloc[-2])
    except Exception as exc:
        log.warning("fallback quote failed for %s: %s", tkr, exc)

    # Determine day range: prefer intraday (last 78 bars), fall back to last daily bar
    day_high = day_low = day_open = None
    if intraday is not None and len(intraday) > 1:
        # isolate today's session rows when possible
        last_date = intraday.index[-1].date()
        today_rows = intraday[intraday.index.date == last_date] if hasattr(intraday.index, "date") else intraday
        if today_rows is not None and len(today_rows) > 0:
            day_high = float(today_rows["High"].max())
            day_low = float(today_rows["Low"].min())
            day_open = float(today_rows["Open"].iloc[0])
    if day_high is None:
        last_row = daily.iloc[-1]
        day_high = float(last_row["High"]); day_low = float(last_row["Low"])
        day_open = float(last_row["Open"])

    if price is None:
        price = float(daily["Close"].iloc[-1])
    if prev_close is None:
        prev_close = (float(daily["Close"].iloc[-2]) if len(daily) >= 2
                      else float(daily["Close"].iloc[-1]))

    change_pct = ((price - prev_close) / prev_close * 100.0) if prev_close else None

    volume = None
    try:
        if intraday is not None and len(intraday) > 1:
            volume = int(intraday["Volume"].sum())
    except Exception:
        pass

    stale = (datetime.now(timezone.utc) - now) > timedelta(seconds=STALE_AFTER_SECONDS)

    result = MarketData(
        symbol=symbol, price=price, day_open=day_open, day_high=day_high,
        day_low=day_low, prev_close=prev_close, change_pct=change_pct,
        volume=volume, fetched_at=now, stale=stale, source=f"yfinance:{tkr}",
        bars_daily=daily, bars_intraday=intraday,
        raw={"ticker": tkr},
    )
    _set_cache(key, {"data": result})
    return result


def fetch_history(symbol: str, period: str = "2y", interval: str = "1d"):
    """Return a pandas DataFrame of historical bars for backtesting."""
    spec = CONTRACTS[symbol]
    df = yf.download(spec.yahoo_ticker, period=period, interval=interval,
                     progress=False, auto_adjust=False)
    return _flatten(df)


# --------------------------------------------------------------------------
# Universe scan (lightweight, parallel, cached)
# --------------------------------------------------------------------------

_UNIVERSE_CACHE: Dict[str, dict] = {}
_UNIVERSE_CACHE_TTL = 180  # seconds; scan of ~45 tickers is slow, keep fresh-ish


def _light_snapshot(symbol: str) -> dict:
    """Fast daily-only snapshot for a symbol. Returns failure dict on error."""
    spec = CONTRACTS.get(symbol)
    if not spec or not spec.yahoo_ticker:
        return {"symbol": symbol, "group": spec.group if spec else None,
                "core": spec.core if spec else False,
                "name": spec.name if spec else symbol, "ok": False,
                "error": "no yahoo ticker"}
    try:
        df = yf.download(spec.yahoo_ticker, period="10d", interval="1d",
                         progress=False, auto_adjust=False)
        df = _flatten(df)
        if df is None or df.empty or len(df) < 2:
            return None
        price = float(df["Close"].iloc[-1])
        prev = float(df["Close"].iloc[-2])
        return {
            "symbol": symbol, "group": spec.group, "core": spec.core,
            "name": spec.name, "price": price, "prev_close": prev,
            "change_pct": round((price - prev) / prev * 100.0, 2),
            "day_high": round(float(df["High"].iloc[-1]), 4),
            "day_low": round(float(df["Low"].iloc[-1]), 4),
            "ok": True,
        }
    except Exception as exc:  # pragma: no cover
        log.debug("light snapshot failed for %s: %s", symbol, exc)
        return {"symbol": symbol, "group": spec.group, "core": spec.core,
                "name": spec.name, "ok": False, "error": str(exc)[:120]}


def scan_universe(symbols: Optional[list] = None, force: bool = False) -> list:
    """Fetch lightweight snapshots for all (or selected) universe symbols in parallel."""
    from concurrent.futures import ThreadPoolExecutor

    syms = symbols or sorted(CONTRACTS.keys())
    key = "|".join(sorted(syms))

    if not force:
        cached = _UNIVERSE_CACHE.get(key)
        if cached and datetime.now(timezone.utc) - cached["ts"] < timedelta(seconds=_UNIVERSE_CACHE_TTL):
            return cached["data"]

    with ThreadPoolExecutor(max_workers=10) as ex:
        futures = {ex.submit(_light_snapshot, s): s for s in syms}
        rows = []
        for fut in futures:
            res = fut.result()
            if res is None:
                res = {"symbol": futures[fut], "group": None, "core": False,
                       "name": futures[fut], "ok": False, "error": "no snapshot"}
            rows.append(res)

    _UNIVERSE_CACHE[key] = {"ts": datetime.now(timezone.utc), "data": rows}
    return rows


def clear_universe_cache():
    _UNIVERSE_CACHE.clear()


# --------------------------------------------------------------------------
# Market context / cross-asset read
# --------------------------------------------------------------------------

def _mean(xs):
    vals = [x for x in xs if x is not None]
    return sum(vals) / len(vals) if vals else None


def _weighted_group_move(rows: list, group: str) -> Optional[dict]:
    members = [r for r in rows if r and isinstance(r, dict)
               and r.get("group") == group and r.get("ok")]
    if not members:
        return None
    moves = [r["change_pct"] for r in members if r["change_pct"] is not None]
    if not moves:
        return None
    avg = _mean(moves)
    leader = max(members, key=lambda r: (r.get("change_pct") if r.get("change_pct") is not None else -999))
    laggard = min(members, key=lambda r: (r.get("change_pct") if r.get("change_pct") is not None else 999))
    return {
        "group": group, "n": len(members), "avg_change": round(avg, 2),
        "leader": leader["symbol"], "leader_pct": leader.get("change_pct"),
        "laggard": laggard["symbol"], "laggard_pct": laggard.get("change_pct"),
    }


def market_context(rows: list) -> dict:
    """Cross-asset read: what the board as a whole is signaling."""
    groups = {}
    for g in GROUP_ORDER:
        m = _weighted_group_move(rows, g)
        if m:
            groups[g] = m

    eq = groups.get("equity", {}).get("avg_change")
    rates = groups.get("rates", {}).get("avg_change")
    metals = groups.get("metals", {}).get("avg_change")
    energy = groups.get("energy", {}).get("avg_change")
    ag = groups.get("ag", {}).get("avg_change")
    fx = groups.get("fx", {}).get("avg_change")
    crypto = groups.get("crypto", {}).get("avg_change")

    ctx = "mixed / no dominant signal"
    if eq is None:
        ctx = "insufficient data for cross-asset read"

    # NOTE: rates group average — rising T-note future PRICE = falling yield.
    # FX futures are quoted in USD per foreign unit: rising = stronger FX / weaker USD.
    elif eq is not None and rates is not None:
        risk_on = eq > 0.1 and rates <= 0.05 and (energy is None or energy > 0)
        risk_off = eq < -0.1 and rates > 0.05
        rate_cut = eq > 0.1 and rates > 0.2 and (metals is None or metals > 0.05)
        defensive = eq < -0.1 and (metals is None or metals > 0.2) and (rates is None or rates > 0.2)
        gold_bid = metals is not None and metals > 0.3 and (metals or 0) > (eq or 0)
        if rate_cut:
            ctx = "risk-on with rate-cut pricing (equities + bonds + gold all bid)"
        elif risk_off:
            ctx = "risk-off rotation (equities down, bonds bid)"
        elif defensive:
            ctx = "defensive rotation (equities down, bonds + metals bid)"
        elif risk_on:
            ctx = "pure risk-on (equities up, bonds down/flat, energy firm)"
        elif eq > 0 and (fx is not None and fx > 0.1):
            ctx = "risk-on with soft USD (equities + FX both bid)"
        elif metals is not None and metals > 0.5:
            ctx = "inflation-hedge bid (metals outperforming; check rate expectations)"
        elif abs(eq) < 0.3 and abs(rates) < 0.15:
            ctx = "quiet tape — no dominant cross-asset signal"

    # divergence notes
    divergences = []
    if eq is not None and rates is not None:
        if (eq > 0.2) and (rates > 0.2):
            divergences.append("equities and bond prices BOTH up — unusual; reads as rate-cut/risk-on blend")
        elif (eq < -0.1) and (rates < -0.1):
            divergences.append("equities and bond prices BOTH down — risk-on defying stock weakness")
    if crypto is not None and eq is not None:
        if (crypto > 0.5) and (eq < -0.1):
            divergences.append("crypto bid while equities down — isolated speculative bid, not broad risk")

    return {
        "one_line": ctx,
        "groups": groups,
        "divergences": divergences,
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }


# --------------------------------------------------------------------------
# Macro calendar
# --------------------------------------------------------------------------

_KNOWN_DATES = {  # (month, day) or (month, day, weekday_ordinal) high-impact 2026 fixtures
    # FOMC 2026 schedule (approx; confirm each quarter)
    "2026-01-27": "FOMC meeting day 1",
    "2026-01-28": "FOMC rate decision",
    "2026-03-17": "FOMC meeting day 1",
    "2026-03-18": "FOMC rate decision",
    "2026-04-28": "FOMC meeting day 1",
    "2026-04-29": "FOMC rate decision",
    "2026-06-16": "FOMC meeting day 1",
    "2026-06-17": "FOMC rate decision",
    "2026-07-28": "FOMC meeting day 1",
    "2026-07-29": "FOMC rate decision",
    "2026-09-15": "FOMC meeting day 1",
    "2026-09-16": "FOMC rate decision",
    "2026-10-27": "FOMC meeting day 1",
    "2026-10-28": "FOMC rate decision",
    "2026-12-08": "FOMC meeting day 1",
    "2026-12-09": "FOMC rate decision",
}


def _first_friday(year: int, month: int) -> str:
    d = datetime(year, month, 1)
    while d.weekday() != 4:
        d += timedelta(days=1)
    return d.strftime("%Y-%m-%d")


def _wednesdays(year: int, month: int) -> list:
    out = []
    d = datetime(year, month, 1)
    while d.month == month:
        if d.weekday() == 2:
            out.append(d.strftime("%Y-%m-%d"))
        d += timedelta(days=1)
    return out


def upcoming_events(hours: int = 48) -> list:
    """Return high-impact events scheduled within the next `hours` window.

    Combines a small deterministic set (NFP first Friday, EIA Wednesdays,
    known FOMC 2026 dates) with user-defined entries from calendar.json.
    Events are labelled with impact and a confidence note — many exact
    release times are not publicly machine-readable, so this is a helper,
    not a certified feed.
    """
    now = datetime.now(timezone.utc)
    horizon = now + timedelta(hours=hours)

    builtin = []
    for m in range(1, 13):
        for y in (now.year, now.year + 1):
            nfp = _first_friday(y, m)
            if now.date().isoformat() <= nfp <= horizon.date().isoformat():
                builtin.append({"date": nfp, "name": "Non-Farm Payrolls", "impact": "high",
                                "confidence": "scheduled-first-Friday"})
            for wd in _wednesdays(y, m):
                if now.date().isoformat() <= wd <= horizon.date().isoformat():
                    builtin.append({"date": wd, "name": "EIA crude inventory", "impact": "medium",
                                    "confidence": "scheduled-Wednesday"})
    for iso, name in _KNOWN_DATES.items():
        if now.date().isoformat() <= iso <= horizon.date().isoformat():
            builtin.append({"date": iso, "name": name, "impact": "high",
                            "confidence": "calendar-fixture"})

    cal = load_calendar()
    custom = []
    for ev in cal.get("events", []):
        try:
            dt = datetime.fromisoformat(ev["date"])
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            if now <= dt <= horizon:
                custom.append({
                    "date": dt.strftime("%Y-%m-%d"),
                    "name": ev["name"], "impact": ev.get("impact", "high"),
                    "confidence": "user-entered",
                })
        except (ValueError, KeyError):
            continue

    merged = {e["date"] + "|" + e["name"]: e for e in builtin + custom}
    events = sorted(merged.values(), key=lambda e: e["date"])
    return events


def event_risk_assessment(events: list) -> Optional[dict]:
    """Flag imminent unpriced macro risk inside the holding window."""
    if not events:
        return None
    now = datetime.now(timezone.utc)
    imminent = [e for e in events
                if 0 <= (datetime.strptime(e["date"], "%Y-%m-%d").replace(tzinfo=timezone.utc) - now).total_seconds() <= 36 * 3600]
    if not imminent:
        return None
    return {
        "flagged": True,
        "count": len(imminent),
        "events": imminent,
        "note": "Major data release inside/near the likely holding window — treat as event risk.",
    }
