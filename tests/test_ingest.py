"""Offline tests for the ingestion layer.

Verifies:
  1. PGN -> Ply parsing (SAN, UCI, FENs, clocks, move numbers).
  2. Perspective + result normalization from a chess.com game dict.
  3. Client filtering/pagination logic, using a FAKE http layer (no network),
     so we exercise iter_games end-to-end exactly as the live API would drive it.

Run:  python test_ingest.py
"""

import json
from chess_coach.models import Color, GameResult
from chess_coach import ingest
from chess_coach.ingest import ChessComClient, parse_game, parse_moves

# A real, short decisive game (Scholar's-mate style) WITH clock annotations,
# matching how chess.com formats pgn movetext.
PGN = (
    '[Event "Live Chess"]\n'
    '[Site "Chess.com"]\n'
    '[Date "2024.03.11"]\n'
    '[White "alice"]\n'
    '[Black "bob"]\n'
    '[Result "1-0"]\n'
    '[TimeControl "600"]\n'
    '[Termination "alice won by checkmate"]\n\n'
    '1. e4 {[%clk 0:09:58]} 1... e5 {[%clk 0:09:57]} '
    '2. Qh5 {[%clk 0:09:55]} 2... Nc6 {[%clk 0:09:50]} '
    '3. Bc4 {[%clk 0:09:53]} 3... Nf6 {[%clk 0:09:40]} '
    '4. Qxf7# {[%clk 0:09:51]} 1-0\n'
)

RAW_GAME = {
    "url": "https://www.chess.com/game/live/123",
    "uuid": "abc-123",
    "pgn": PGN,
    "time_control": "600",
    "time_class": "rapid",
    "rated": True,
    "rules": "chess",
    "end_time": 1710000000,
    "eco": "C20",
    "white": {"username": "Alice", "rating": 1500, "result": "win"},
    "black": {"username": "Bob", "rating": 1480, "result": "checkmated"},
}


def test_parse_moves():
    plies = parse_moves(PGN)
    assert len(plies) == 7, len(plies)
    first, last = plies[0], plies[-1]

    assert first.san == "e4" and first.uci == "e2e4"
    assert first.color is Color.WHITE and first.move_number == 1
    assert first.fen_before.startswith(
        "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w"), first.fen_before
    assert first.clock_seconds == 598.0, first.clock_seconds  # 9:58

    assert last.san == "Qxf7#" and last.uci == "h5f7"
    assert last.color is Color.WHITE
    # position after final move: black to move, in checkmate
    import chess
    b = chess.Board(last.fen_after)
    assert b.is_checkmate()
    print("  parse_moves: 7 plies, SAN/UCI/FEN/clock OK, mate detected")


def test_parse_game_perspective_and_result():
    # From white's perspective -> win
    g_white = parse_game(RAW_GAME, perspective_username="alice")
    assert g_white.perspective is Color.WHITE
    assert g_white.result is GameResult.WIN
    assert g_white.me.username == "alice" and g_white.opponent.username == "bob"
    assert g_white.my_rating == 1500 and g_white.opponent_rating == 1480
    assert len(g_white.my_plies()) == 4  # white made 4 of the 7 half-moves

    # Same game from black's perspective -> loss
    g_black = parse_game(RAW_GAME, perspective_username="bob")
    assert g_black.perspective is Color.BLACK
    assert g_black.result is GameResult.LOSS
    assert len(g_black.my_plies()) == 3
    print("  parse_game: perspective, result, ratings, my_plies OK")


class FakeResp:
    def __init__(self, payload, status=200):
        self._payload = payload
        self.status_code = status
        self.headers = {}
        self.text = json.dumps(payload)

    def json(self):
        return self._payload


def test_client_iter_and_filters(monkeypatch=None):
    """Drive iter_games through a fake HTTP layer with 2 archives + variety."""
    archives = {
        "https://api.chess.com/pub/player/tester/games/archives":
            {"archives": [
                "https://api.chess.com/pub/player/tester/games/2024/01",
                "https://api.chess.com/pub/player/tester/games/2024/02",
            ]},
        "https://api.chess.com/pub/player/tester/games/2024/01":
            {"games": [
                _mk("bullet", rated=True, rules="chess"),
                _mk("blitz", rated=False, rules="chess"),
            ]},
        "https://api.chess.com/pub/player/tester/games/2024/02":
            {"games": [
                _mk("rapid", rated=True, rules="chess"),
                _mk("blitz", rated=True, rules="chess960"),  # variant, filtered out
            ]},
    }

    client = ChessComClient(user_agent="test")
    client._get = lambda url: FakeResp(archives[url])  # bypass network

    # Default: standard chess only, newest archive first.
    all_std = client.fetch_games("tester")
    classes = [g.time_class for g in all_std]
    assert "chess960" not in [g.rules for g in all_std]
    assert len(all_std) == 3, classes
    # newest_first -> 2024/02 games come before 2024/01
    assert classes[0] == "rapid", classes

    # rated only
    rated = client.fetch_games("tester", rated_only=True)
    assert {g.time_class for g in rated} == {"rapid", "bullet"}, rated

    # time_class filter
    blitz = client.fetch_games("tester", time_classes={"blitz"})
    assert len(blitz) == 1 and blitz[0].time_class == "blitz"

    # max_games cap
    capped = client.fetch_games("tester", max_games=2)
    assert len(capped) == 2
    print("  client.iter_games: archives, filters (rules/rated/class), cap, order OK")


def _mk(time_class, rated, rules):
    g = dict(RAW_GAME)
    g["time_class"] = time_class
    g["rated"] = rated
    g["rules"] = rules
    return g


if __name__ == "__main__":
    print("Running ingestion tests...")
    test_parse_moves()
    test_parse_game_perspective_and_result()
    test_client_iter_and_filters()
    print("ALL PASSED")
