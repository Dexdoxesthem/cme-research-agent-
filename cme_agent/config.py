"""Account configuration, full contract universe, and JSON persistence."""
import json
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional

BASE_DIR = Path(__file__).resolve().parent
DEFAULT_DATA_DIR = BASE_DIR / "data"
CONFIG_PATH = DEFAULT_DATA_DIR / "config.json"
SESSION_PATH = DEFAULT_DATA_DIR / "session.json"
CALENDAR_PATH = DEFAULT_DATA_DIR / "calendar.json"


@dataclass(frozen=True)
class ContractSpec:
    symbol: str          # CME root
    name: str
    group: str           # equity / rates / metals / energy / ag / fx / crypto
    core: bool           # core focus instrument (position framework by default)
    yahoo_ticker: Optional[str]
    tick_size: float     # minimum price increment (in price points)
    tick_value: float    # $ per tick for the MICRO contract (or full-size if no micro)
    description: str
    sizeable: bool = True

    @property
    def point_value(self) -> float:
        """$ per full 1.00 price point (micro)."""
        return self.tick_value / self.tick_size


def _s(symbol, name, group, core, yahoo, tick_size, tick_value, description,
       sizeable=True) -> ContractSpec:
    return ContractSpec(symbol, name, group, core, yahoo, tick_size, tick_value,
                        description, sizeable)


