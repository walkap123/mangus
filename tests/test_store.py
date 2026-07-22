"""Offline tests for the SQLite store: game round-trip + eval cache."""

import os
import tempfile

from chess_coach.models import Color, Evaluation, GameResult
from chess_coach.ingest import parse_game
from chess_coach.store import Store

# reuse the same fixture the ingest tests use
from test_ingest import RAW_GAME


def _tmp_store() -> tuple[Store, str]:
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    return Store(path), path


def test_game_roundtrip():
    store, path = _tmp_store()
    try:
        g = parse_game(RAW_GAME, perspective_username="alice")
        assert not store.has_game(g.game_id)
        store.save_game(g)
        assert store.has_game(g.game_id)

        back = store.get_game(g.game_id)
        assert back is not None
        assert back.perspective is Color.WHITE
        assert back.result is GameResult.WIN
        assert back.me.username == "alice" and back.opponent.username == "bob"
        assert back.my_rating == 1500 and back.opponent_rating == 1480
        assert len(back.moves) == len(g.moves) == 7
        # ply fidelity
        assert back.moves[0].san == "e4" and back.moves[0].uci == "e2e4"
        assert back.moves[-1].san == "Qxf7#"
        assert back.moves[0].clock_seconds == 598.0
        assert back.moves[0].fen_before == g.moves[0].fen_before

        # idempotent re-save doesn't duplicate plies
        store.save_game(g)
        assert len(store.get_game(g.game_id).moves) == 7

        # iter
        assert [x.game_id for x in store.iter_stored_games()] == [g.game_id]
        print("  store.save/get_game: round-trip + idempotent OK")
    finally:
        store.close()
        os.remove(path)


def test_eval_cache():
    store, path = _tmp_store()
    try:
        fen = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
        assert store.get_eval(fen, 18) is None
        ev = Evaluation(fen=fen, depth=18, cp=31, best_move="e2e4")
        store.put_eval(ev)

        hit = store.get_eval(fen, 18)
        assert hit == ev
        # depth is part of the key
        assert store.get_eval(fen, 20) is None
        assert store.eval_cache_size() == 1

        # mate eval round-trips
        mate_fen = "6k1/5ppp/8/8/8/8/5PPP/4R1K1 w - - 0 1"
        store.put_eval(Evaluation(fen=mate_fen, depth=18, mate=3, best_move="e1e8"))
        got = store.get_eval(mate_fen, 18)
        assert got.mate == 3 and got.cp is None
        print("  store eval cache: (fen,depth) key, cp/mate round-trip OK")
    finally:
        store.close()
        os.remove(path)


def test_pov_negation():
    # white-to-move eval, +50 for white
    w = Evaluation(fen="8/8/8/8/8/8/8/K6k w - - 0 1", depth=18, cp=50)
    assert w.pov(Color.WHITE).cp == 50
    assert w.pov(Color.BLACK).cp == -50
    # black-to-move eval, +50 means black is better
    b = Evaluation(fen="8/8/8/8/8/8/8/K6k b - - 0 1", depth=18, cp=50)
    assert b.pov(Color.BLACK).cp == 50
    assert b.pov(Color.WHITE).cp == -50
    print("  Evaluation.pov: side-to-move negation OK")


if __name__ == "__main__":
    print("Running store tests...")
    test_game_roundtrip()
    test_eval_cache()
    test_pov_negation()
    print("ALL PASSED")
