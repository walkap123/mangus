"""Live Stockfish test. Skips cleanly if no engine is installed, so the rest
of the suite stays fully offline.

Run:  python tests/test_eval.py
"""

from chess_coach.eval import StockfishEval, EngineNotFound, find_stockfish
from chess_coach.store import Store
from chess_coach.ingest import parse_game
from test_ingest import RAW_GAME

START_FEN = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
# White has a free rook to grab; engine should find a big advantage.
FREE_ROOK = "4k3/8/8/8/8/8/8/r3K2R w K - 0 1"


def test_eval_and_cache():
    try:
        path = find_stockfish()
    except EngineNotFound as e:
        print(f"  SKIP test_eval: {e}")
        return

    print(f"  using stockfish at {path}")
    import tempfile, os
    fd, dbpath = tempfile.mkstemp(suffix=".db"); os.close(fd)
    store = Store(dbpath)
    try:
        with StockfishEval(depth=12, store=store) as sf:
            ev = sf.evaluate(START_FEN)
            assert ev.depth == 12
            # start position is roughly balanced, small white edge
            assert ev.cp is not None and -50 <= ev.cp <= 120, ev.cp
            assert ev.best_move is not None

            # second call is a cache hit -> no engine work, identical result
            assert store.eval_cache_size() == 1
            ev2 = sf.evaluate(START_FEN)
            assert ev2 == ev and store.eval_cache_size() == 1

            # warm a whole game; every position cached, reported misses match
            g = parse_game(RAW_GAME, perspective_username="alice")
            misses = sf.evaluate_game(g)
            assert misses >= 1
            # re-warming the same game makes zero new engine calls
            assert sf.evaluate_game(g) == 0
        print(f"  eval + FEN cache OK ({store.eval_cache_size()} positions cached)")
    finally:
        store.close(); os.remove(dbpath)


if __name__ == "__main__":
    print("Running eval tests...")
    test_eval_and_cache()
    print("DONE")
