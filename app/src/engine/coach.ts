// Cross-game aggregation + viewer payload — TS port of coach.py + viewer.py.
// Produces the exact object shape the app renders (mirrors viewer_data()).
import { Chess } from 'chess.js';
import { Game, gameResult, myRating, opponent } from './model';
import { Evaluator, MoveClass, MoveJudgment, classifyGame, winProb } from './classify';
import { Tag, tagGame } from './tag';
import { accuracy, eloEstimate } from './stats';

export interface GameAnalysis { game: Game; judgments: MoveJudgment[]; tags: Tag[]; }

export function analyzeGame(game: Game, evaluator: Evaluator): GameAnalysis {
  const judgments = classifyGame(game, evaluator, true);
  return { game, judgments, tags: tagGame(game, judgments) };
}

function phase(moveNumber: number): 'opening' | 'middlegame' | 'endgame' {
  if (moveNumber <= 12) return 'opening';
  if (moveNumber <= 30) return 'middlegame';
  return 'endgame';
}

function bestSan(fenBefore: string, uci: string | null): string | null {
  if (!uci) return null;
  try {
    const b = new Chess(fenBefore);
    const mv = b.move({ from: uci.slice(0, 2), to: uci.slice(2, 4), promotion: uci[4] as any });
    return mv.san;
  } catch {
    return uci;
  }
}

function whiteWinProb(fen: string, evaluator: Evaluator): number {
  const b = new Chess(fen);
  if (b.isGameOver()) {
    if (b.isCheckmate()) return b.turn() === 'w' ? 0.0 : 1.0;
    return 0.5;
  }
  const ev = evaluator(fen);
  const wp = winProb(ev.cp, ev.mate);
  return b.turn() === 'w' ? wp : 1.0 - wp;
}

interface Finding { key: string; headline: string; detail: string; examples: any[]; }

function findings(analyses: GameAnalysis[]): Finding[] {
  const out: Finding[] = [];
  const n = analyses.length;
  if (!n) return out;

  // 1) hung pieces
  const hung: [GameAnalysis, Tag][] = [];
  for (const a of analyses) for (const t of a.tags) if (t.name === 'hung_piece') hung.push([a, t]);
  if (hung.length) {
    const games = new Set(hung.map(([a]) => a));
    const nPun = hung.filter(([, t]) => t.punished).length;
    const nMiss = hung.length - nPun;
    const ex = hung.slice(0, 6).map(([a, t]) => ({
      url: a.game.url, move: t.san, detail: t.detail, ply: t.plyNumber,
      result: gameResult(a.game), punished: !!t.punished,
    }));
    const bits: string[] = [];
    if (nPun) bits.push(`${nPun} the opponent took`);
    if (nMiss) bits.push(`${nMiss} they missed`);
    out.push({
      key: 'hung_pieces',
      headline: `You left a piece hanging ${hung.length} times across ${games.size} of ${n} games.`,
      detail: `Punishment: ${bits.join(', ')}. An unpunished hang isn't why you lost — but it's a habit to fix before someone does take it.`,
      examples: ex,
    });
  }

  // 1b) allowed tactics
  const allowed: [GameAnalysis, Tag][] = [];
  for (const a of analyses) for (const t of a.tags) if (t.name === 'allowed_tactic') allowed.push([a, t]);
  if (allowed.length) {
    const games = new Set(allowed.map(([a]) => a));
    out.push({
      key: 'allowed_tactics',
      headline: `You allowed a material-winning tactic ${allowed.length} times across ${games.size} of ${n} games.`,
      detail: 'A move that let the opponent win material by force over the next few moves — and they took it every time here.',
      examples: allowed.slice(0, 6).map(([a, t]) => ({
        url: a.game.url, move: t.san, detail: t.detail, ply: t.plyNumber, result: gameResult(a.game), punished: true,
      })),
    });
  }

  // 1c) allowed attacks / mates
  const attacks: [GameAnalysis, Tag][] = [];
  for (const a of analyses) for (const t of a.tags) if (t.name === 'allowed_attack') attacks.push([a, t]);
  if (attacks.length) {
    const games = new Set(attacks.map(([a]) => a));
    const nMate = attacks.filter(([, t]) => t.detail.includes('mating')).length;
    out.push({
      key: 'allowed_attacks',
      headline: `You walked into a decisive attack ${attacks.length} times across ${games.size} of ${n} games`
        + (nMate ? ` (${nMate} were mating attacks).` : '.'),
      detail: 'Your position collapsed with no material lost — king safety / attack, not a hang. Different skill to fix.',
      examples: attacks.slice(0, 6).map(([a, t]) => ({
        url: a.game.url, move: t.san, detail: t.detail, ply: t.plyNumber, result: gameResult(a.game), punished: true,
      })),
    });
  }

  // 2) blunder timing
  const phaseCounts = { opening: 0, middlegame: 0, endgame: 0 };
  let totalBlunders = 0;
  for (const a of analyses) {
    for (const j of a.judgments) {
      if (j.moveClass === 'blunder') {
        const ply = a.game.moves.find((p) => p.plyNumber === j.plyNumber)!;
        phaseCounts[phase(ply.moveNumber)]++;
        totalBlunders++;
      }
    }
  }
  if (totalBlunders >= 3) {
    const worst = (Object.keys(phaseCounts) as (keyof typeof phaseCounts)[])
      .reduce((a, b) => (phaseCounts[a] >= phaseCounts[b] ? a : b));
    const share = Math.round((100 * phaseCounts[worst]) / totalBlunders);
    out.push({
      key: 'blunder_timing',
      headline: `${share}% of your blunders happen in the ${worst}.`,
      detail: `Blunders by phase — opening ${phaseCounts.opening}, middlegame ${phaseCounts.middlegame}, endgame ${phaseCounts.endgame}.`,
      examples: [],
    });
  }

  // 3) mistakes punished
  const serious = analyses.flatMap((a) => a.judgments.filter((j) => j.moveClass === 'mistake' || j.moveClass === 'blunder'));
  if (serious.length) {
    const punished = serious.filter((j) => j.punished).length;
    out.push({
      key: 'mistakes_punished',
      headline: `You made ${serious.length} serious mistakes; opponents punished ${punished} of them.`,
      detail: `The other ${serious.length - punished} you got away with — still worth fixing, but they didn't cost you those games.`,
      examples: [],
    });
  }
  return out;
}

