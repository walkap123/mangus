"""Offline tests for the tag layer: SEE correctness + hung-piece detection."""

import chess

from chess_coach.models import Color, Game, Player, Ply
from chess_coach.classify import MoveClass, MoveJudgment
from chess_coach.tag import (
    HungPieceDetector, tag_game, static_exchange_eval, best_free_capture,
)

# Black to move; White just parked a knight on e5 where a pawn wins it free.
HUNG_KNIGHT = "4k3/8/3p4/4N3/8/8/8/4K3 b - - 0 1"
# Black to move; the e5 knight is defended by the f4 pawn -> even trade, and
# nothing else on the board hangs.
DEFENDED_KNIGHT = "4k3/8/2n5/4N3/5P2/8/8/4K3 b - - 0 1"
# Black to move; nothing to capture at all.
QUIET = "4k3/8/8/8/8/8/5PPP/4K3 b - - 0 1"


def test_see_free_piece():
    board = chess.Board(HUNG_KNIGHT)
    see = static_exchange_eval(board, chess.Move.from_uci("d6e5"))
    assert see == 300, see  # wins a whole knight
    print("  SEE: free knight = +300 OK")


def test_see_equal_trade():
    board = chess.Board(DEFENDED_KNIGHT)
    # Nc6xe5, pawn recaptures -> knight for knight, net 0.
    see = static_exchange_eval(board, chess.Move.from_uci("c6e5"))
    assert see == 0, see
    print("  SEE: defended knight (even trade) = 0 OK")


def test_best_free_capture():
    assert best_free_capture(chess.Board(HUNG_KNIGHT))[0] == 300
    assert best_free_capture(chess.Board(DEFENDED_KNIGHT)) is None
    assert best_free_capture(chess.Board(QUIET)) is None
    print("  best_free_capture: picks the winning capture, else None OK")


def _judgment(ply_number, lost, cls=MoveClass.BLUNDER):
    return MoveJudgment(
        ply_number=ply_number, color=Color.WHITE, san="Ne5", uci="c4e5",
        move_class=cls, win_prob_before=0.55, win_prob_after=0.55 - lost,
        win_prob_lost=lost, best_move="d2d4", played_best=False,
    )


def _game(fen_after):
    ply = Ply(
        ply_number=5, move_number=3, color=Color.WHITE, san="Ne5", uci="c4e5",
        fen_before="4k3/8/3p4/8/2N5/8/8/4K3 w - - 0 1", fen_after=fen_after,
    )
    return Game(
        game_id="g", url="", played_at=None, time_class="blitz",
        time_control="300", rated=True, rules="chess", eco=None,
        white=Player("me", 1500), black=Player("them", 1500),
        perspective=Color.WHITE, moves=[ply],
    )


def test_hung_piece_detected():
    game = _game(HUNG_KNIGHT)
    tags = tag_game(game, [_judgment(5, 0.35)])
    assert len(tags) == 1, tags
    t = tags[0]
    assert t.name == "hung_piece" and t.color is Color.WHITE
    assert t.victim_piece == "knight" and t.victim_square == "e5"
    assert t.material_cp == 300
    assert "hung a knight on e5" in t.detail
    print(f"  detect: {t.detail!r} OK")


def test_no_tag_when_swing_too_small():
    # Free piece on the board, but the classifier says the move barely hurt
    # (e.g. already winning) -> not attributed as a hang.
    game = _game(HUNG_KNIGHT)
    tags = tag_game(game, [_judgment(5, 0.04, cls=MoveClass.GOOD)])
    assert tags == []
    print("  gate: big free capture but tiny eval swing -> no tag OK")


def test_no_tag_when_no_free_capture():
    # Big swing, but nothing hanging (blunder was positional / a threat).
    game = _game(QUIET)
    tags = tag_game(game, [_judgment(5, 0.40)])
    assert tags == []
    # Defended piece (even trade) also shouldn't flag despite a big swing.
    assert tag_game(_game(DEFENDED_KNIGHT), [_judgment(5, 0.40)]) == []
    print("  gate: swing without a material-winning capture -> no tag OK")


def test_no_tag_on_even_trade():
    # Regression (found on real games): Qxd7 captures a QUEEN, gets recaptured
    # by a knight. Big eval swing (bad trade), but net material is 0 -> it is a
    # blunder, NOT a hung piece. Must not be tagged.
    before = "5nk1/3q4/8/8/8/3Q4/8/6K1 w - - 0 1"   # white Qd3, black Qd7 (def by Nf8)
    after = "5nk1/3Q4/8/8/8/8/8/6K1 b - - 0 1"      # after Qxd7, black to move
    ply = Ply(63, 32, Color.WHITE, "Qxd7+", "d3d7", before, after)
    game = Game(
        game_id="g", url="", played_at=None, time_class="rapid",
        time_control="600", rated=True, rules="chess", eco=None,
        white=Player("me", 1500), black=Player("them", 1500),
        perspective=Color.WHITE, moves=[ply],
    )
    j = MoveJudgment(63, Color.WHITE, "Qxd7+", "d3d7", MoveClass.BLUNDER,
                     0.60, 0.30, 0.30, "a1a2", False)
    assert tag_game(game, [j]) == []
    print("  gate: capture that's an even trade (big swing) -> no tag OK")


if __name__ == "__main__":
    print("Running tag tests...")
    test_see_free_piece()
    test_see_equal_trade()
    test_best_free_capture()
    test_hung_piece_detected()
    test_no_tag_when_swing_too_small()
    test_no_tag_when_no_free_capture()
    test_no_tag_on_even_trade()
    print("ALL PASSED")
