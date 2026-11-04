"""Vercel serverless function entrypoint for CME Futures Research Agent."""
import os
import sys
import tempfile
from pathlib import Path

# Ensure project root is in sys.path so cme_agent module can be imported
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

# Ensure writable cache locations in serverless environment
_tmp_dir = tempfile.gettempdir()
os.environ.setdefault("XDG_CACHE_HOME", _tmp_dir)
os.environ.setdefault("YFINANCE_CACHE_DIR", str(Path(_tmp_dir) / ".cache" / "yfinance"))

from cme_agent.main import app  # noqa: E402

# Explicitly expose app for Vercel Python runtime
__all__ = ["app"]
