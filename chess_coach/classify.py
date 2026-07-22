"""Move classifier.

Turns engine evals into human labels: best / good / inaccuracy / mistake /
blunder. The method (not the code) is the well-known one: map each eval to a
**win probability**, then judge a move by how much win probability it threw
away versus the best available move.

    win% lost = winprob(position before, from mover's POV)
              - winprob(position after,  from mover's POV)

The eval of the position *before* a move already reflects best play, so it's
the win% the mover could have kept; the eval *after* is what they actually got.
This is our own implementation end to end (logistic below is ours, tunable) so
nothing here is derived from another project's source.

Engine-agnostic: it consumes `Evaluation`s via any object with `.evaluate(fen)`
(e.g. `StockfishEval`, cache-first), and never talks to an engine itself.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, replace
from enum import Enum
from typing import Optional, Protocol

from .models import Color, Evaluation, Game, GameResult, Ply

# Logistic steepness mapping centipawns -> win probability. Our own choice:
# ~+100cp ≈ 60%, ~+300cp ≈ 77%, ~+600cp ≈ 92%. Tune in one place.
CP_TO_WINPROB_K = 0.004


class MoveClass(str, Enum):
    BEST = "best"
    GOOD = "good"
    INACCURACY = "inaccuracy"
    MISTAKE = "mistake"
    BLUNDER = "blunder"


# Win-probability lost thresholds (fractions of 1.0). A move is judged by the
# first bucket it falls into. These are plain numbers, tune to taste.
@dataclass(frozen=True)
class Thresholds:
    best_eps: float = 0.02     # <= this (and not clearly worse) counts as best
    inaccuracy: float = 0.10
    mistake: float = 0.20
    blunder: float = 0.30


def win_prob(cp: Optional[int], mate: Optional[int]) -> float:
    """Win probability in [0,1] for the side to move.

    `cp`/`mate` must already be from the POV you want the probability for.
    """
    if mate is not None:
        return 1.0 if mate > 0 else 0.0
    if cp is None:
        return 0.5
    return 1.0 / (1.0 + math.exp(-CP_TO_WINPROB_K * cp))


@dataclass(frozen=True)
class MoveJudgment:
    ply_number: int
    color: Color
    san: str
    uci: str
    move_class: MoveClass
    win_prob_before: float     # mover POV, best play available
    win_prob_after: float      # mover POV, engine best-play eval AFTER the move
    win_prob_lost: float       # >= 0, the *potential* damage (assumes best reply)
    best_move: Optional[str]   # engine's best move (UCI) at fen_before
    played_best: bool
    # ---- actual consequence (filled by classify_game; needs game context) ----
    # win_prob_after is hypothetical: it assumes the opponent punishes perfectly.
    # These record what actually happened on the board:
    win_prob_after_reply: Optional[float] = None  # mover POV after opponent's REAL reply
    retained_loss: Optional[float] = None          # win% that actually stuck (>= 0)
    punished: Optional[bool] = None                # opponent kept most of the damage?


class Evaluator(Protocol):
    def evaluate(self, fen: str) -> Evaluation: ...


class MoveClassifier:
    def __init__(self, thresholds: Thresholds = Thresholds(), *, punish_ratio: float = 0.5):
        self.t = thresholds
        # A move counts as "punished" if, after the opponent's ACTUAL reply, at
        # least this fraction of the win% it handed over actually stuck.
        self.punish_ratio = punish_ratio

    def judge(
        self, ply: Ply, eval_before: Evaluation, eval_after: Evaluation
    ) -> MoveJudgment:
        """Classify a single ply from precomputed before/after evals."""
        mover = ply.color
        # eval_before's side to move IS the mover, so it's already mover-POV.
        wp_before = win_prob(eval_before.cp, eval_before.mate)
        # eval_after's side to move is the opponent; flip to mover-POV.
        after = eval_after.pov(mover)
        wp_after = win_prob(after.cp, after.mate)
        lost = max(0.0, wp_before - wp_after)

        played_best = (
            eval_before.best_move is not None
            and ply.uci == eval_before.best_move
        )
        move_class = self._bucket(lost, played_best)

        return MoveJudgment(
            ply_number=ply.ply_number, color=mover, san=ply.san, uci=ply.uci,
            move_class=move_class, win_prob_before=wp_before,
            win_prob_after=wp_after, win_prob_lost=lost,
            best_move=eval_before.best_move, played_best=played_best,
        )

    def _bucket(self, lost: float, played_best: bool) -> MoveClass:
        if played_best or lost <= self.t.best_eps:
            return MoveClass.BEST
        if lost < self.t.inaccuracy:
            return MoveClass.GOOD
        if lost < self.t.mistake:
            return MoveClass.INACCURACY
        if lost < self.t.blunder:
            return MoveClass.MISTAKE
        return MoveClass.BLUNDER

    def classify_game(
        self, game: Game, evaluator: Evaluator, *, mine_only: bool = False
    ) -> list[MoveJudgment]:
        """Judge every ply of a game (or just the user's, if mine_only).

        Pulls evals through `evaluator` (cache-first when it's a StockfishEval
        backed by a Store), so this costs nothing beyond warming the cache.
        """
        by_num = {p.ply_number: p for p in game.moves}
        out: list[MoveJudgment] = []
        for ply in game.moves:
            if mine_only and ply.color is not game.perspective:
                continue
            eval_before = evaluator.evaluate(ply.fen_before)
            eval_after = evaluator.evaluate(ply.fen_after)
            j = self.judge(ply, eval_before, eval_after)
            out.append(self._with_consequence(j, by_num, game, evaluator))
        return out

    def _with_consequence(
        self, j: MoveJudgment, by_num: dict[int, Ply], game: Game,
        evaluator: Evaluator,
    ) -> MoveJudgment:
        """Attach what the move ACTUALLY cost, from the game's real continuation.

        The position the mover faces two plies later (after the opponent's real
        reply) is their next move's `fen_before` — already evaluated when we
        judge that move, so this is free from the cache. If the mover has no
        next move, the game ended within one reply; fall back to the result.
        """
        nxt2 = by_num.get(j.ply_number + 2)
        if nxt2 is not None:
            ev = evaluator.evaluate(nxt2.fen_before)  # mover is to move -> mover POV
            wp_reply = win_prob(ev.cp, ev.mate)
        else:
            wp_reply = {GameResult.WIN: 1.0, GameResult.LOSS: 0.0,
                        GameResult.DRAW: 0.5}.get(game.result)
            if wp_reply is None:
                return j
        retained = max(0.0, j.win_prob_before - wp_reply)
        punished = (j.win_prob_lost > 1e-9
                    and retained >= self.punish_ratio * j.win_prob_lost)
        return replace(j, win_prob_after_reply=wp_reply, retained_loss=retained,
                       punished=punished)


def summarize(judgments: list[MoveJudgment]) -> dict[MoveClass, int]:
    """Count judgments by class (handy for a quick per-game/coach rollup)."""
    counts = {mc: 0 for mc in MoveClass}
    for j in judgments:
        counts[j.move_class] += 1
    return counts