CONTRACTS: Dict[str, ContractSpec] = {
    # ---------------- CORE ----------------
    "MES": _s("MES", "Micro E-mini S&P 500", "equity", True, "ES=F",
              0.25, 1.25, "Tracks S&P 500 index futures"),
    "MGC": _s("MGC", "Micro Gold", "metals", True, "GC=F",
              0.10, 1.00, "Tracks gold futures"),
    "MCL": _s("MCL", "Micro Crude Oil", "energy", True, "CL=F",
              0.01, 1.00, "Tracks WTI crude futures"),
    "ZN": _s("ZN", "10-Year T-Note", "rates", True, "ZN=F",
              1 / 64, 15.625, "Tracks 10Y U.S. Treasury note futures"),

    # ---------------- EQUITY INDEX ----------------
    "MNQ": _s("MNQ", "Micro E-mini Nasdaq-100", "equity", False, "MNQ=F",
              0.25, 0.50, "Micro Nasdaq-100 index futures"),
    "MYM": _s("MYM", "Micro E-mini Dow", "equity", False, "MYM=F",
              1.00, 0.50, "Micro Dow Jones index futures"),
    "M2K": _s("M2K", "Micro E-mini Russell 2000", "equity", False, "M2K=F",
              0.10, 0.50, "Micro Russell 2000 index futures"),
    "NQ": _s("NQ", "E-mini Nasdaq-100", "equity", False, "NQ=F",
             0.25, 5.00, "Full E-mini Nasdaq-100 (context)", sizeable=False),
    "N225": _s("N225", "Nikkei 225", "equity", False, "^N225",
               5.00, 1.00, "Nikkei 225 index (context)", sizeable=False),

    # ---------------- RATES ----------------
    "ZT": _s("ZT", "2-Year T-Note", "rates", False, "ZT=F",
             1 / 128, 7.8125, "2Y Treasury note futures"),
    "ZF": _s("ZF", "5-Year T-Note", "rates", False, "ZF=F",
             1 / 64, 15.625, "5Y Treasury note futures"),
    "ZB": _s("ZB", "T-Bond", "rates", False, "ZB=F",
             1 / 32, 31.25, "30Y Treasury bond futures"),
    "TN": _s("TN", "Ultra 10-Year T-Note", "rates", False, "TN=F",
             1 / 64, 15.625, "Ultra 10Y Treasury note futures"),
    "UB": _s("UB", "Ultra T-Bond", "rates", False, "UB=F",
             1 / 32, 31.25, "Ultra 30Y Treasury bond futures"),
    "SR1": _s("SR1", "1-Month SOFR", "rates", False, "SR1=F",
              0.0025, 2.50, "1M secured overnight financing rate future"),
    "SR3": _s("SR3", "3-Month SOFR", "rates", False, "SR3=F",
              0.0025, 6.25, "3M SOFR future (context)", sizeable=False),
    "ZQ": _s("ZQ", "30-Day Fed Funds", "rates", False, "ZQ=F",
             0.0025, 10.4167, "Fed funds rate future (context)", sizeable=False),

    # ---------------- METALS ----------------
    "SIL": _s("SIL", "Micro Silver", "metals", False, "SIL=F",
              0.005, 5.00, "Micro silver futures"),
    "PL": _s("PL", "Platinum", "metals", False, "PL=F",
             0.10, 5.00, "Platinum futures (full size)"),
    "HG": _s("HG", "Copper", "metals", False, "HG=F",
             0.0005, 12.50, "Copper futures (full size)"),
    "MHG": _s("MHG", "Micro Copper", "metals", False, "MHG=F",
              0.0005, 1.25, "Micro copper futures"),
    "PA": _s("PA", "Palladium", "metals", False, "PA=F",
             0.50, 50.00, "Palladium futures (full size)", sizeable=False),

    # ---------------- ENERGY ----------------
    "QG": _s("QG", "Micro Natural Gas", "energy", False, "QG=F",
             0.001, 2.50, "Micro Henry Hub nat gas futures"),
    "NG": _s("NG", "Natural Gas (Henry Hub)", "energy", False, "NG=F",
             0.001, 10.00, "Henry Hub nat gas futures (full size)", sizeable=False),
    "BZ": _s("BZ", "Brent Crude", "energy", False, "BZ=F",
             0.01, 10.00, "Brent crude futures (full size)", sizeable=False),
    "RB": _s("RB", "RBOB Gasoline", "energy", False, "RB=F",
             0.0001, 4.20, "RBOB gasoline futures (full size)", sizeable=False),
    "HO": _s("HO", "NY Harbor ULSD", "energy", False, "HO=F",
             0.0001, 4.20, "ULSD heating oil futures (full size)", sizeable=False),

    # ---------------- AGRICULTURE ----------------
    "ZW": _s("ZW", "Wheat (CBOT)", "ag", False, "ZW=F",
             0.25, 12.50, "Wheat futures (full size)", sizeable=False),
    "KE": _s("KE", "KC HRW Wheat", "ag", False, "KE=F",
             0.25, 12.50, "KC hard red winter wheat (full size)", sizeable=False),
    "ZC": _s("ZC", "Corn", "ag", False, "ZC=F",
             0.25, 12.50, "Corn futures (full size)", sizeable=False),
    "ZS": _s("ZS", "Soybeans", "ag", False, "ZS=F",
             0.25, 12.50, "Soybean futures (full size)", sizeable=False),
    "ZL": _s("ZL", "Soybean Oil", "ag", False, "ZL=F",
             0.01, 6.00, "Soybean oil futures (full size)", sizeable=False),
    "ZM": _s("ZM", "Soybean Meal", "ag", False, "ZM=F",
             0.10, 10.00, "Soybean meal futures (full size)", sizeable=False),
    "HE": _s("HE", "Lean Hogs", "ag", False, "HE=F",
             0.025, 10.00, "Lean hog futures (full size)", sizeable=False),
    "LE": _s("LE", "Live Cattle", "ag", False, "LE=F",
             0.025, 10.00, "Live cattle futures (full size)", sizeable=False),
    "GF": _s("GF", "Feeder Cattle", "ag", False, "GF=F",
             0.025, 12.50, "Feeder cattle futures (full size)", sizeable=False),

    # ---------------- FX ----------------
    "M6E": _s("M6E", "Micro EUR/USD", "fx", False, "M6E=F",
              0.0001, 1.25, "Micro euro/USD futures"),
    "M6B": _s("M6B", "Micro GBP/USD", "fx", False, "M6B=F",
              0.0001, 0.625, "Micro pound/USD futures"),
    "MJY": _s("MJY", "Micro JPY/USD", "fx", False, "MJY=F",
              0.000001, 1.25, "Micro yen/USD futures"),
    "M6A": _s("M6A", "Micro AUD/USD", "fx", False, "M6A=F",
              0.0001, 1.00, "Micro aussie/USD futures"),
    "M6C": _s("M6C", "Micro CAD/USD", "fx", False, "MCD=F",
              0.0001, 1.00, "Micro loonie/USD futures (Yahoo: MCD=F)"),
    "6E": _s("6E", "EUR/USD", "fx", False, "6E=F",
             0.0001, 12.50, "Euro/USD futures (full size)", sizeable=False),
    "6B": _s("6B", "GBP/USD", "fx", False, "6B=F",
             0.0001, 6.25, "Pound/USD futures (full size)", sizeable=False),
    "6J": _s("6J", "JPY/USD", "fx", False, "6J=F",
             0.0000005, 6.25, "Yen/USD futures (full size)", sizeable=False),
    "6A": _s("6A", "AUD/USD", "fx", False, "6A=F",
             0.0001, 10.00, "Aussie/USD futures (full size)", sizeable=False),
    "6C": _s("6C", "CAD/USD", "fx", False, "6C=F",
             0.0001, 10.00, "Loonie/USD futures (full size)", sizeable=False),

    # ---------------- CRYPTO ----------------
    "MBT": _s("MBT", "Micro Bitcoin", "crypto", False, "MBT=F",
              5.0, 0.50, "Micro bitcoin futures (0.1 BTC)"),
    "MET": _s("MET", "Micro Ether", "crypto", False, "MET=F",
              0.50, 0.05, "Micro ether futures (0.1 ETH)"),
    "BTC": _s("BTC", "Bitcoin (Friday/continuous proxy)", "crypto", False, "BTC=F",
              5.0, 5.00, "Bitcoin futures (context)", sizeable=False),
}

CORE_SYMBOLS = [s for s, c in CONTRACTS.items() if c.core]

GROUP_ORDER = ["equity", "rates", "metals", "energy", "ag", "fx", "crypto"]
GROUP_LABELS = {
    "equity": "Equity Index", "rates": "Rates", "metals": "Metals",
    "energy": "Energy", "ag": "Agriculture", "fx": "FX", "crypto": "Crypto",
}

