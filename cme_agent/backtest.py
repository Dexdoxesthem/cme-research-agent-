"""Simple built-in backtester for the trend + RSI setup.

Tests the SAME setup rules used by the analysis engine against historical
daily bars: (trend alignment) + (RSI confirmation). Simulates entries at the
next session open, stop = 1.5*ATR beyond entry, target = 2R, capped holding
period. Always reports sample size alongside any rate.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .config import CONTRACTS
from .data import fetch_history
from .indicators import build_indicators


def _round_tick(price, tick):
    return round(round(price / tick) * tick, 4)


def run_backtest(symbol: str, period: str = "3y", r_multiple: float = 2.0,
                 stop_atr: float = 1.5, max_hold: int = 20,
                 min_atr: float = 0.0) -> dict:
    spec = CONTRACTS[symbol]
    df = fetch_history(symbol, period=period, interval="1d")
    if df is None or len(df) < 220:
        return {"error": "insufficient history", "sample_size": 0}

    df = build_indicators(df)
    if "SMA200" not in df or df["SMA200"].isna().iloc[-1]:
        df = df.dropna(subset=["SMA20", "SMA50", "SMA200", "RSI14", "ATR14"])

    df = df.dropna(subset=["SMA20", "SMA50", "SMA200", "RSI14", "ATR14"])

    trades = []
    for i in range(200, len(df) - 1):
        row = df.iloc[i]
        price = row["Close"]
        s20, s50, s200 = row["SMA20"], row["SMA50"], row["SMA200"]
        rsi14 = row["RSI14"]
        a = row["ATR14"]
        if a is None or np.isnan(a) or a < min_atr:
            continue

        bull = price > s20 > s50 > s200 and 50 < rsi14 < 70
        bear = price < s20 < s50 < s200 and 30 < rsi14 < 50
        if not (bull or bear):
            continue

        direction = 1 if bull else -1
        entry = float(df["Open"].iloc[i + 1])
        stop = entry - direction * stop_atr * a
        target = entry + direction * (entry - stop) * r_multiple
        tick = spec.tick_size
        stop = _round_tick(stop, tick)
        target = _round_tick(target, tick)

        # simulate forward
        realized = None
        exit_reason = "hold"
        for j in range(i + 1, min(i + 1 + max_hold, len(df))):
            h, l, c = float(df["High"].iloc[j]), float(df["Low"].iloc[j]), float(df["Close"].iloc[j])
            if direction == 1:
                if l <= stop:
                    realized, exit_reason = -1.0, "stop"
                    break
                if h >= target:
                    realized, exit_reason = r_multiple, "target"
                    break
            else:
                if h >= stop:
                    realized, exit_reason = -1.0, "stop"
                    break
                if l <= target:
                    realized, exit_reason = r_multiple, "target"
                    break
        if realized is None:
            realized = (c - entry) / (entry - stop) if entry != stop else 0.0
            exit_reason = "time"

        trades.append({
            "date": df.index[i].date().isoformat(),
            "direction": "long" if bull else "short",
            "entry": entry, "stop": stop, "target": target,
            "r_outcome": round(realized, 3), "exit_reason": exit_reason,
        })

    n = len(trades)
    if n == 0:
        return {"sample_size": 0, "note": "No setups matched in history."}

    longs = [t for t in trades if t["direction"] == "long"]
    shorts = [t for t in trades if t["direction"] == "short"]
    r_values = np.array([t["r_outcome"] for t in trades])
    wins = r_values > 0
    avg_r = float(r_values.mean())
    win_rate = float(wins.mean())
    # expectancy in R per trade
    expectancy = float(r_values[r_values > 0].mean()) * win_rate - float(-r_values[r_values <= 0].mean()) * (1 - win_rate) if n > 1 else 0.0

    def _stats(ts):
        if not ts:
            return None
        rv = np.array([t["r_outcome"] for t in ts])
        return {"n": len(ts), "win_rate": round(float((rv > 0).mean()), 3),
                "avg_r": round(float(rv.mean()), 3)}

    return {
        "symbol": symbol,
        "period": period,
        "sample_size": n,
        "win_rate": round(win_rate, 3),
        "avg_r": round(avg_r, 3),
        "expectancy_r": round(expectancy, 3),
        "longs": _stats(longs),
        "shorts": _stats(shorts),
        "stop_hit_pct": round(float((r_values < 0).mean()), 3),
        "target_hit_pct": round(float((r_values > 0).mean()), 3),
        "time_exit_pct": round(float(np.mean([t["exit_reason"] == "time" for t in trades])), 3),
        "note": "Built-in test of the trend+RSI setup on daily bars. Anecdotal-quality: no transaction costs, no slippage, ideal fills at levels.",
        "recent_trades": trades[-12:],
    }
