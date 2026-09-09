"""Technical indicators computed from pandas bars."""
from __future__ import annotations

import numpy as np
import pandas as pd


def sma(series: pd.Series, period: int) -> pd.Series:
    return series.rolling(period).mean()


def ema(series: pd.Series, period: int) -> pd.Series:
    return series.ewm(span=period, adjust=False).mean()


def rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
    gain = delta.clip(lower=0.0)
    loss = -delta.clip(upper=0.0)
    avg_gain = gain.ewm(alpha=1 / period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


def macd(series: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9):
    line = ema(series, fast) - ema(series, slow)
    sig = line.ewm(span=signal, adjust=False).mean()
    hist = line - sig
    return line, sig, hist


def atr(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
    pc = close.shift(1)
    tr = pd.concat([
        high - low,
        (high - pc).abs(),
        (low - pc).abs(),
    ], axis=1).max(axis=1)
    return tr.ewm(alpha=1 / period, adjust=False).mean()


def swing_high_low(df: pd.DataFrame, lookback: int = 20):
    """Most recent swing high/low from last `lookback` completed bars."""
    high = df["High"].iloc[-lookback:-1] if lookback < len(df) else df["High"]
    low = df["Low"].iloc[-lookback:-1] if lookback < len(df) else df["Low"]
    return float(high.max()), float(low.min())


def _pivot_highs(df: pd.DataFrame, lookback: int, window: int = 2):
    """Local maxima (pivot highs) over the last `lookback` bars."""
    highs = df["High"].tail(lookback)
    pivots = []
    for i in range(window, len(highs) - window):
        center = float(highs.iloc[i])
        left = float(highs.iloc[i - window:i].max())
        right = float(highs.iloc[i + 1:i + 1 + window].max())
        if center >= left and center >= right:
            pivots.append(center)
    return pivots


def _pivot_lows(df: pd.DataFrame, lookback: int, window: int = 2):
    """Local minima (pivot lows) over the last `lookback` bars."""
    lows = df["Low"].tail(lookback)
    pivots = []
    for i in range(window, len(lows) - window):
        center = float(lows.iloc[i])
        left = float(lows.iloc[i - window:i].min())
        right = float(lows.iloc[i + 1:i + 1 + window].min())
        if center <= left and center <= right:
            pivots.append(center)
    return pivots


def nearest_swing_high_above(df: pd.DataFrame, price: float,
                             lookback: int = 60, window: int = 2):
    """Nearest pivot high strictly above `price`; None if none found."""
    above = [p for p in _pivot_highs(df, lookback, window) if p > price]
    return min(above) if above else None


def nearest_swing_low_below(df: pd.DataFrame, price: float,
                            lookback: int = 60, window: int = 2):
    """Nearest pivot low strictly below `price`; None if none found."""
    below = [p for p in _pivot_lows(df, lookback, window) if p < price]
    return max(below) if below else None


def build_indicators(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    close = df["Close"]
    for p in (20, 50, 200):
        df[f"SMA{p}"] = sma(close, p)
    df["RSI14"] = rsi(close, 14)
    df["MACD"], df["MACD_sig"], df["MACD_hist"] = macd(close)
    df["ATR14"] = atr(df["High"], df["Low"], close, 14)
    return df


def technical_rating(row) -> dict:
    """Consensus rating from price-vs-MA, MA alignment, RSI and MACD."""
    votes = []
    detail = []

    price = float(row["Close"]); s20 = row["SMA20"]; s50 = row["SMA50"]; s200 = row["SMA200"]

    if s20 and price > s20:
        votes.append(1); detail.append("price > 20SMA")
    else:
        votes.append(-1); detail.append("price < 20SMA")
    if s20 and s50:
        if s20 > s50:
            votes.append(1); detail.append("20SMA > 50SMA")
        else:
            votes.append(-1); detail.append("20SMA < 50SMA")
    if s200:
        if price > s200:
            votes.append(1); detail.append("price > 200SMA")
        else:
            votes.append(-1); detail.append("price < 200SMA")

    r = row.get("RSI14")
    if r is not None and not np.isnan(r):
        if 50 < r < 70:
            votes.append(1); detail.append(f"RSI {r:.1f} bullish zone")
        elif r >= 70:
            votes.append(-1); detail.append(f"RSI {r:.1f} overbought")
        elif 30 < r <= 50:
            votes.append(-1); detail.append(f"RSI {r:.1f} weak zone")
        else:
            votes.append(1); detail.append(f"RSI {r:.1f} oversold")

    m = row.get("MACD_hist"); ms = row.get("MACD_sig")
    if m is not None and ms is not None and not np.isnan(m):
        if m > 0:
            votes.append(1); detail.append("MACD histogram positive")
        else:
            votes.append(-1); detail.append("MACD histogram negative")

    score = sum(votes)
    n = len(votes)
    if n == 0:
        rating, direction = "NEUTRAL", 0
    elif score / n > 0.25:
        rating, direction = "BULLISH", 1
    elif score / n < -0.25:
        rating, direction = "BEARISH", -1
    else:
        rating, direction = "NEUTRAL", 0
    return {"rating": rating, "direction": direction, "score": score,
            "votes": n, "detail": detail}
