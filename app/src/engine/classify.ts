// Move classifier — TypeScript port of chess_coach/classify.py.
// Keep in lockstep with the Python reference (validated in engine/__tests__).

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
