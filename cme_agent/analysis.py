"""Signal synthesis + position framework + risk checks (the analysis engine)."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

import pandas as pd

from .config import (CONTRACTS, CORE_SYMBOLS, GROUP_LABELS, load_config,
                     load_session, risk_budget)
from .data import (event_risk_assessment, fetch_market_data, market_context,
                   scan_universe, upcoming_events)
from .indicators import (build_indicators, swing_high_low, technical_rating,
                           nearest_swing_high_above, nearest_swing_low_below)

SETUP_STATES = ("BULLISH SETUP", "BEARISH SETUP", "NO EDGE / STAY FLAT")


@dataclass
class AnalysisResult:
    signal: str
    data: dict
    why: list
    position: Optional[dict]
    backtest: dict
    invalidation: str
    risk_flags: list
    cross_asset: dict
    timestamp: str


def _round_tick(price, tick_size):
    return round(round(price / tick_size) * tick_size, 4)


def _ticks_between(a, b, tick_size):
    return round(abs(a - b) / tick_size)


def build_position(symbol, direction, entry, entry_zone, stop, target, cfg):
    spec = CONTRACTS[symbol]
    risk_per_contract = _ticks_between(entry, stop, spec.tick_size) * spec.tick_value
    budget = risk_budget(cfg)
    if risk_per_contract <= 0:
        return None
    max_contracts = int(budget // risk_per_contract)
    suggested = max(1, int(max_contracts * float(cfg.get("suggested_size_ratio", 0.6))))

    if max_contracts < 1:
        return {"blocked": True,
                "reason": f"1 contract risk ${risk_per_contract:.0f} exceeds budget ${budget:.0f}."}

    if direction == "long":
        rr = (target - entry) / (entry - stop) if entry != stop else 0.0
    else:
        rr = (entry - target) / (stop - entry) if entry != stop else 0.0

    return {
        "blocked": False,
        "direction": direction,
        "entry_zone": [round(e, 4) for e in entry_zone],
        "entry_ref": entry,
        "stop": stop,
        "stop_distance_points": round(abs(entry - stop), 4),
        "stop_distance_ticks": _ticks_between(entry, stop, spec.tick_size),
        "risk_per_contract": round(risk_per_contract, 2),
        "risk_budget": round(budget, 2),
        "max_contracts": max_contracts,
        "suggested_contracts": suggested,
        "suggested_ratio_pct": round(float(cfg.get("suggested_size_ratio", 0.6)) * 100),
        "target": target,
        "reward_points": round(abs(target - entry), 4),
        "rr": round(rr, 2),
        "total_risk_suggested": round(suggested * risk_per_contract, 2),
        "total_risk_pct_account": round(suggested * risk_per_contract / float(cfg["account_size"]) * 100, 2),
        "point_value": spec.point_value,
        "tick_size": spec.tick_size,
        "tick_value": spec.tick_value,
    }


def _peer_compare(symbol, rows):
    """Where does this asset sit within its sector group (leader/lagger/divergent)?"""
    spec = CONTRACTS[symbol]
    group_rows = [r for r in rows if r.get("group") == spec.group and r.get("ok")
                  and r.get("change_pct") is not None]
    if len(group_rows) < 2:
        return None
    moves = sorted(group_rows, key=lambda r: r["change_pct"])
    this = next((r for r in group_rows if r["symbol"] == symbol), None)
    if not this:
        return None
    avg = sum(r["change_pct"] for r in group_rows) / len(group_rows)
    own = this["change_pct"]
    best, worst = moves[-1], moves[0]
    if own >= avg + 0.5:
        role = "leading the group"
    elif own <= avg - 0.5:
        role = "lagging the group"
    else:
        role = "in line with the group"
    # divergence: moved opposite to the group majority
    signs = [1 if r["change_pct"] > 0 else -1 for r in group_rows]
    group_up = sum(1 for s in signs if s > 0)
    group_down = sum(1 for s in signs if s < 0)
    divergent = (own > 0 and group_down >= group_up) or (own < 0 and group_up >= group_down)
    return {
        "group": GROUP_LABELS.get(spec.group, spec.group),
        "group_avg": round(avg, 2),
        "n": len(group_rows),
        "role": role,
        "divergent": divergent,
        "best": best["symbol"], "best_pct": best["change_pct"],
        "worst": worst["symbol"], "worst_pct": worst["change_pct"],
    }


def _cross_asset_line(symbol, peers, ctx):
    """One-line cross-asset context for this asset."""
    spec = CONTRACTS[symbol]
    if peers:
        return (f"{spec.name} is {peers['role']} in {peers['group']} "
                f"(group avg {peers['group_avg']:+.2f}%, leader {peers['best']} "
                f"{peers['best_pct']:+.2f}%, laggard {peers['worst']} {peers['worst_pct']:+.2f}%). "
                f"Market context: {ctx.get('one_line', 'n/a')}")
    return f"Market context: {ctx.get('one_line', 'n/a')}"


def _analyze_sized(symbol, md, cfg, rows, ctx, allow_size):
    """Shared logic for core (sized) and watchlist (report-only) assets."""
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    risk_flags = []

    df = build_indicators(md.bars_daily)
    row = df.iloc[-1]

    intra = md.bars_intraday.copy()
    intra = build_indicators(intra) if len(intra) > 40 else None

    rating = technical_rating(row)
    s20, s50, s200 = row["SMA20"], row["SMA50"], row["SMA200"]
    rsi14 = row["RSI14"]
    atr14 = row["ATR14"]
    swh, swl = swing_high_low(df, lookback=20)

    if intra is not None:
        atr_series = intra["ATR14"].dropna()
        iatr = float(atr_series.iloc[-1]) if len(atr_series) else atr14
    else:
        iatr = atr14

    events = upcoming_events(hours=48)
    ev_risk = event_risk_assessment(events)

    spec = CONTRACTS[symbol]
    data_snapshot = {
        "symbol": symbol, "name": spec.name, "group": GROUP_LABELS.get(spec.group, spec.group),
        "core": spec.core, "sizeable": spec.sizeable,
        "price": md.price,
        "day_open": md.day_open, "day_high": md.day_high, "day_low": md.day_low,
        "prev_close": md.prev_close,
        "change_pct": round(md.change_pct, 2) if md.change_pct is not None else None,
        "volume": md.volume,
        "ma20": round(float(s20), 2) if pd.notna(s20) else None,
        "ma50": round(float(s50), 2) if pd.notna(s50) else None,
        "ma200": round(float(s200), 2) if pd.notna(s200) else None,
        "rsi14": round(float(rsi14), 1) if pd.notna(rsi14) else None,
        "atr14": round(float(atr14), 3) if pd.notna(atr14) else None,
        "swing_high": round(swh, 2), "swing_low": round(swl, 2),
        "technical_rating": rating,
        "fetch_time": md.fetched_at.isoformat(timespec="seconds"),
        "stale": md.stale,
        "source": md.source,
    }

    if md.stale:
        risk_flags.append("DATA STALE: intraday quote exceeds 15 min age — treat snapshot as delayed.")

    peers = _peer_compare(symbol, rows)
    cross_asset = {"peers": peers,
                   "line": _cross_asset_line(symbol, peers, ctx)}

    why = []
    why.append(f"Price {md.price:.2f} vs 20SMA {s20:.2f} / 50SMA {s50:.2f} / 200SMA {s200:.2f}")
    why.append(f"Technical consensus: {rating['rating']} ({rating['score']:+d}/{rating['votes']} votes: {', '.join(rating['detail'])})")
    if peers:
        why.append(f"Sector: {peers['group']} avg {peers['group_avg']:+.2f}% — {spec.name} {peers['role']}" +
                   (", DIVERGING from group" if peers["divergent"] else ""))
    if ev_risk:
        why.append(f"Macro: {len(ev_risk['events'])} high-impact release(s) inside 36h window ({', '.join(e['name'] for e in ev_risk['events'][:2])})")
        risk_flags.append(ev_risk["note"])

    # ---------------- Signal synthesis ----------------
    direction = 0
    event_block = bool(ev_risk and rating["direction"] == 0)
    trend_ok_bull = (pd.notna(s20) and pd.notna(s50) and pd.notna(s200)
                     and md.price > s20 > s50 > s200)
    trend_ok_bear = (pd.notna(s20) and pd.notna(s50) and pd.notna(s200)
                     and md.price < s20 < s50 < s200)

    if rating["direction"] == 1 and trend_ok_bull and not event_block:
        direction = 1
    elif rating["direction"] == -1 and trend_ok_bear and not event_block:
        direction = -1
    else:
        if rating["direction"] == 1 and (md.price > s20) and rating["score"] >= 3 and not event_block:
            direction = 1
        elif rating["direction"] == -1 and (md.price < s20) and rating["score"] <= -3 and not event_block:
            direction = -1
        else:
            direction = 0

    if event_block:
        direction = 0

    if direction == 0:
        why.append("Mixed or contradictory signals — no directional edge.")
        if event_block:
            why.append("Major macro release imminent and unpriced — standing down is the correct position.")
        return AnalysisResult(
            signal="NO EDGE / STAY FLAT", data=data_snapshot, why=why, position=None,
            backtest={"note": "no setup to backtest"},
            invalidation="n/a — no position taken.",
            risk_flags=risk_flags, cross_asset=cross_asset, timestamp=now,
        )

    # ---------------- Position framework (core only unless explicitly allowed) ----------------
    pos = None
    invalidation = "n/a — report-only (watchlist). Request explicit sizing to get a framework."
    if allow_size or spec.core:
        tick = spec.tick_size
        atr = iatr if iatr else atr14
        mult = 1.5
        stop_dist = float(min(max(atr * mult, 0.5 * atr), 2.5 * atr))
        entry = md.price

        if direction == 1:
            entry_zone = [_round_tick(entry, tick),
                          _round_tick(entry - 0.25 * atr, tick)]
            stop = entry - stop_dist
            res = nearest_swing_high_above(df, entry)
            target = res if res is not None else entry + 2 * stop_dist
        else:
            entry_zone = [_round_tick(entry, tick),
                          _round_tick(entry + 0.25 * atr, tick)]
            stop = entry + stop_dist
            sup = nearest_swing_low_below(df, entry)
            target = sup if sup is not None else entry - 2 * stop_dist

        stop = _round_tick(stop, tick)
        target = _round_tick(target, tick)

        pos = build_position(symbol, "long" if direction == 1 else "short",
                             entry, entry_zone, stop, target, cfg)
        invalidation = (f"{'Close below' if direction == 1 else 'Close above'} {stop:.4f} "
                        f"on a completed bar, or a confirmed break of the entry-zone extreme.")
    elif not spec.core:
        risk_flags.append("Watchlist asset — report only, no position size by default. "
                          "Request explicit sizing if you want a framework.")

    # ---------------- Risk checks ----------------
    sess = load_session()
    daily_pnl = sess.get("realized_pnl", 0.0)
    limit = float(cfg["daily_loss_limit"])
    if daily_pnl <= -limit:
        risk_flags.append(f"DAILY LOSS LIMIT REACHED (${daily_pnl:.0f} / limit ${limit:.0f}) — "
                          f"no new positions recommended regardless of setup.")
    elif daily_pnl <= -0.7 * limit:
        risk_flags.append(f"Approaching daily loss limit (${daily_pnl:.0f} / ${limit:.0f}) — "
                          f"reduce size or stand down.")

    return AnalysisResult(
        signal=("BULLISH SETUP" if direction == 1 else "BEARISH SETUP"),
        data=data_snapshot, why=why, position=pos,
        backtest={"note": "run backtest endpoint for stats"} if spec.core else {"note": "watchlist — backtest available on request"},
        invalidation=invalidation, risk_flags=risk_flags,
        cross_asset=cross_asset, timestamp=now,
    )


def analyze_symbol(symbol: str, allow_size: bool = False, light: bool = False) -> AnalysisResult:
    cfg = load_config()
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    spec = CONTRACTS.get(symbol)
    if not spec:
        return AnalysisResult(
            signal="NO EDGE / STAY FLAT",
            data={"error": f"unknown symbol {symbol}"},
            why=["Invalid instrument."], position=None,
            backtest={"note": "no data"}, invalidation="n/a",
            risk_flags=["INVALID SYMBOL"], cross_asset={}, timestamp=now,
        )

    rows = scan_universe()
    ctx = market_context(rows)

    try:
        md = fetch_market_data(symbol, light=light)
    except Exception as exc:
        return AnalysisResult(
            signal="NO EDGE / STAY FLAT",
            data={"error": str(exc)},
            why=[f"Market data fetch failed: {exc}. No signal produced."],
            position=None, backtest={"note": "no data"},
            invalidation="n/a", risk_flags=[f"DATA FAILURE: {exc}"],
            cross_asset={"line": ctx.get("one_line", "n/a"), "peers": None},
            timestamp=now,
        )

    return _analyze_sized(symbol, md, cfg, rows, ctx, allow_size)


def analyze_all(include_watchlist: bool = False):
    """Core instruments by default; whole universe when include_watchlist=True."""
    from concurrent.futures import ThreadPoolExecutor

    syms = load_config().get("instruments", CORE_SYMBOLS)
    if include_watchlist:
        syms = sorted(CONTRACTS.keys())

    rows = scan_universe()
    ctx = market_context(rows)

    def _run(sym):
        light = not CONTRACTS[sym].core
        return sym, analyze_symbol(sym, allow_size=False, light=light)

    results = {}
    with ThreadPoolExecutor(max_workers=8) as ex:
        for sym, res in ex.map(_run, syms):
            results[sym] = res
    return results
