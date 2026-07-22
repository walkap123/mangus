"""Internal data models for the chess coach engine.

These are the clean, engine-agnostic representations that every downstream
layer reads from:

    ingestion  ->  Game / Ply   ->  (eval layer)  ->  (tagging layer)  ->  coach

Keeping this layer free of any chess.com or Stockfish specifics means we can
swap data sources (Lichess later?) or engines without touching downstream code.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional


class Color(str, Enum):
    WHITE = "white"
    BLACK = "black"

    @property
    def opponent(self) -> "Color":
        return Color.BLACK if self is Color.WHITE else Color.WHITE


class GameResult(str, Enum):
    """Result from the perspective of a specific player."""
    WIN = "win"
    LOSS = "loss"
    DRAW = "draw"
    UNKNOWN = "unknown"


@dataclass
class Player:
    username: str
    rating: Optional[int] = None
    # Raw chess.com result string, e.g. "win", "checkmated", "resigned",
    # "timeout", "stalemate", "agreed", "repetition", "insufficient".
    result_raw: Optional[str] = None


# chess.com encodes the outcome per side. "win" is the only winning token;
# everything else is either a loss reason or a draw reason.
_DRAW_RESULTS = {
    "agreed", "stalemate", "repetition", "insufficient",
    "50move", "timevsinsufficient",
}


def result_for(player: Player) -> GameResult:
    r = (player.result_raw or "").lower()
    if r == "win":
        return GameResult.WIN
    if r in _DRAW_RESULTS:
        return GameResult.DRAW
    if r == "":
        return GameResult.UNKNOWN
    # anything else (checkmated, resigned, timeout, abandoned, lose, ...) is a loss
    return GameResult.LOSS


@dataclass
class Ply:
    """A single half-move, with everything the eval layer needs.

    `fen_before` is the position the mover faced; `uci`/`san` is what they
    played. To evaluate a move you eval `fen_before`, then eval the position
    after `uci`, and compare — that centipawn delta is the raw signal the
    classifier turns into blunder/mistake/good/best.
    """
    ply_number: int          # 1-based half-move index
    move_number: int         # full-move number (1, 1, 2, 2, ...)
    color: Color             # side that moved
    san: str                 # e.g. "Nf3"
    uci: str                 # e.g. "g1f3"
    fen_before: str          # position before the move
    fen_after: str           # position after the move
    clock_seconds: Optional[float] = None  # time left after move, if in PGN


@dataclass(frozen=True)
class Evaluation:
    """Engine evaluation of one position, from the side-to-move's POV.

    A FEN fully determines whose turn it is, so keeping evals side-to-move
    relative means the value depends only on the position — which is exactly
    what lets us cache by FEN and share hits across every game.

    Exactly one of `cp` / `mate` carries the signal:
      cp:   centipawns; positive = side to move is better.
      mate: signed mate distance; +N = side to move mates in N,
            -N = side to move is mated in N.
    `best_move` is the engine's principal-variation first move (UCI), handy
    later for "there was a better move / missed tactic" tagging.
    """
    fen: str
    depth: int
    cp: Optional[int] = None
    mate: Optional[int] = None
    best_move: Optional[str] = None

    def pov(self, mover: "Color") -> "Evaluation":
        """Return this eval from `mover`'s POV.

        Stockfish reports relative to the side to move. When you evaluate the
        position *after* a move it's the opponent's turn, so to compare a move's
        before/after from the mover's angle you negate the 'after' eval.
        """
        stm = Color.WHITE if self.fen.split(" ")[1] == "w" else Color.BLACK
        if stm is mover:
            return self
        return Evaluation(
            fen=self.fen, depth=self.depth,
            cp=None if self.cp is None else -self.cp,
            mate=None if self.mate is None else -self.mate,
            best_move=self.best_move,
        )


@dataclass
class Game:
    """One parsed game, normalized and perspective-aware.

    `perspective` is the color of the user we ingested for, so downstream
    coaching ("you hung a piece") always knows which side is 'you'.
    """
    game_id: str
    url: str
    played_at: Optional[datetime]
    time_class: str          # bullet | blitz | rapid | daily
    time_control: str        # raw e.g. "600" or "1/259200"
    rated: bool
    rules: str               # "chess", "chess960", ...
    eco: Optional[str]

    white: Player
    black: Player

    perspective: Color
    moves: list[Ply] = field(default_factory=list)

    pgn: str = ""

    # ---- perspective-aware convenience accessors ----
    @property
    def me(self) -> Player:
        return self.white if self.perspective is Color.WHITE else self.black

    @property
    def opponent(self) -> Player:
        return self.black if self.perspective is Color.WHITE else self.white

    @property
    def result(self) -> GameResult:
        return result_for(self.me)

    @property
    def my_rating(self) -> Optional[int]:
        return self.me.rating

    @property
    def opponent_rating(self) -> Optional[int]:
        return self.opponent.rating

    def my_plies(self) -> list[Ply]:
        """Only the half-moves the user actually played."""
        return [p for p in self.moves if p.color is self.perspective]

    def __repr__(self) -> str:
        d = self.played_at.date().isoformat() if self.played_at else "?"
        return (f"<Game {self.white.username} vs {self.black.username} "
                f"{self.time_class} {d} me={self.perspective.value} "
                f"result={self.result.value} plies={len(self.moves)}>")


def epoch_to_dt(end_time: Optional[int]) -> Optional[datetime]:
    if not end_time:
        return None
    return datetime.fromtimestamp(end_time, tz=timezone.utc)
