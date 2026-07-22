"""End-to-end runner + cross-game coach output.

Ties the pipeline together for one username:

    ingest -> store -> eval (cache-first) -> classify (your moves) -> tag
           -> aggregate across games -> findings

and emits a structured **report** (JSON = the data contract a future UI renders;
HTML = a quick view for eyeballing while we tune). The whole point of the coach
layer is that it reasons *across* games — turning per-move tags and eval swings
into recurring, human-meaningful weaknesses.

Everything here is perspective-aware: we only judge and tag the moves *you*
played (`game.perspective`), so findings are about you, never your opponents.
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

from .classify import MoveClass, MoveClassifier, MoveJudgment, summarize
from .eval import StockfishEval
from .ingest import ChessComClient, DEFAULT_UA
from .models import Game, GameResult
from .store import Store
from .tag import Detector, HungPieceDetector, Tag, tag_game


def _phase(move_number: int) -> str:
    """Rough game phase from full-move number (cheap heuristic, not exact)."""
    if move_number <= 12:
        return "opening"
    if move_number <= 30:
        return "middlegame"
    return "endgame"


@dataclass
class GameAnalysis:
    """One game, reduced to what the coach aggregates over (your side only)."""
    game: Game
    judgments: list[MoveJudgment]      # your moves
    tags: list[Tag]                    # your tags

    @property
    def class_counts(self) -> dict[MoveClass, int]:
        return summarize(self.judgments)


def analyze_game(
    game: Game,
    evaluator: StockfishEval,
    classifier: MoveClassifier,
    detectors: list[Detector],
) -> GameAnalysis:
    judgments = classifier.classify_game(game, evaluator, mine_only=True)
    tags = tag_game(game, judgments, detectors)
    return GameAnalysis(game=game, judgments=judgments, tags=tags)


@dataclass
class Finding:
    key: str
    headline: str
    detail: str = ""
    examples: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {"key": self.key, "headline": self.headline,
                "detail": self.detail, "examples": self.examples}


@dataclass
class CoachReport:
    username: str
    params: dict
    analyses: list[GameAnalysis]
    generated_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(timespec="seconds"))

    # ---- rolled-up numbers ----
    def _record(self) -> tuple[int, int, int]:
        w = l = d = 0
        for a in self.analyses:
            r = a.game.result
            w += r is GameResult.WIN
            l += r is GameResult.LOSS
            d += r is GameResult.DRAW
        return w, l, d

    def _totals(self) -> dict[MoveClass, int]:
        totals = {mc: 0 for mc in MoveClass}
        for a in self.analyses:
            for mc, n in a.class_counts.items():
                totals[mc] += n
        return totals

    # ---- findings: the actual coaching ----
    def findings(self) -> list[Finding]:
        out: list[Finding] = []
        n_games = len(self.analyses)
        if n_games == 0:
            return out

        # 1) Hung pieces (across games). We separate the *habit* (you left it
        #    hangable) from what it *cost* (did the opponent actually take it).
        #    An unpunished hang is still worth fixing but is NOT why you lost.
        hung = [(a, t) for a in self.analyses for t in a.tags
                if t.name == "hung_piece"]
        if hung:
            hung_games = {id(a) for a, _ in hung}
            n_punished = sum(1 for _, t in hung if t.punished)
            n_missed = len(hung) - n_punished
            examples = []
            for a, t in hung[:6]:
                examples.append({
                    "url": a.game.url, "move": t.san, "detail": t.detail,
                    "ply": t.ply_number, "result": a.game.result.value,
                    "punished": bool(t.punished),
                })
            bits = []
            if n_punished:
                bits.append(f"{n_punished} the opponent took")
            if n_missed:
                bits.append(f"{n_missed} they missed")
            out.append(Finding(
                key="hung_pieces",
                headline=f"You left a piece hanging {len(hung)} times "
                         f"across {len(hung_games)} of {n_games} games.",
                detail=f"Punishment: {', '.join(bits)}. An unpunished hang isn't "
                       f"why you lost — but it's a habit to fix before someone "
                       f"does take it.",
                examples=examples,
            ))

        # 2) Where your blunders happen (game phase)
        phase_counts = {"opening": 0, "middlegame": 0, "endgame": 0}
        total_blunders = 0
        for a in self.analyses:
            for j in a.judgments:
                if j.move_class is MoveClass.BLUNDER:
                    # find the ply to get its move number
                    ply = next(p for p in a.game.moves if p.ply_number == j.ply_number)
                    phase_counts[_phase(ply.move_number)] += 1
                    total_blunders += 1
        if total_blunders >= 3:
            worst = max(phase_counts, key=phase_counts.get)
            share = round(100 * phase_counts[worst] / total_blunders)
            out.append(Finding(
                key="blunder_timing",
                headline=f"{share}% of your blunders happen in the {worst}.",
                detail=f"Blunders by phase — opening {phase_counts['opening']}, "
                       f"middlegame {phase_counts['middlegame']}, "
                       f"endgame {phase_counts['endgame']}.",
            ))

        # 3) Blunder rate in losses vs. wins
        def blunders(a: GameAnalysis) -> int:
            return sum(j.move_class is MoveClass.BLUNDER for j in a.judgments)
        losses = [a for a in self.analyses if a.game.result is GameResult.LOSS]
        wins = [a for a in self.analyses if a.game.result is GameResult.WIN]
        if losses and wins:
            bl = sum(blunders(a) for a in losses) / len(losses)
            bw = sum(blunders(a) for a in wins) / len(wins)
            if bl >= bw + 0.5:
                out.append(Finding(
                    key="blunders_decide_games",
                    headline=f"Your losses average {bl:.1f} blunders vs. {bw:.1f} in your wins.",
                    detail="Blunders, not slow positional losses, are deciding most of "
                           "your games — cutting them is the fastest rating gain.",
                ))
        return out

    # ---- serialization (the UI contract) ----
    def to_dict(self) -> dict:
        w, l, d = self._record()
        totals = self._totals()
        my_moves = sum(totals.values())
        best_pct = round(100 * totals[MoveClass.BEST] / my_moves, 1) if my_moves else 0.0
        return {
            "username": self.username,
            "generated_at": self.generated_at,
            "params": self.params,
            "summary": {
                "games": len(self.analyses),
                "wins": w, "losses": l, "draws": d,
                "my_moves": my_moves,
                "move_classes": {mc.value: totals[mc] for mc in MoveClass},
                "blunders_per_game": round(totals[MoveClass.BLUNDER] / len(self.analyses), 2)
                                     if self.analyses else 0.0,
                "best_pct": best_pct,
            },
            "findings": [f.to_dict() for f in self.findings()],
            "games": [
                {
                    "url": a.game.url,
                    "time_class": a.game.time_class,
                    "result": a.game.result.value,
                    "opponent": a.game.opponent.username,
                    "my_rating": a.game.my_rating,
                    "opponent_rating": a.game.opponent_rating,
                    "move_classes": {mc.value: a.class_counts[mc] for mc in MoveClass},
                    "tags": [
                        {"name": t.name, "san": t.san, "detail": t.detail,
                         "ply": t.ply_number}
                        for t in a.tags
                    ],
                }
                for a in self.analyses
            ],
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)


# ---------------- the runner ----------------
def run(
    username: str,
    *,
    store: Store,
    evaluator: StockfishEval,
    classifier: Optional[MoveClassifier] = None,
    detectors: Optional[list[Detector]] = None,
    max_games: int = 10,
    time_classes: Optional[set[str]] = None,
    rated_only: bool = False,
    ua: str = DEFAULT_UA,
    progress=sys.stderr,
) -> CoachReport:
    """Fetch, analyze, and aggregate a user's recent games into a CoachReport."""
    classifier = classifier or MoveClassifier()
    detectors = detectors or [HungPieceDetector()]
    client = ChessComClient(user_agent=ua)

    analyses: list[GameAnalysis] = []
    games = client.iter_games(
        username, time_classes=time_classes, rated_only=rated_only,
        max_games=max_games,
    )
    for i, game in enumerate(games, 1):
        store.save_game(game)
        if progress:
            print(f"  [{i}/{max_games}] {game.time_class:<6} vs "
                  f"{game.opponent.username} ({game.result.value}) — "
                  f"{len(game.my_plies())} of your moves...",
                  file=progress, flush=True)
        analyses.append(analyze_game(game, evaluator, classifier, detectors))

    return CoachReport(
        username=username,
        params={"max_games": max_games, "depth": evaluator.depth,
                "time_classes": sorted(time_classes) if time_classes else None,
                "rated_only": rated_only},
        analyses=analyses,
    )


