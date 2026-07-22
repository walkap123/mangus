"""Offline tests for the tag layer: SEE correctness + hung-piece detection."""

import chess

from chess_coach.models import Color, Game, Player, Ply
from chess_coach.classify import MoveClass, MoveJudgment
from chess_coach.tag import (
    HungPieceDetector, AllowedTacticDetector, AllowedAttackDetector, tag_game,
    static_exchange_eval, best_free_capture,
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


def test_punished_flag():
    # Ply 5: White hangs the knight on e5. Ply 6: Black actually takes it.
    hang = Ply(5, 3, Color.WHITE, "Ne5", "c4e5",
               "4k3/8/3p4/8/2N5/8/8/4K3 w - - 0 1", HUNG_KNIGHT)
    take = Ply(6, 3, Color.BLACK, "dxe5", "d6e5", HUNG_KNIGHT,
               "4k3/8/8/4p3/8/8/8/4K3 w - - 0 2")
    g = Game(
        game_id="g", url="", played_at=None, time_class="blitz",
        time_control="300", rated=True, rules="chess", eco=None,
        white=Player("me", 1500), black=Player("them", 1500),
        perspective=Color.WHITE, moves=[hang, take],
    )
    tag = tag_game(g, [_judgment(5, 0.35)])[0]
    assert tag.punished is True and "missed" not in tag.detail
    # same hang but no follow-up capture in the game -> not punished
    g2 = _game(HUNG_KNIGHT)  # single ply, no reply
    tag2 = tag_game(g2, [_judgment(5, 0.35)])[0]
    assert tag2.punished is False and "opponent missed it" in tag2.detail
    print("  punished flag: taken=True / not-taken=False OK")


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


def test_allowed_tactic():
    # White (me) plays Re1, allowing a knight fork that wins the rook over the
    # next moves: ...Nf3+ Kf1 Nxe1. Multi-move, not a one-move hang.
    p5 = Ply(5, 3, Color.WHITE, "Re1", "a1e1",
             "6k1/8/8/6n1/8/8/8/R5K1 w - - 0 1", "6k1/8/8/6n1/8/8/8/4R1K1 b - - 1 1")
    p6 = Ply(6, 3, Color.BLACK, "Nf3+", "g5f3",
             p5.fen_after, "6k1/8/8/8/8/5n2/8/4R1K1 w - - 2 2")
    p7 = Ply(7, 4, Color.WHITE, "Kf1", "g1f1",
             p6.fen_after, "6k1/8/8/8/8/5n2/8/4RK2 b - - 3 2")
    p8 = Ply(8, 4, Color.BLACK, "Nxe1", "f3e1",
             p7.fen_after, "6k1/8/8/8/8/8/8/4nK2 w - - 0 3")
    game = Game(
        game_id="g", url="", played_at=None, time_class="rapid",
        time_control="600", rated=True, rules="chess", eco=None,
        white=Player("me", 1500), black=Player("them", 1500),
        perspective=Color.WHITE, moves=[p5, p6, p7, p8])

    punished = MoveJudgment(5, Color.WHITE, "Re1", "a1e1", MoveClass.BLUNDER,
                            0.60, 0.20, 0.40, "a1a2", False,
                            win_prob_after_reply=0.20, retained_loss=0.40, punished=True)
    tags = AllowedTacticDetector().detect(game, [punished])
    assert len(tags) == 1 and tags[0].name == "allowed_tactic", tags
    assert tags[0].material_cp == 500 and "allowed a tactic (-5)" in tags[0].detail

    # got away with it (not punished) -> no tag
    unpun = MoveJudgment(5, Color.WHITE, "Re1", "a1e1", MoveClass.BLUNDER,
                         0.60, 0.55, 0.05, "a1a2", False,
                         win_prob_after_reply=0.55, retained_loss=0.05, punished=False)
    assert AllowedTacticDetector().detect(game, [unpun]) == []

    # a one-move free capture is a hung piece, NOT an allowed tactic (no overlap)
    ph = Ply(5, 3, Color.WHITE, "Ne5", "c4e5",
             "4k3/8/3p4/8/2N5/8/8/4K3 w - - 0 1", HUNG_KNIGHT)
    gh = Game(game_id="g2", url="", played_at=None, time_class="rapid",
              time_control="600", rated=True, rules="chess", eco=None,
              white=Player("me", 1500), black=Player("them", 1500),
              perspective=Color.WHITE, moves=[ph])
    jh = MoveJudgment(5, Color.WHITE, "Ne5", "c4e5", MoveClass.BLUNDER,
                      0.60, 0.20, 0.40, "a1a2", False,
                      win_prob_after_reply=0.20, retained_loss=0.40, punished=True)
    assert AllowedTacticDetector().detect(gh, [jh]) == []
    print("  allowed_tactic: fork detected; not-punished & hung-piece both skip OK")


def test_allowed_attack_mate():
    # White (me) plays an idle knight move, allowing a back-rank mate: ...Re1#.
    # No material changes hands.
    p5 = Ply(5, 20, Color.WHITE, "Nc3", "b1c3",
             "4r1k1/8/8/8/8/8/5PPP/1N4K1 w - - 0 1",
             "4r1k1/8/8/8/8/2N5/5PPP/6K1 b - - 1 1")
    p6 = Ply(6, 20, Color.BLACK, "Re1#", "e8e1",
             p5.fen_after, "6k1/8/8/8/8/2N5/5PPP/4r1K1 w - - 2 2")
    game = Game(
        game_id="g", url="", played_at=None, time_class="blitz",
        time_control="300", rated=True, rules="chess", eco=None,
        white=Player("me", 1500), black=Player("them", 1500),
        perspective=Color.WHITE, moves=[p5, p6])
    j = MoveJudgment(5, Color.WHITE, "Nc3", "b1c3", MoveClass.BLUNDER,
                     0.70, 0.0, 0.70, "g1f1", False,
                     win_prob_after_reply=0.0, retained_loss=0.70, punished=True)
    tags = AllowedAttackDetector().detect(game, [j])
    assert len(tags) == 1 and tags[0].name == "allowed_attack", tags
    assert tags[0].detail == "allowed a mating attack", tags[0].detail

    # a MATERIAL loss (fork) must NOT be labeled an attack — tactic owns it
    p5b = Ply(5, 3, Color.WHITE, "Re1", "a1e1",
              "6k1/8/8/6n1/8/8/8/R5K1 w - - 0 1", "6k1/8/8/6n1/8/8/8/4R1K1 b - - 1 1")
    p6b = Ply(6, 3, Color.BLACK, "Nf3+", "g5f3", p5b.fen_after,
              "6k1/8/8/8/8/5n2/8/4R1K1 w - - 2 2")
    p7b = Ply(7, 4, Color.WHITE, "Kf1", "g1f1", p6b.fen_after,
              "6k1/8/8/8/8/5n2/8/4RK2 b - - 3 2")
    p8b = Ply(8, 4, Color.BLACK, "Nxe1", "f3e1", p7b.fen_after,
              "6k1/8/8/8/8/8/8/4nK2 w - - 0 3")
    gb = Game(game_id="g2", url="", played_at=None, time_class="rapid",
              time_control="600", rated=True, rules="chess", eco=None,
              white=Player("me", 1500), black=Player("them", 1500),
              perspective=Color.WHITE, moves=[p5b, p6b, p7b, p8b])
    jb = MoveJudgment(5, Color.WHITE, "Re1", "a1e1", MoveClass.BLUNDER,
                      0.60, 0.20, 0.40, "a1a2", False,
                      win_prob_after_reply=0.20, retained_loss=0.40, punished=True)
    assert AllowedAttackDetector().detect(gb, [jb]) == []

    # non-material collapse but NO checks against me (squandered compensation /
    # positional drift) -> must NOT be called an attack
    q5 = Ply(5, 20, Color.WHITE, "Kf1", "g1f1",
             "6k1/5ppp/8/8/8/8/5PPP/6K1 w - - 0 1", "6k1/5ppp/8/8/8/8/5PPP/5K2 b - - 1 1")
    q6 = Ply(6, 20, Color.BLACK, "Kf8", "g8f8", q5.fen_after,
             "5k2/5ppp/8/8/8/8/5PPP/5K2 w - - 2 2")
    q7 = Ply(7, 21, Color.WHITE, "Ke1", "f1e1", q6.fen_after,
             "5k2/5ppp/8/8/8/8/5PPP/4K3 b - - 3 2")
    gq = Game(game_id="g3", url="", played_at=None, time_class="rapid",
              time_control="600", rated=True, rules="chess", eco=None,
              white=Player("me", 1500), black=Player("them", 1500),
              perspective=Color.WHITE, moves=[q5, q6, q7])
    jq = MoveJudgment(5, Color.WHITE, "Kf1", "g1f1", MoveClass.BLUNDER,
                      0.65, 0.20, 0.45, "g1h1", False,
                      win_prob_after_reply=0.20, retained_loss=0.45, punished=True)
    assert AllowedAttackDetector().detect(gq, [jq]) == []
    print("  allowed_attack: mate flagged; material tactic & no-king-pressure excluded OK")


if __name__ == "__main__":
    print("Running tag tests...")
    test_see_free_piece()
    test_see_equal_trade()
    test_best_free_capture()
    test_hung_piece_detected()
    test_no_tag_when_swing_too_small()
    test_no_tag_when_no_free_capture()
    test_punished_flag()
    test_no_tag_on_even_trade()
    test_allowed_tactic()
    test_allowed_attack_mate()
    print("ALL PASSED")