function decisiveLosses(analyses: GameAnalysis[]): any[] {
  const out: any[] = [];
  for (const a of analyses) {
    if (gameResult(a.game) !== 'loss') continue;
    const byNum = new Map(a.game.moves.map((p) => [p.plyNumber, p]));
    const cands = a.judgments.filter((j) => j.punished && j.winProbLost >= 0.15);
    const entry: any = { url: a.game.url, opponent: opponent(a.game).username };
    if (cands.length) {
      const j = cands.reduce((x, y) => ((y.retainedLoss ?? 0) > (x.retainedLoss ?? 0) ? y : x));
      const ply = byNum.get(j.plyNumber)!;
      const tag = a.tags.find((t) => t.plyNumber === j.plyNumber);
      entry.decisive = true;
      entry.ply = j.plyNumber;
      entry.move_number = ply.moveNumber;
      entry.san = j.san;
      entry.kind = tag ? tag.name : j.moveClass;
      entry.detail = tag ? tag.detail : j.moveClass;
      entry.win_before = Math.round(100 * j.winProbBefore);
      entry.win_after = Math.round(100 * (j.winProbAfterReply ?? 0));
    } else {
      entry.decisive = false;
      entry.detail = 'no single punished blunder — ground down gradually';
    }
    out.push(entry);
  }
  return out;
}

function gameData(a: GameAnalysis, evaluator: Evaluator) {
  const game = a.game;
  const jmap = new Map(a.judgments.map((j) => [j.plyNumber, j]));
  const tmap = new Map<number, Tag>();
  for (const t of a.tags) if (!tmap.has(t.plyNumber)) tmap.set(t.plyNumber, t);

  const plies = game.moves.map((p) => {
    const j = jmap.get(p.plyNumber);
    const t = tmap.get(p.plyNumber);
    return {
      moveNo: p.moveNumber, color: p.color, san: p.san, uci: p.uci, fen: p.fenAfter, fenBefore: p.fenBefore,
      mine: p.color === game.perspective,
      cls: j ? j.moveClass : null,
      winB: j ? Math.round(j.winProbBefore * 100) : null,
      winA: j ? Math.round(j.winProbAfter * 100) : null,
      punished: j ? j.punished : null,
      tag: t ? t.detail : null,
      tagSquare: t ? t.victimSquare : null,
      bestUci: j ? j.bestMove : null,
      bestSan: j && j.bestMove ? bestSan(p.fenBefore, j.bestMove) : null,
    };
  });

  let posEvals: number[] | null = null;
  let bestMoves: ({ uci: string; san: string } | null)[] | null = null;
  if (game.moves.length) {
    const myWhite = game.perspective === 'white';
    const fens = [game.moves[0].fenBefore, ...game.moves.map((p) => p.fenAfter)];
    posEvals = [];
    bestMoves = [];
    for (const f of fens) {
      const b = new Chess(f);
      if (b.isGameOver()) {
        const whiteWp = b.isCheckmate() ? (b.turn() === 'w' ? 0.0 : 1.0) : 0.5;
        posEvals.push(Math.round((myWhite ? whiteWp : 1 - whiteWp) * 100));
        bestMoves.push(null);
      } else {
        const w = whiteWinProb(f, evaluator);
        posEvals.push(Math.round((myWhite ? w : 1 - w) * 100));
        const ev = evaluator(f);
        bestMoves.push(ev.bestMove ? { uci: ev.bestMove, san: bestSan(f, ev.bestMove)! } : null);
      }
    }
  }

  const acc = accuracy(a.judgments.map((j) => ({ winProbBefore: j.winProbBefore, winProbAfter: j.winProbAfter })));
  return {
    white: game.white.username, black: game.black.username, opponent: opponent(game).username,
    perspective: game.perspective, result: gameResult(game), timeClass: game.timeClass, url: game.url,
    startFen: game.moves.length ? game.moves[0].fenBefore : '',
    plies, posEvals, bestMoves, accuracy: acc, elo: null as number | null,
  };
}

export function viewerData(username: string, analyses: GameAnalysis[], evaluator: Evaluator) {
  const urlToIdx = new Map(analyses.map((a, i) => [a.game.url, i]));
  const dl = decisiveLosses(analyses);
  for (const e of dl) e.gameIndex = urlToIdx.get(e.url) ?? null;

  const games = analyses.map((a) => gameData(a, evaluator));
  const accs = games.map((g) => g.accuracy).filter((x): x is number => x != null);
  const avgAcc = accs.length ? accs.reduce((s, x) => s + x, 0) / accs.length : null;
  const ratings = analyses.map((a) => myRating(a.game)).filter((x): x is number => x != null);
  const avgRating = ratings.length ? ratings.reduce((s, x) => s + x, 0) / ratings.length : null;
  games.forEach((g, i) => { g.elo = eloEstimate(g.accuracy, myRating(analyses[i].game), avgAcc, avgRating); });

  const fs = findings(analyses);
  for (const f of fs) for (const ex of f.examples) ex.gameIndex = urlToIdx.get(ex.url) ?? null;

  return { username, games, findings: fs, decisiveLosses: dl };
}