# ---------------- HTML view (for eyeballing during tuning) ----------------
def render_html(report: CoachReport) -> str:
    import html
    d = report.to_dict()
    s = d["summary"]

    def esc(x) -> str:
        return html.escape(str(x))

    findings_html = ""
    for f in d["findings"]:
        ex = ""
        if f["examples"]:
            items = "".join(
                f'<li><a href="{esc(e["url"])}" target="_blank">{esc(e["detail"])}</a> '
                f'<span class="muted">({esc(e["result"])})</span></li>'
                for e in f["examples"]
            )
            ex = f"<ul>{items}</ul>"
        findings_html += (
            f'<div class="finding"><div class="headline">{esc(f["headline"])}</div>'
            f'<div class="muted">{esc(f["detail"])}</div>{ex}</div>'
        )
    if not d["findings"]:
        findings_html = '<p class="muted">No recurring weaknesses detected yet ' \
                        '(more detectors coming).</p>'

    rows = ""
    for g in d["games"]:
        mc = g["move_classes"]
        tags = ", ".join(t["detail"] for t in g["tags"]) or "—"
        rows += (
            f'<tr><td><a href="{esc(g["url"])}" target="_blank">{esc(g["time_class"])}</a></td>'
            f'<td>{esc(g["result"])}</td><td>{esc(g["opponent"])}</td>'
            f'<td>{esc(g["opponent_rating"])}</td>'
            f'<td class="bl">{mc["blunder"]}</td><td>{mc["mistake"]}</td>'
            f'<td>{mc["inaccuracy"]}</td><td>{esc(tags)}</td></tr>'
        )

    return f"""<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>mangus — {esc(d['username'])}</title>
<style>
  :root {{ color-scheme: light dark; }}
  body {{ font: 15px/1.5 -apple-system, system-ui, sans-serif; max-width: 820px;
         margin: 2rem auto; padding: 0 1rem; }}
  h1 {{ margin-bottom: .2rem; }}
  .muted {{ opacity: .65; font-size: .9em; }}
  .stats {{ display: flex; flex-wrap: wrap; gap: 1rem; margin: 1rem 0; }}
  .stat {{ background: color-mix(in srgb, currentColor 8%, transparent);
          border-radius: 10px; padding: .6rem 1rem; }}
  .stat b {{ font-size: 1.5rem; display: block; }}
  .finding {{ border-left: 3px solid #e0803a; padding: .4rem .9rem; margin: .8rem 0; }}
  .headline {{ font-weight: 600; }}
  table {{ border-collapse: collapse; width: 100%; margin-top: .5rem; font-size: .9em; }}
  th, td {{ text-align: left; padding: .35rem .5rem; border-bottom: 1px solid
           color-mix(in srgb, currentColor 15%, transparent); }}
  td.bl {{ font-weight: 700; }}
  a {{ color: #e0803a; }}
</style></head><body>
<h1>mangus</h1>
<div class="muted">{esc(d['username'])} · {esc(d['generated_at'])} ·
  depth {esc(d['params']['depth'])}</div>
<div class="stats">
  <div class="stat"><b>{s['games']}</b>games</div>
  <div class="stat"><b>{s['wins']}–{s['losses']}–{s['draws']}</b>W–L–D</div>
  <div class="stat"><b>{s['blunders_per_game']}</b>blunders / game</div>
  <div class="stat"><b>{s['best_pct']}%</b>best moves</div>
  <div class="stat"><b>{s['move_classes']['blunder']}</b>blunders</div>
</div>
<h2>What to work on</h2>
{findings_html}
<h2>Games</h2>
<table><thead><tr><th>type</th><th>result</th><th>opponent</th><th>rating</th>
<th>blun</th><th>mist</th><th>inacc</th><th>tags</th></tr></thead>
<tbody>{rows}</tbody></table>
</body></html>"""


