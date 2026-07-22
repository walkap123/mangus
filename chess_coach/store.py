"""Local SQLite persistence for the chess coach.

Two jobs, one file:

  1. **Games/plies** — so we ingest each game from chess.com exactly once and
     never re-fetch or re-parse it.
  2. **Eval cache** — the crown jewel. Keyed by (fen, depth), so a position is
     handed to Stockfish exactly once *ever*, shared across every game and every
     future run. Openings and common endgames collapse to a single row.

This is deliberately tiny and dependency-free (stdlib `sqlite3`). It stays
engine-agnostic: it stores `Evaluation`s, it doesn't know what produced them.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Iterator, Optional

from .models import (
    Color, Evaluation, Game, Player, Ply, epoch_to_dt,
)

SCHEMA = """
CREATE TABLE IF NOT EXISTS games (
    game_id       TEXT PRIMARY KEY,
    url           TEXT,
    played_at     INTEGER,           -- unix epoch (UTC), nullable
    time_class    TEXT,
    time_control  TEXT,
    rated         INTEGER,
    rules         TEXT,
    eco           TEXT,
    perspective   TEXT,              -- "white" | "black"
    white_user    TEXT, white_rating INTEGER, white_result TEXT,
    black_user    TEXT, black_rating INTEGER, black_result TEXT,
    pgn           TEXT
);

CREATE TABLE IF NOT EXISTS plies (
    game_id       TEXT NOT NULL REFERENCES games(game_id) ON DELETE CASCADE,
    ply_number    INTEGER NOT NULL,
    move_number   INTEGER,
    color         TEXT,
    san           TEXT,
    uci           TEXT,
    fen_before    TEXT,
    fen_after     TEXT,
    clock_seconds REAL,
    PRIMARY KEY (game_id, ply_number)
);

-- The eval cache. Position-only key: (fen, depth). Evals are side-to-move
-- relative, so a FEN alone determines the value.
CREATE TABLE IF NOT EXISTS evals (
    fen        TEXT NOT NULL,
    depth      INTEGER NOT NULL,
    cp         INTEGER,
    mate       INTEGER,
    best_move  TEXT,
    PRIMARY KEY (fen, depth)
);
"""


class Store:
    """A local SQLite-backed store. Use as a context manager or call close()."""

    def __init__(self, path: str | Path = "mangus.db"):
        self.path = str(path)
        self.conn = sqlite3.connect(self.path)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")
        self.conn.executescript(SCHEMA)
        self.conn.commit()

    def __enter__(self) -> "Store":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    def close(self) -> None:
        self.conn.close()

    # ---------------- games ----------------
    def has_game(self, game_id: str) -> bool:
        cur = self.conn.execute("SELECT 1 FROM games WHERE game_id = ?", (game_id,))
        return cur.fetchone() is not None

    def save_game(self, game: Game) -> None:
        """Upsert a game and all its plies. Idempotent."""
        played = int(game.played_at.timestamp()) if game.played_at else None
        self.conn.execute(
            """INSERT OR REPLACE INTO games
               (game_id, url, played_at, time_class, time_control, rated, rules,
                eco, perspective, white_user, white_rating, white_result,
                black_user, black_rating, black_result, pgn)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (game.game_id, game.url, played, game.time_class, game.time_control,
             int(game.rated), game.rules, game.eco, game.perspective.value,
             game.white.username, game.white.rating, game.white.result_raw,
             game.black.username, game.black.rating, game.black.result_raw,
             game.pgn),
        )
        # replace plies wholesale so re-saving never duplicates
        self.conn.execute("DELETE FROM plies WHERE game_id = ?", (game.game_id,))
        self.conn.executemany(
            """INSERT INTO plies
               (game_id, ply_number, move_number, color, san, uci,
                fen_before, fen_after, clock_seconds)
               VALUES (?,?,?,?,?,?,?,?,?)""",
            [(game.game_id, p.ply_number, p.move_number, p.color.value, p.san,
              p.uci, p.fen_before, p.fen_after, p.clock_seconds)
             for p in game.moves],
        )
        self.conn.commit()

    def get_game(self, game_id: str) -> Optional[Game]:
        row = self.conn.execute(
            "SELECT * FROM games WHERE game_id = ?", (game_id,)).fetchone()
        if row is None:
            return None
        return self._row_to_game(row)

    def iter_stored_games(self) -> Iterator[Game]:
        """All stored games, newest first (nulls last)."""
        rows = self.conn.execute(
            "SELECT * FROM games ORDER BY played_at DESC").fetchall()
        for row in rows:
            yield self._row_to_game(row)

    def _row_to_game(self, row: sqlite3.Row) -> Game:
        ply_rows = self.conn.execute(
            "SELECT * FROM plies WHERE game_id = ? ORDER BY ply_number",
            (row["game_id"],)).fetchall()
        moves = [
            Ply(
                ply_number=pr["ply_number"], move_number=pr["move_number"],
                color=Color(pr["color"]), san=pr["san"], uci=pr["uci"],
                fen_before=pr["fen_before"], fen_after=pr["fen_after"],
                clock_seconds=pr["clock_seconds"],
            )
            for pr in ply_rows
        ]
        return Game(
            game_id=row["game_id"], url=row["url"],
            played_at=epoch_to_dt(row["played_at"]),
            time_class=row["time_class"], time_control=row["time_control"],
            rated=bool(row["rated"]), rules=row["rules"], eco=row["eco"],
            white=Player(row["white_user"], row["white_rating"], row["white_result"]),
            black=Player(row["black_user"], row["black_rating"], row["black_result"]),
            perspective=Color(row["perspective"]), moves=moves, pgn=row["pgn"],
        )

    # ---------------- eval cache ----------------
    def get_eval(self, fen: str, depth: int) -> Optional[Evaluation]:
        row = self.conn.execute(
            "SELECT * FROM evals WHERE fen = ? AND depth = ?",
            (fen, depth)).fetchone()
        if row is None:
            return None
        return Evaluation(
            fen=row["fen"], depth=row["depth"], cp=row["cp"],
            mate=row["mate"], best_move=row["best_move"],
        )

    def put_eval(self, ev: Evaluation) -> None:
        self.conn.execute(
            """INSERT OR REPLACE INTO evals (fen, depth, cp, mate, best_move)
               VALUES (?,?,?,?,?)""",
            (ev.fen, ev.depth, ev.cp, ev.mate, ev.best_move),
        )
        self.conn.commit()

    def eval_cache_size(self) -> int:
        return self.conn.execute("SELECT COUNT(*) FROM evals").fetchone()[0]
