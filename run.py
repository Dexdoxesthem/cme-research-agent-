"""Entry point: python run.py  (opens dashboard at http://127.0.0.1:8000)"""
import os

import uvicorn

if __name__ == "__main__":
    uvicorn.run(
        "cme_agent.main:app",
        host="127.0.0.1",
        port=int(os.environ.get("PORT", 8000)),
        reload=False,
    )