# ---------------- CLI ----------------
def main(argv: Optional[list[str]] = None) -> int:
    import argparse
    from pathlib import Path

    p = argparse.ArgumentParser(description="Analyze a chess.com user's recent games.")
    p.add_argument("username")
    p.add_argument("--max", type=int, default=10, help="max games to analyze")
    p.add_argument("--depth", type=int, default=12, help="Stockfish search depth")
    p.add_argument("--time-class", default=None, help="comma list: bullet,blitz,rapid,daily")
    p.add_argument("--rated", action="store_true")
    p.add_argument("--db", default="mangus.db", help="SQLite store path")
    p.add_argument("--out", default="report", help="output basename (writes .json + .html)")
    p.add_argument("--ua", default=DEFAULT_UA, help="chess.com User-Agent (real contact info)")
    args = p.parse_args(argv)

    time_classes = set(args.time_class.split(",")) if args.time_class else None
    store = Store(args.db)
    try:
        with StockfishEval(depth=args.depth, store=store) as sf:
            print(f"Analyzing {args.username} "
                  f"(max {args.max} games, depth {args.depth})...", file=sys.stderr)
            report = run(
                args.username, store=store, evaluator=sf,
                max_games=args.max, time_classes=time_classes,
                rated_only=args.rated, ua=args.ua,
            )
    finally:
        store.close()

    Path(f"{args.out}.json").write_text(report.to_json())
    Path(f"{args.out}.html").write_text(render_html(report))
    print(f"\nWrote {args.out}.json and {args.out}.html "
          f"({len(report.analyses)} games).", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
