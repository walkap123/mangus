"""Offline tests for the move classifier, using a fake evaluator (no engine)."""

from chess_coach.models import Color, Evaluation, Ply
from chess_coach.classify import (
    MoveClass, MoveClassifier, Thresholds, win_prob, summarize,
)

START = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
AFTER_E4 = "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1"
AFTER_F3 = "rnbqkbnr/pppppppp/8/8/8/5P2/PPPPP1PP/RNBQKBNR b KQkq - 0 1"


class FakeEval:
    """Returns canned evals by FEN; mimics StockfishEval.evaluate()."""
    def __init__(self, table: dict[str, Evaluation]):
        self.table = table

    def evaluate(self, fen: str) -> Evaluation:
        return self.table[fen]


def test_win_prob():
    assert win_prob(0, None) == 0.5
    assert win_prob(None, 3) == 1.0          # mover has forced mate
    assert win_prob(None, -3) == 0.0         # mover gets mated
    assert win_prob(None, None) == 0.5       # unknown -> coin flip
    assert win_prob(1000, None) > 0.95       # crushing
    assert win_prob(-1000, None) < 0.05
    # symmetric around 0
    assert abs(win_prob(200, None) + win_prob(-200, None) - 1.0) < 1e-9
    print("  win_prob: mate, sign symmetry, monotonic OK")


def test_best_move_is_best():
    ply = Ply(1, 1, Color.WHITE, "e4", "e2e4", START, AFTER_E4)
    ev = FakeEval({
        # white slightly better before; engine's best IS what was played
        START: Evaluation(START, 18, cp=50, best_move="e2e4"),
        # black to move, black is 50 worse -> white kept the +50
        AFTER_E4: Evaluation(AFTER_E4, 18, cp=-50, best_move="e7e5"),
    })
    j = MoveClassifier().judge(ply, ev.evaluate(START), ev.evaluate(AFTER_E4))
    assert j.played_best is True
    assert j.win_prob_lost < 1e-9
    assert j.move_class is MoveClass.BEST
    print("  judge: engine top move -> BEST, ~0 win% lost OK")


def test_blunder():
    ply = Ply(1, 1, Color.WHITE, "f3", "f2f3", START, AFTER_F3)
    ev = FakeEval({
        # best was d2d4, player played f2f3 instead
        START: Evaluation(START, 18, cp=50, best_move="d2d4"),
        # black to move and now +300 for black -> white POV is -300
        AFTER_F3: Evaluation(AFTER_F3, 18, cp=300, best_move="e7e5"),
    })
    j = MoveClassifier().judge(ply, ev.evaluate(START), ev.evaluate(AFTER_F3))
    assert j.played_best is False
    # ~0.55 -> ~0.23, lost ~0.32
    assert j.win_prob_lost > 0.30
    assert j.move_class is MoveClass.BLUNDER
    print(f"  judge: eval swing -> BLUNDER (lost {j.win_prob_lost:.2f}) OK")


def test_buckets():
    c = MoveClassifier(Thresholds())
    assert c._bucket(0.00, played_best=False) is MoveClass.BEST      # within eps
    assert c._bucket(0.05, played_best=False) is MoveClass.GOOD
    assert c._bucket(0.15, played_best=False) is MoveClass.INACCURACY
    assert c._bucket(0.25, played_best=False) is MoveClass.MISTAKE
    assert c._bucket(0.40, played_best=False) is MoveClass.BLUNDER
    # played_best overrides even a tiny nonzero loss
    assert c._bucket(0.015, played_best=True) is MoveClass.BEST
    print("  buckets: eps/inaccuracy/mistake/blunder boundaries OK")


def test_classify_game_mine_only():
    # two plies: white best, black blunder. mine_only=white -> only white judged.
    from chess_coach.models import Game, Player
    plies = [
        Ply(1, 1, Color.WHITE, "e4", "e2e4", START, AFTER_E4),
        Ply(2, 1, Color.BLACK, "f6", "f7f6", AFTER_E4, AFTER_F3),  # dummy after
    ]
    g = Game(
        game_id="g1", url="", played_at=None, time_class="blitz",
        time_control="300", rated=True, rules="chess", eco=None,
        white=Player("me", 1500), black=Player("them", 1500),
        perspective=Color.WHITE, moves=plies,
    )
    ev = FakeEval({
        START: Evaluation(START, 18, cp=50, best_move="e2e4"),
        AFTER_E4: Evaluation(AFTER_E4, 18, cp=-50, best_move="e7e5"),
        AFTER_F3: Evaluation(AFTER_F3, 18, cp=0),
    })
    all_j = MoveClassifier().classify_game(g, ev)
    mine = MoveClassifier().classify_game(g, ev, mine_only=True)
    assert len(all_j) == 2 and len(mine) == 1
    assert mine[0].color is Color.WHITE
    counts = summarize(all_j)
    assert counts[MoveClass.BEST] >= 1
    print("  classify_game: mine_only filter + summarize OK")


if __name__ == "__main__":
    print("Running classifier tests...")
    test_win_prob()
    test_best_move_is_best()
    test_blunder()
    test_buckets()
    test_classify_game_mine_only()
    print("ALL PASSED")
