# mangus

A personal chess.com coaching engine. Give it your chess.com username; it pulls
your public games, runs each through Stockfish, classifies every move
(blunder / mistake / inaccuracy / good / best), and — the point of the whole
thing — attaches **semantic tags** to positions ("hung a piece", "missed
tactic", "lost a won pawn endgame", "flagged in a winning position") so it can
reason *across all your games*:

> "You convert winning middlegames but lose 60% of your pawn endgames."

That cross-game, holistic view is what makes it a coach rather than a
single-game analyzer.

## Pipeline

```
ingest  ->  eval (Stockfish)  ->  classify moves  ->  tag  ->  coach
```

Every stage reads a clean, engine-agnostic data model and knows nothing about
the stage before it, so the data source, engine, and classifier are all
swappable. A local SQLite **store** underneath persists games and caches evals
by FEN so nothing is fetched or analyzed twice.

**Built:** ingest, store, eval. **Next:** move classifier (own win% impl),
then the semantic tag layer.

## Setup

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

The eval layer needs a Stockfish binary. Install it and either put it on `PATH`
or point `MANGUS_STOCKFISH` at it:

```bash
brew install stockfish          # macOS
```

## Run

```bash
# offline tests
cd tests && PYTHONPATH="..:." python test_ingest.py && \
            PYTHONPATH="..:." python test_store.py && \
            PYTHONPATH="..:." python test_eval.py     # skips if no Stockfish

# ingest smoke test (needs network)
python -m chess_coach.cli YOUR_USERNAME --max 20 --ua "mangus (you@email.com)"
```

## Layout

```
chess_coach/
  models.py   clean data model: Game, Ply, Evaluation (all engine-agnostic)
  ingest.py   chess.com Published-Data API client + PGN parsing
  store.py    SQLite: games/plies persistence + (fen,depth) eval cache
  eval.py     Stockfish UCI wrapper, cache-first, fixed depth
  cli.py      ingestion smoke test
tests/        fully offline except test_eval (self-skips without Stockfish)
```
