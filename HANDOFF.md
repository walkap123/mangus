# chess-coach — project handoff

## What we're building

A chess.com coaching engine. A user types their chess.com username; the app
pulls all their public games, runs each one through Stockfish, classifies every
move (blunder / mistake / inaccuracy / good / best), and then adds a layer of
**semantic tags** — "piece hung," "missed tactic," "pawn endgame," "lost on
time in a winning position," etc.

The move classifier and Stockfish analysis are the commodity parts (open source,
done by many projects before). The **tag layer is the point of the product**: by
attaching human-meaningful labels to positions, a coach layer can then reason
*across all of a player's games* — "you convert winning middlegames but lose 60%
of your pawn endgames" — instead of just annotating one game at a time. That
cross-game, holistic feedback is what makes it a coach rather than an analyzer.

## Architecture

```
ingest  ->  eval (Stockfish)  ->  classify moves  ->  tag  ->  coach
 [DONE]        [DONE]              [next]            [the moat]   [later]
```

Under all of it: **`store.py`** (SQLite) persists ingested games and caches
evals by `(fen, depth)`, so no game is re-fetched and no position is analyzed
twice — across every game and every future run.

Every stage reads from a clean internal model and knows nothing about the stage
before it. Data source (chess.com today, maybe Lichess later), engine, and
classifier are all swappable without rewriting downstream code.

## What's built (ingestion layer)

`chess_coach/` is a Python package:

- **`models.py`** — engine- and source-agnostic data model. `Game` and `Ply`.
  Every `Ply` carries `fen_before`, `fen_after`, SAN, UCI, and clock — i.e.
  exactly what the eval layer needs. `Game` is **perspective-aware**: because we
  ingest per-username, each game knows which color is "you" (`game.me`,
  `game.result`, `game.my_plies()`), so coaching never mixes up sides.
- **`ingest.py`** — `ChessComClient`. Pulls monthly archives from the public
  chess.com Published-Data API and parses PGNs into `Game`s. Handles the required
  descriptive User-Agent (403 without it), 429/Retry-After backoff, and
  404 -> `PlayerNotFound`. Filters to standard chess by default (drops
  chess960/variants). Supports filtering by time class, rated-only, and a
  max-games cap.
- **`cli.py`** — `python -m chess_coach.cli USERNAME` smoke test.
- **`test_ingest.py`** — fully offline tests: real PGN parsing + a fake HTTP
  layer that drives the client end-to-end (archives, filters, pagination,
  ordering) against the real API's data shape. All passing.

## Key design decision on the classifier (context for later)

Do NOT copy Lichess's move-classification code — it's AGPL, which would force the
whole project to become AGPL/source-available. The *algorithm* (convert the
engine eval to a win probability, then classify a move by how much win-% it lost)
is not copyrightable. Plan: reimplement that documented win-% formula ourselves
(~30 lines), behind a clean interface, so it's swappable and license-clean.

## Next steps (in order)

1. **Stockfish eval wrapper** — UCI process wrapper that takes a FEN and returns
   an evaluation (centipawns / mate). Cache by FEN (positions repeat across
   games). Feed it `ply.fen_before`.
2. **Move classifier** — own win-% implementation; turns eval deltas into
   blunder/mistake/inaccuracy/good/best.
3. **Semantic tag layer** — the differentiator. Rule-based detectors over board
   state + eval swings (hung piece, missed tactic, endgame type, time trouble).
4. **Cross-game aggregation + coach output** — roll tags up across all games into
   themed weaknesses and concrete advice.

## Run it

```bash
pip install -r requirements.txt          # python-chess, requests
python test_ingest.py                     # offline tests
python -m chess_coach.cli YOUR_USERNAME --max 20 --ua "chesscoach (you@email.com)"
```
