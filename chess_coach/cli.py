"""Tiny CLI for the ingestion layer.

    python -m chess_coach.cli USERNAME [--max 20] [--time-class blitz,rapid]
                              [--rated] [--ua "myapp (contact@you.com)"]

Prints a one-line summary per game. This is the smoke test for real API access
(run it on a machine with network access to api.chess.com).
"""

from __future__ import annotations

import argparse
import sys

from .ingest import ChessComClient, DEFAULT_UA, PlayerNotFound, ChessComError


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Ingest chess.com games for a user.")
    p.add_argument("username")
    p.add_argument("--max", type=int, default=20, help="max games to fetch")
    p.add_argument("--time-class", default=None,
                   help="comma list: bullet,blitz,rapid,daily")
    p.add_argument("--rated", action="store_true", help="rated games only")
    p.add_argument("--ua", default=DEFAULT_UA, help="User-Agent (put real contact info)")
    args = p.parse_args(argv)

    time_classes = set(args.time_class.split(",")) if args.time_class else None
    client = ChessComClient(user_agent=args.ua)

    try:
        games = client.iter_games(
            args.username,
            time_classes=time_classes,
            rated_only=args.rated,
            max_games=args.max,
        )
        n = 0
        for g in games:
            opp = g.opponent
            print(f"{g.played_at.date() if g.played_at else '?':>10}  "
                  f"{g.time_class:<6} {g.result.value:<4} "
                  f"me({g.my_rating}) vs {opp.username}({opp.rating})  "
                  f"{len(g.my_plies())} of my moves  {g.url}")
            n += 1
        print(f"\n{n} games ingested for {args.username}.", file=sys.stderr)
    except PlayerNotFound:
        print(f"No such chess.com user: {args.username}", file=sys.stderr)
        return 1
    except ChessComError as e:
        print(f"chess.com API error: {e}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
