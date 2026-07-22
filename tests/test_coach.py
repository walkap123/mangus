"""Offline test for the coach aggregation, using a fake evaluator (no engine,
no network)."""

import json

import chess

from chess_coach.models import Color, Evaluation, Game, Player, Ply
from chess_coach.classify import MoveClassifier
from chess_coach.tag import HungPieceDetector
from chess_coach.coach import analyze_game, CoachReport, render_html

# A short game where White (us) hangs a knight on e5 and loses.
START = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
AFTER_W1 = "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1"
BEFORE_HANG = "4k3/8/3p4/8/2N5/8/8/4K3 w - - 0 1"       # our move: Nc4-e5??
HUNG = "4k3/8/3p4/4N3/8/8/8/4K3 b - - 0 1"              # knight hangs to d6 pawn


class FakeEval:
    def __init__(self, table):
        self.table = table

    def evaluate(self, fen):
        # default: dead level, so only the crafted hang moves the needle
        return self.table.get(fen, Evaluation(fen, 12, cp=0, best_move=None))


def _game():
    plies = [
        Ply(1, 1, Color.WHITE, "e4", "e2e4", START, AFTER_W1),
        Ply(2, 1, Color.BLACK, "e5", "e7e5", AFTER_W1, BEFORE_HANG),  # dummy link
        Ply(3, 2, Color.WHITE, "Ne5", "c4e5", BEFORE_HANG, HUNG),      # the blunder
    ]
    return Game(
        game_id="g1", url="https://chess.com/game/1", played_at=None,
        time_class="blitz", time_control="300", rated=True, rules="chess",
        eco=None, white=Player("mastapate", 1400, "checkmated"),
        black=Player("opp", 1420, "win"), perspective=Color.WHITE, moves=plies,
    )


def test_coach_report():
    game = _game()
    ev = FakeEval({
        # before the hang we're fine (+20), after it black is winning a piece:
        BEFORE_HANG: Evaluation(BEFORE_HANG, 12, cp=20, best_move="c4d2"),
        HUNG: Evaluation(HUNG, 12, cp=320, best_move="d6e5"),  # black to move, +320
    })
    a = analyze_game(game, ev, MoveClassifier(), [HungPieceDetector()])
    # our Ne5 should be a blunder and carry a hung_piece tag
    assert any(t.name == "hung_piece" and t.victim_piece == "knight" for t in a.tags), a.tags

    report = CoachReport(username="mastapate", params={"depth": 12}, analyses=[a])
    d = report.to_dict()
    assert d["summary"]["games"] == 1
    assert d["summary"]["losses"] == 1
    assert d["summary"]["move_classes"]["blunder"] >= 1
    keys = [f["key"] for f in d["findings"]]
    assert "hung_pieces" in keys, keys

    # lens 2: this lost game should have an identified deciding move
    dec = d["decisive_losses"]
    assert len(dec) == 1 and dec[0]["decisive"] is True, dec
    assert dec[0]["kind"] == "hung_piece", dec
    assert dec[0]["win_before"] > dec[0]["win_after"], dec  # win chance dropped

    # JSON is serializable and HTML renders both lenses without error
    json.loads(report.to_json())
    html = render_html(report)
    assert "mastapate" in html and "hung a knight" in html
    assert "Why you actually lost" in html

    # board viewer: embeds valid per-move JSON with the moves and a tag
    from chess_coach.viewer import render_viewer
    v = render_viewer(report)
    marker = "const DATA = "
    payload = v.split(marker, 1)[1].split(";\n", 1)[0]
    embedded = json.loads(payload)
    assert embedded["username"] == "mastapate"
    plies = embedded["games"][0]["plies"]
    assert plies[0]["san"] == "e4" and "fen" in plies[0]
    assert any(p["tag"] and "hung a knight" in p["tag"] for p in plies)
    print("  coach: two-lens + board-viewer data / JSON / HTML OK")


if __name__ == "__main__":
    print("Running coach tests...")
    test_coach_report()
    print("ALL PASSED")
