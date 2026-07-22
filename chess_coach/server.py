"""Local HTTP API for the beta — the "local server" the Expo app talks to.

Wraps the existing pipeline: GET /analyze?username=... runs ingest -> eval ->
classify -> tag -> coach and returns the exact `viewer_data` payload the review
UI renders. Stockfish and the eval cache stay here on the laptop; the phone app
just fetches over the LAN.

Run:
    python -m chess_coach.server            # binds 0.0.0.0:8000
then point the Expo app at http://<your-laptop-LAN-IP>:8000
"""

from __future__ import annotations

import socket
import sys
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from .coach import run
from .eval import EngineNotFound, StockfishEval
from .ingest import PlayerNotFound
from .store import Store
from .viewer import viewer_data

UA = "mangus-beta (walkerpate22@gmail.com)"
_state: dict = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    store = Store("mangus.db")
    engine = StockfishEval(depth=12, store=store)
    engine.__enter__()
    _state["store"], _state["engine"] = store, engine
    try:
        yield
    finally:
        engine.close()
        store.close()


app = FastAPI(title="mangus", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"],
)


@app.get("/health")
def health() -> dict:
    return {"ok": True, "engine": _state["engine"].engine_path}


@app.get("/analyze")
def analyze(
    username: str,
    max: int = Query(8, ge=1, le=50),
    depth: int = Query(12, ge=6, le=22),
    time_class: Optional[str] = None,
) -> dict:
    """Analyze a chess.com user's recent games; returns the review payload."""
    engine, store = _state["engine"], _state["store"]
    engine.depth = depth  # single-user beta: sequential requests only
    tcs = set(time_class.split(",")) if time_class else None
    try:
        report = run(username, store=store, evaluator=engine,
                     max_games=max, time_classes=tcs, ua=UA, progress=sys.stderr)
    except PlayerNotFound:
        raise HTTPException(status_code=404, detail=f"No such chess.com user: {username}")
    if not report.analyses:
        raise HTTPException(status_code=404,
                            detail=f"No standard games found for {username}")
    return viewer_data(report, engine)


def _lan_ip() -> str:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


def main() -> int:
    import uvicorn
    try:
        StockfishEval(depth=12)  # fail fast with a clear message if no engine
    except EngineNotFound as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1
    ip, port = _lan_ip(), 8000
    print(f"\n  mangus API — point the Expo app at:  http://{ip}:{port}\n"
          f"  (health check: http://{ip}:{port}/health)\n", file=sys.stderr)
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
