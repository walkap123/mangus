"""Stockfish evaluation layer.

Turns a FEN into an `Evaluation` at a fixed depth, checking the store's cache
first so any position is ever handed to the engine once. Fixed depth (not fixed
time) is deliberate: it's reproducible, which is what makes the cache correct to
reuse across runs.

Everything downstream (the move classifier) reads `Evaluation`s and never talks
to Stockfish directly, mirroring how the ingest layer hides chess.com.

Usage:
    with StockfishEval(depth=18, store=store) as sf:
        ev = sf.evaluate(fen)
        sf.evaluate_game(game)      # warm the cache for a whole game

Requires a Stockfish binary. Point at it with the MANGUS_STOCKFISH env var, pass
engine_path=..., or `brew install stockfish` so it's on PATH.
"""

from __future__ import annotations

import os
import shutil
from typing import Iterable, Optional

import chess
import chess.engine

from .models import Color, Evaluation, Game
from .store import Store

# Cap used when converting a forced mate into a centipawn-ish score for any
# caller that wants a single number. We keep mate separate in the model, but the
# engine's PovScore needs a finite bound to resolve mate lines.
_MATE_SCORE = 100_000

_COMMON_PATHS = (
    "/opt/homebrew/bin/stockfish",   # Apple-silicon Homebrew
    "/usr/local/bin/stockfish",      # Intel Homebrew
    "/usr/bin/stockfish",
    "/usr/games/stockfish",          # Debian/Ubuntu
)


class EngineNotFound(RuntimeError):
    pass


def find_stockfish(explicit: Optional[str] = None) -> str:
    """Locate a Stockfish binary: explicit arg -> env -> PATH -> common paths."""
    for candidate in (explicit, os.environ.get("MANGUS_STOCKFISH")):
        if candidate:
            if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
                return candidate
            raise EngineNotFound(f"Stockfish not runnable at {candidate!r}")
    found = shutil.which("stockfish")
    if found:
        return found
    for path in _COMMON_PATHS:
        if os.path.isfile(path) and os.access(path, os.X_OK):
            return path
    raise EngineNotFound(
        "Stockfish not found. Install it (`brew install stockfish`) or set "
        "MANGUS_STOCKFISH to the binary path."
    )


class StockfishEval:
    def __init__(
        self,
        *,
        depth: int = 18,
        store: Optional[Store] = None,
        engine_path: Optional[str] = None,
        threads: int = 1,
        hash_mb: int = 128,
    ):
        self.depth = depth
        self.store = store
        self.engine_path = find_stockfish(engine_path)
        self._threads = threads
        self._hash_mb = hash_mb
        self._engine: Optional[chess.engine.SimpleEngine] = None

    # ---- engine lifecycle ----
    def __enter__(self) -> "StockfishEval":
        self._engine = chess.engine.SimpleEngine.popen_uci(self.engine_path)
        self._engine.configure({"Threads": self._threads, "Hash": self._hash_mb})
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    def close(self) -> None:
        if self._engine is not None:
            self._engine.quit()
            self._engine = None

    # ---- evaluation ----
    def evaluate(self, fen: str, *, use_cache: bool = True) -> Evaluation:
        """Evaluate one FEN at the configured depth. Cache-first, write-through."""
        if use_cache and self.store is not None:
            hit = self.store.get_eval(fen, self.depth)
            if hit is not None:
                return hit

        if self._engine is None:
            raise RuntimeError("Engine not started; use `with StockfishEval(...)`.")

        board = chess.Board(fen)
        info = self._engine.analyse(board, chess.engine.Limit(depth=self.depth))
        ev = self._info_to_eval(fen, info)

        if self.store is not None:
            self.store.put_eval(ev)
        return ev

    def _info_to_eval(self, fen: str, info: chess.engine.InfoDict) -> Evaluation:
        score = info["score"].relative  # side-to-move POV, matches Evaluation
        mate = score.mate()
        cp = None if mate is not None else score.score(mate_score=_MATE_SCORE)
        pv = info.get("pv")
        best = pv[0].uci() if pv else None
        return Evaluation(
            fen=fen, depth=self.depth, cp=cp, mate=mate, best_move=best,
        )

    def evaluate_game(self, game: Game) -> int:
        """Warm the cache for every position in a game.

        Every ply's `fen_after` is the next ply's `fen_before`, so evaluating
        each `fen_before` plus the final `fen_after` covers every position a
        classifier needs (position before AND after each move). Returns the
        number of engine calls actually made (cache misses).
        """
        fens = [p.fen_before for p in game.moves]
        if game.moves:
            fens.append(game.moves[-1].fen_after)
        return self.evaluate_many(fens)

    def evaluate_many(self, fens: Iterable[str]) -> int:
        """Evaluate a sequence of FENs, deduping. Returns cache-miss count."""
        seen: set[str] = set()
        misses = 0
        for fen in fens:
            if fen in seen:
                continue
            seen.add(fen)
            cached = (
                self.store.get_eval(fen, self.depth) is not None
                if self.store is not None else False
            )
            self.evaluate(fen)
            if not cached:
                misses += 1
        return misses
