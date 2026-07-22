"""Semantic tag layer — the differentiator.

Where the classifier says *how bad* a move was (win% lost), the tag layer says
*what kind* of mistake it was — the human-meaningful label a coach reasons over
and rolls up across games ("you hang pieces in time trouble").

First detector: **hung piece**. It fires only when two independent signals
agree:

  1. the classifier flagged a real eval swing against the mover (so we never
     tag a sound sacrifice or a position that was already lost), AND
  2. a **static exchange evaluation (SEE)** on the resulting position shows the
     opponent can win material outright with a capture.

SEE is our own implementation of the standard swap-off algorithm (an algorithm,
not borrowed code): on the target square, both sides recapture with their
least-valuable attacker in turn, and either side may stop when continuing would
lose material. Because we make each capture on a board copy, x-ray attackers
revealed behind a mover are handled for free.

Detectors read only `Game` + the classifier's `MoveJudgment`s, so they stay
engine-agnostic (the eval swing is already baked into the judgments).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Protocol

import chess

from .classify import MoveJudgment
from .models import Color, Game, Ply

# Rough material values in centipawns. King is nominal (it's never actually
# captured; the value just keeps it last in the swap order).
PIECE_VALUE = {
    chess.PAWN: 100, chess.KNIGHT: 300, chess.BISHOP: 300,
    chess.ROOK: 500, chess.QUEEN: 900, chess.KING: 10_000,
}


@dataclass
class Tag:
    """A semantic label attached to one ply.

    `punished` separates what you *did* from what it *cost*: the tag fires on the
    mistake (the piece was hangable), but `punished` records whether the opponent
    actually took it on their real next move. An unpunished hang is still a habit
    worth fixing — it is NOT why you lost the game.
    """
    name: str                 # e.g. "hung_piece"
    ply_number: int
    color: Color              # whose move earned the tag
    san: str
    detail: str               # human phrase, e.g. "hung a knight on e5 (-3)"
    win_prob_lost: Optional[float] = None
    material_cp: Optional[int] = None    # material the opponent wins (SEE)
    victim_square: Optional[str] = None  # e.g. "e5"
    victim_piece: Optional[str] = None   # e.g. "knight"
    punished: Optional[bool] = None      # did the opponent actually take it?


# ---------------- static exchange evaluation ----------------
def _least_valuable_attacker(board: chess.Board, sq: int, side: bool) -> Optional[int]:
    attackers = board.attackers(side, sq)
    if not attackers:
        return None
    return min(attackers, key=lambda s: PIECE_VALUE[board.piece_at(s).piece_type])


def _see_recapture(board: chess.Board, sq: int, side: bool) -> int:
    """Best material `side` can gain by (optionally) recapturing on `sq`."""
    lva = _least_valuable_attacker(board, sq, side)
    if lva is None:
        return 0
    piece = board.piece_at(lva)
    # A king can't capture into a square the opponent still defends.
    if piece.piece_type == chess.KING and board.attackers(not side, sq):
        return 0
    captured_value = PIECE_VALUE[board.piece_at(sq).piece_type]
    promo = (chess.QUEEN if piece.piece_type == chess.PAWN
             and chess.square_rank(sq) in (0, 7) else None)
    board.push(chess.Move(lva, sq, promotion=promo))
    gain = captured_value - _see_recapture(board, sq, not side)
    board.pop()
    return max(0, gain)  # standing pat: don't recapture if it loses material


def static_exchange_eval(board: chess.Board, move: chess.Move) -> int:
    """Net material (centipawns) for the side making capturing `move`.

    Positive means the capture wins material even after every recapture.
    """
    to_sq = move.to_square
    if board.is_en_passant(move):
        captured_value = PIECE_VALUE[chess.PAWN]
    else:
        target = board.piece_at(to_sq)
        if target is None:
            return 0
        captured_value = PIECE_VALUE[target.piece_type]
    board = board.copy(stack=False)
    board.push(move)
    return captured_value - _see_recapture(board, to_sq, board.turn)


def _move_capture_value(fen_before: str, uci: str) -> int:
    """Material (centipawns) the mover captured with their own move, else 0."""
    board = chess.Board(fen_before)
    move = chess.Move.from_uci(uci)
    if not board.is_capture(move):
        return 0
    if board.is_en_passant(move):
        return PIECE_VALUE[chess.PAWN]
    target = board.piece_at(move.to_square)
    return PIECE_VALUE[target.piece_type] if target else 0


def best_free_capture(board: chess.Board) -> Optional[tuple[int, int, int]]:
    """Best material-winning capture for the side to move.

    Returns (see_cp, to_square, victim_piece_type) for the capture with the
    highest positive SEE, or None if no capture wins material.
    """
    best: Optional[tuple[int, int, int]] = None
    for move in board.legal_moves:
        if not board.is_capture(move):
            continue
        see = static_exchange_eval(board, move)
        if see <= 0:
            continue
        victim = (chess.PAWN if board.is_en_passant(move)
                  else board.piece_at(move.to_square).piece_type)
        if best is None or see > best[0]:
            best = (see, move.to_square, victim)
    return best


# ---------------- detectors ----------------
class Detector(Protocol):
    def detect(self, game: Game, judgments: list[MoveJudgment]) -> list[Tag]: ...


class HungPieceDetector:
    """Flags a move that left a piece hanging for a material-losing swing.

    min_swing:   minimum win% lost (classifier) to consider the move a real
                 mistake — the guard against tagging sound sacrifices.
    min_material: minimum SEE (centipawns) the opponent wins — default a minor
                 piece, so "hung a pawn" doesn't count as hanging a *piece*.
    """

    name = "hung_piece"

    def __init__(self, *, min_swing: float = 0.15, min_material: int = 300):
        self.min_swing = min_swing
        self.min_material = min_material

    def detect(self, game: Game, judgments: list[MoveJudgment]) -> list[Tag]:
        jmap = {j.ply_number: j for j in judgments}
        by_num = {p.ply_number: p for p in game.moves}
        tags: list[Tag] = []
        for ply in game.moves:
            j = jmap.get(ply.ply_number)
            if j is None or j.win_prob_lost < self.min_swing:
                continue
            # In the position after the move, can the opponent grab material?
            board = chess.Board(ply.fen_after)
            cap = best_free_capture(board)
            if cap is None:
                continue
            see_cp, to_sq, victim_type = cap
            # If the move was itself a capture, net out what it grabbed — losing
            # a queen to win a knight is a -6 blunder, not -9.
            net_cp = see_cp - _move_capture_value(ply.fen_before, ply.uci)
            if net_cp < self.min_material:
                continue
            piece = chess.piece_name(victim_type)        # "knight"
            square = chess.square_name(to_sq)            # "e5"
            # Did the opponent actually take it on their real next move?
            nxt = by_num.get(ply.ply_number + 1)
            punished = bool(nxt and nxt.uci[2:4] == square)
            note = "" if punished else " — opponent missed it"
            tags.append(Tag(
                name=self.name, ply_number=ply.ply_number, color=ply.color,
                san=ply.san,
                detail=f"hung a {piece} on {square} (-{net_cp // 100}){note}",
                win_prob_lost=j.win_prob_lost, material_cp=net_cp,
                victim_square=square, victim_piece=piece, punished=punished,
            ))
        return tags


# Material values for counting (no king — it's never captured).
_MATERIAL = {chess.PAWN: 100, chess.KNIGHT: 300, chess.BISHOP: 300,
             chess.ROOK: 500, chess.QUEEN: 900}


def _my_material(board: chess.Board, me_white: bool) -> int:
    """(my material − opponent material) in centipawns, from my POV."""
    diff = sum(v * (len(board.pieces(pt, chess.WHITE))
                    - len(board.pieces(pt, chess.BLACK)))
               for pt, v in _MATERIAL.items())
    return diff if me_white else -diff


class AllowedTacticDetector:
    """Flags a move that let the opponent win material by force over the next
    few moves — a combination, not a one-move hang.

    Fires only when the move was a real error AND actually **punished** (the
    opponent kept the advantage in the real game) AND material actually shifts
    to the opponent within `lookahead` plies. A one-move free capture is left to
    HungPieceDetector, so the two never double-label the same move.
    """

    name = "allowed_tactic"

    def __init__(self, *, min_swing: float = 0.15, min_material: int = 300,
                 lookahead: int = 6):
        self.min_swing = min_swing
        self.min_material = min_material
        self.lookahead = lookahead

    def detect(self, game: Game, judgments: list[MoveJudgment]) -> list[Tag]:
        jmap = {j.ply_number: j for j in judgments}
        by_num = {p.ply_number: p for p in game.moves}
        if not by_num:
            return []
        max_ply = max(by_num)
        me_white = game.perspective is Color.WHITE
        tags: list[Tag] = []
        for ply in game.moves:
            j = jmap.get(ply.ply_number)
            if j is None or not j.punished or j.win_prob_lost < self.min_swing:
                continue
            after = chess.Board(ply.fen_after)
            # A one-move free capture is a hung piece, not a combination — skip.
            cap = best_free_capture(after)
            if cap is not None:
                net = cap[0] - _move_capture_value(ply.fen_before, ply.uci)
                if net >= self.min_material:
                    continue
            # Did material actually swing to the opponent over the next few plies?
            end_ply = by_num.get(min(ply.ply_number + self.lookahead, max_ply))
            if end_ply is None or end_ply.ply_number <= ply.ply_number:
                continue
            lost = _my_material(after, me_white) - _my_material(
                chess.Board(end_ply.fen_after), me_white)
            if lost < self.min_material:
                continue
            tags.append(Tag(
                name=self.name, ply_number=ply.ply_number, color=ply.color,
                san=ply.san, detail=f"allowed a tactic (-{lost // 100})",
                win_prob_lost=j.win_prob_lost, material_cp=lost, punished=True,
            ))
        return tags


class AllowedAttackDetector:
    """Flags a move that let the opponent's ATTACK decide the game with (almost)
    no material change — you walked into a mating attack, or got positionally
    crushed. The material detectors (hung-piece, allowed-tactic) structurally
    can't see these, so this covers the gap.

    Gated on: real error + punished + win% actually *collapsed* to losing +
    (almost) no material swing + **evidence of an actual attack** on your king
    (the opponent delivers checks, or mate). Without that king-pressure evidence
    a non-material collapse is left as a generic blunder — it might be squandered
    compensation or positional drift, and we won't call that an "attack".
    """

    name = "allowed_attack"

    def __init__(self, *, min_swing: float = 0.20, collapse_to: float = 0.30,
                 material_ceiling: int = 100, lookahead: int = 6):
        self.min_swing = min_swing
        self.collapse_to = collapse_to        # win% must fall to at most this
        self.material_ceiling = material_ceiling  # opponent gains less than this
        self.lookahead = lookahead

    def detect(self, game: Game, judgments: list[MoveJudgment]) -> list[Tag]:
        jmap = {j.ply_number: j for j in judgments}
        by_num = {p.ply_number: p for p in game.moves}
        if not by_num:
            return []
        max_ply = max(by_num)
        me_white = game.perspective is Color.WHITE
        tags: list[Tag] = []
        for ply in game.moves:
            j = jmap.get(ply.ply_number)
            if j is None or not j.punished or j.win_prob_lost < self.min_swing:
                continue
            if j.win_prob_after_reply is None or j.win_prob_after_reply > self.collapse_to:
                continue
            # Must be (almost) non-material, else a tactic/hang already owns it.
            end_ply = by_num.get(min(ply.ply_number + self.lookahead, max_ply))
            if end_ply is not None and end_ply.ply_number > ply.ply_number:
                lost = (_my_material(chess.Board(ply.fen_after), me_white)
                        - _my_material(chess.Board(end_ply.fen_after), me_white))
            else:
                lost = 0
            if lost >= self.material_ceiling:
                continue
            # Only call it an attack if the opponent actually pressured my king.
            checks, mate = self._king_pressure(
                by_num, ply.ply_number, max_ply, game.perspective)
            if not mate and checks == 0:
                continue
            tags.append(Tag(
                name=self.name, ply_number=ply.ply_number, color=ply.color,
                san=ply.san,
                detail="allowed a mating attack" if mate else "allowed an attack on your king",
                win_prob_lost=j.win_prob_lost, punished=True,
            ))
        return tags

    def _king_pressure(self, by_num: dict[int, Ply], start: int, max_ply: int,
                       me: Color) -> tuple[int, bool]:
        """(opponent checks against me, mated) over the lookahead window."""
        checks, mate = 0, False
        for n in range(start + 1, min(start + self.lookahead, max_ply) + 1):
            p = by_num.get(n)
            if p is None:
                break
            if p.color is me:            # only the opponent's moves attack me
                continue
            b = chess.Board(p.fen_after)
            if b.is_check():
                side = Color.WHITE if b.turn == chess.WHITE else Color.BLACK
                if side is me:
                    checks += 1
                    if b.is_checkmate():
                        mate = True
        return checks, mate


def tag_game(
    game: Game,
    judgments: list[MoveJudgment],
    detectors: Optional[list[Detector]] = None,
) -> list[Tag]:
    """Run detectors over a classified game; tags sorted by ply."""
    if detectors is None:
        detectors = [HungPieceDetector(), AllowedTacticDetector(),
                     AllowedAttackDetector()]
    tags: list[Tag] = []
    for d in detectors:
        tags.extend(d.detect(game, judgments))
    tags.sort(key=lambda t: t.ply_number)
    return tags
