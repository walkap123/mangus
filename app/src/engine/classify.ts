// Move classifier — TypeScript port of chess_coach/classify.py.
// Keep in lockstep with the Python reference (validated in engine/__tests__).
import { Color, Evaluation, Game, Ply, evalPov, gameResult } from './model';

export type MoveClass = 'best' | 'good' | 'inaccuracy' | 'mistake' | 'blunder';

// Logistic steepness mapping centipawns -> win probability (our own constant).
export const CP_TO_WINPROB_K = 0.004;

export function winProb(cp: number | null, mate: number | null): number {
  if (mate != null) return mate > 0 ? 1.0 : 0.0;
  if (cp == null) return 0.5;
  return 1.0 / (1.0 + Math.exp(-CP_TO_WINPROB_K * cp));
}

export interface Thresholds {
  bestEps: number;
  inaccuracy: number;
  mistake: number;
  blunder: number;
}
export const DEFAULT_THRESHOLDS: Thresholds = {
  bestEps: 0.02, inaccuracy: 0.1, mistake: 0.2, blunder: 0.3,
};

export function classifyBucket(lost: number, playedBest: boolean, t: Thresholds = DEFAULT_THRESHOLDS): MoveClass {
  if (playedBest || lost <= t.bestEps) return 'best';
  if (lost < t.inaccuracy) return 'good';
  if (lost < t.mistake) return 'inaccuracy';
  if (lost < t.blunder) return 'mistake';
  return 'blunder';
}

export interface MoveJudgment {
  plyNumber: number;
  color: Color;
  san: string;
  uci: string;
  moveClass: MoveClass;
  winProbBefore: number;
  winProbAfter: number;   // engine best-play (hypothetical)
  winProbLost: number;
  bestMove: string | null;
  playedBest: boolean;
  // actual consequence (from the real continuation)
  winProbAfterReply: number | null;
  retainedLoss: number | null;
  punished: boolean | null;
}

export type Evaluator = (fen: string) => Evaluation;

export function judge(ply: Ply, evalBefore: Evaluation, evalAfter: Evaluation, t = DEFAULT_THRESHOLDS): MoveJudgment {
  const mover = ply.color;
  const wpBefore = winProb(evalBefore.cp, evalBefore.mate);
  const after = evalPov(evalAfter, mover);
  const wpAfter = winProb(after.cp, after.mate);
  const lost = Math.max(0, wpBefore - wpAfter);
  const playedBest = evalBefore.bestMove != null && ply.uci === evalBefore.bestMove;
  return {
    plyNumber: ply.plyNumber, color: mover, san: ply.san, uci: ply.uci,
    moveClass: classifyBucket(lost, playedBest, t),
    winProbBefore: wpBefore, winProbAfter: wpAfter, winProbLost: lost,
    bestMove: evalBefore.bestMove, playedBest,
    winProbAfterReply: null, retainedLoss: null, punished: null,
  };
}

export function classifyGame(
  game: Game, evaluator: Evaluator, mineOnly = false, punishRatio = 0.5,
): MoveJudgment[] {
  const byNum = new Map(game.moves.map((p) => [p.plyNumber, p]));
  const out: MoveJudgment[] = [];
  for (const ply of game.moves) {
    if (mineOnly && ply.color !== game.perspective) continue;
    const j = judge(ply, evaluator(ply.fenBefore), evaluator(ply.fenAfter));

    // what the move ACTUALLY cost, from the real continuation
    const nxt2 = byNum.get(ply.plyNumber + 2);
    let wpReply: number | null;
    if (nxt2) {
      const ev = evaluator(nxt2.fenBefore);
      wpReply = winProb(ev.cp, ev.mate);
    } else {
      const r = gameResult(game);
      wpReply = r === 'win' ? 1.0 : r === 'loss' ? 0.0 : r === 'draw' ? 0.5 : null;
    }
    if (wpReply != null) {
      j.winProbAfterReply = wpReply;
      j.retainedLoss = Math.max(0, j.winProbBefore - wpReply);
      j.punished = j.winProbLost > 1e-9 && j.retainedLoss >= punishRatio * j.winProbLost;
    }
    out.push(j);
  }
  return out;
}
