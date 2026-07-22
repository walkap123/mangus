"""Chess.com ingestion.

Pulls a player's public games from the chess.com Published-Data API and parses
them into the internal `Game` model.

API shape (all public, no auth):
    GET /pub/player/{username}/games/archives
        -> {"archives": ["https://api.chess.com/pub/player/{u}/games/2024/01", ...]}
    GET /pub/player/{username}/games/{YYYY}/{MM}
        -> {"games": [ {url, pgn, time_control, time_class, rated, rules,
                        end_time, eco?, white:{...}, black:{...}}, ... ]}

Notes that bite people:
  * chess.com now REQUIRES a descriptive User-Agent or returns 403. Set a real
    contact string.
  * Endpoints are Cloudflare-cached and rate-limited; on 429 we honor
    Retry-After and back off.
  * Games include variants (chess960, bughouse, ...). We keep only standard
    `rules == "chess"` by default so the eval/tagging layers can assume normal
    chess.
"""

from __future__ import annotations

import io
import time
from typing import Iterable, Iterator, Optional

import chess
import chess.pgn
import requests

from .models import (
    Color, Game, Player, Ply, epoch_to_dt,
)

API_BASE = "https://api.chess.com"
DEFAULT_UA = "chess-coach/0.1 (https://github.com/yourname/chess-coach; contact@example.com)"


class ChessComError(RuntimeError):
    pass


class PlayerNotFound(ChessComError):
    pass


class ChessComClient:
    def __init__(
        self,
        user_agent: str = DEFAULT_UA,
        *,
        timeout: float = 20.0,
        max_retries: int = 4,
        session: Optional[requests.Session] = None,
    ):
        self.timeout = timeout
        self.max_retries = max_retries
        self.session = session or requests.Session()
        self.session.headers.update({
            "User-Agent": user_agent,
            "Accept": "application/json",
        })

    # ---------------- low-level HTTP ----------------
    def _get(self, url: str) -> requests.Response:
        backoff = 1.0
        for attempt in range(self.max_retries + 1):
            resp = self.session.get(url, timeout=self.timeout)
            if resp.status_code == 200:
                return resp
            if resp.status_code == 404:
                raise PlayerNotFound(f"404 Not Found: {url}")
            if resp.status_code == 429 and attempt < self.max_retries:
                wait = float(resp.headers.get("Retry-After", backoff))
                time.sleep(wait)
                backoff = min(backoff * 2, 30)
                continue
            if resp.status_code >= 500 and attempt < self.max_retries:
                time.sleep(backoff)
                backoff = min(backoff * 2, 30)
                continue
            raise ChessComError(f"{resp.status_code} for {url}: {resp.text[:200]}")
        raise ChessComError(f"Exhausted retries for {url}")

    # ---------------- archives ----------------
    def list_archive_urls(self, username: str) -> list[str]:
        """Monthly archive URLs, oldest first."""
        url = f"{API_BASE}/pub/player/{username.lower()}/games/archives"
        data = self._get(url).json()
        return data.get("archives", [])

    def _fetch_archive(self, archive_url: str) -> list[dict]:
        return self._get(archive_url).json().get("games", [])

    # ---------------- public: iterate games ----------------
    def iter_games(
        self,
        username: str,
        *,
        rules: Optional[set[str]] = frozenset({"chess"}),
        time_classes: Optional[set[str]] = None,
        rated_only: bool = False,
        max_games: Optional[int] = None,
        newest_first: bool = True,
    ) -> Iterator[Game]:
        """Yield parsed `Game` objects for a username.

        rules: keep only these rule sets (default: standard chess). None = all.
        time_classes: e.g. {"blitz","rapid"}. None = all.
        max_games: stop after N (useful for a quick first pass).
        newest_first: process most recent archives first.
        """
        username = username.lower()
        archives = self.list_archive_urls(username)
        if newest_first:
            archives = list(reversed(archives))

        count = 0
        for archive_url in archives:
            raw_games = self._fetch_archive(archive_url)
            if newest_first:
                raw_games = list(reversed(raw_games))
            for raw in raw_games:
                if rules is not None and raw.get("rules") not in rules:
                    continue
                if time_classes is not None and raw.get("time_class") not in time_classes:
                    continue
                if rated_only and not raw.get("rated", False):
                    continue
                game = parse_game(raw, perspective_username=username)
                if game is None:
                    continue
                yield game
                count += 1
                if max_games is not None and count >= max_games:
                    return

    def fetch_games(self, username: str, **kwargs) -> list[Game]:
        return list(self.iter_games(username, **kwargs))


# ---------------- parsing ----------------
def _player_from_raw(raw_side: dict) -> Player:
    return Player(
        username=(raw_side.get("username") or "").lower(),
        rating=raw_side.get("rating"),
        result_raw=raw_side.get("result"),
    )


def parse_game(raw: dict, perspective_username: str) -> Optional[Game]:
    """Turn one chess.com game dict into an internal Game.

    Returns None for games we can't/shouldn't parse (no PGN, unfinished daily
    game with empty movetext, etc.).
    """
    pgn_text = raw.get("pgn")
    if not pgn_text:
        return None

    white = _player_from_raw(raw.get("white", {}))
    black = _player_from_raw(raw.get("black", {}))

    pu = perspective_username.lower()
    if pu == white.username:
        perspective = Color.WHITE
    elif pu == black.username:
        perspective = Color.BLACK
    else:
        # Username didn't match either side (rare: name change). Default white.
        perspective = Color.WHITE

    moves = parse_moves(pgn_text)

    return Game(
        game_id=raw.get("uuid") or raw.get("url", ""),
        url=raw.get("url", ""),
        played_at=epoch_to_dt(raw.get("end_time")),
        time_class=raw.get("time_class", ""),
        time_control=raw.get("time_control", ""),
        rated=bool(raw.get("rated", False)),
        rules=raw.get("rules", "chess"),
        eco=raw.get("eco"),
        white=white,
        black=black,
        perspective=perspective,
        moves=moves,
        pgn=pgn_text,
    )


def parse_moves(pgn_text: str) -> list[Ply]:
    """Replay a PGN into a list of Ply objects with FEN before/after each move."""
    game = chess.pgn.read_game(io.StringIO(pgn_text))
    if game is None:
        return []

    board = game.board()
    plies: list[Ply] = []
    ply_no = 0
    for node in game.mainline():
        move = node.move
        fen_before = board.fen()
        color = Color.WHITE if board.turn == chess.WHITE else Color.BLACK
        move_number = board.fullmove_number
        san = board.san(move)
        board.push(move)
        ply_no += 1
        plies.append(Ply(
            ply_number=ply_no,
            move_number=move_number,
            color=color,
            san=san,
            uci=move.uci(),
            fen_before=fen_before,
            fen_after=board.fen(),
            clock_seconds=_clock_from_node(node),
        ))
    return plies


def _clock_from_node(node) -> Optional[float]:
    """Extract [%clk H:MM:SS] from a PGN node comment, in seconds."""
    try:
        clk = node.clock()  # python-chess >= 1.0 parses %clk
    except Exception:
        return None
    return clk