DEFAULT_CONFIG = {
    "account_size": 24000,
    "risk_percent": 0.02,
    "daily_loss_limit": 500,
    "risk_per_trade_override": None,
    "suggested_size_ratio": 0.6,
    "instruments": CORE_SYMBOLS,
    "data_source": "yfinance",
}

DEFAULT_CALENDAR = {
    "high_impact": [
        {"event": "FOMC rate decision", "window_hours": 24},
        {"event": "Non-Farm Payrolls (NFP)", "window_hours": 24},
        {"event": "CPI release", "window_hours": 24},
        {"event": "PPI release", "window_hours": 12},
        {"event": "EIA crude inventory", "window_hours": 12},
        {"event": "USDA WASDE report", "window_hours": 12},
    ],
    "events": [],
}


_IN_MEMORY_STORE: Dict[str, dict] = {}


def _get_writable_data_dir() -> Path:
    if "DATA_DIR" in os.environ:
        p = Path(os.environ["DATA_DIR"])
    elif os.environ.get("VERCEL"):
        p = Path(tempfile.gettempdir()) / "cme_agent_data"
    else:
        p = DEFAULT_DATA_DIR
    try:
        p.mkdir(parents=True, exist_ok=True)
    except OSError:
        pass
    return p


def _read_json(path_or_filename, default):
    filename = path_or_filename.name if isinstance(path_or_filename, Path) else str(path_or_filename)

    if filename in _IN_MEMORY_STORE:
        val = _IN_MEMORY_STORE[filename]
        if isinstance(default, dict) and isinstance(val, dict):
            merged = dict(default)
            merged.update(val)
            return merged
        return val

    # 1. Try writable data directory
    writable_path = _get_writable_data_dir() / filename
    if writable_path.exists():
        try:
            with open(writable_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(default, dict) and isinstance(data, dict):
                merged = dict(default)
                merged.update(data)
                return merged
            return data
        except (json.JSONDecodeError, OSError):
            pass

    # 2. Try default packaged data directory
    packaged_path = DEFAULT_DATA_DIR / filename
    if packaged_path.exists():
        try:
            with open(packaged_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(default, dict) and isinstance(data, dict):
                merged = dict(default)
                merged.update(data)
                return merged
            return data
        except (json.JSONDecodeError, OSError):
            pass

    return default


def _write_json(path_or_filename, data) -> None:
    filename = path_or_filename.name if isinstance(path_or_filename, Path) else str(path_or_filename)
    _IN_MEMORY_STORE[filename] = data
    target_path = _get_writable_data_dir() / filename
    try:
        target_path.parent.mkdir(parents=True, exist_ok=True)
        with open(target_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except OSError:
        pass


def load_config() -> dict:
    return _read_json(CONFIG_PATH, dict(DEFAULT_CONFIG))


def save_config(cfg: dict) -> dict:
    merged = dict(DEFAULT_CONFIG)
    merged.update(cfg)
    _write_json(CONFIG_PATH, merged)
    return merged


def load_session() -> dict:
    default = {"trades": [], "date": "", "realized_pnl": 0.0}
    return _read_json(SESSION_PATH, default)


def save_session(sess: dict) -> None:
    _write_json(SESSION_PATH, sess)


def load_calendar() -> dict:
    return _read_json(CALENDAR_PATH, json.loads(json.dumps(DEFAULT_CALENDAR)))


def save_calendar(cal: dict) -> None:
    merged = json.loads(json.dumps(DEFAULT_CALENDAR))
    merged.update(cal)
    _write_json(CALENDAR_PATH, merged)


def risk_budget(cfg: dict) -> float:
    """Effective max $ risk per trade (2% rule or explicit override)."""
    if cfg.get("risk_per_trade_override"):
        return float(cfg["risk_per_trade_override"])
    return float(cfg["account_size"]) * float(cfg["risk_percent"])


def reset_session_if_new_day() -> dict:
    from datetime import date
    today = date.today().isoformat()
    sess = load_session()
    if sess.get("date") != today:
        sess = {"trades": [], "date": today, "realized_pnl": 0.0}
        save_session(sess)
    return sess


def log_trade(entry, exit_px, contracts, side, symbol) -> dict:
    """Record a closed trade and update realized session PnL."""
    from datetime import datetime
    spec = CONTRACTS.get(symbol.upper())
    if not spec:
        raise ValueError(f"Unknown symbol {symbol}")
    direction = 1 if side.lower() in ("long", "buy") else -1
    pnl = direction * (exit_px - entry) * contracts * spec.point_value
    sess = reset_session_if_new_day()
    sess["trades"].append({
        "symbol": symbol.upper(), "side": "long" if direction == 1 else "short",
        "entry": entry, "exit": exit_px, "contracts": contracts, "pnl": round(pnl, 2),
        "time": datetime.now().isoformat(timespec="seconds"),
    })
    sess["realized_pnl"] = round(sum(t["pnl"] for t in sess["trades"]), 2)
    save_session(sess)
    return {"pnl": round(pnl, 2), "realized_pnl": sess["realized_pnl"]}
