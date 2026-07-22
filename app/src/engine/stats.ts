// Per-game accuracy + rating-anchored ELO estimate.
// TypeScript port of the helpers in chess_coach/viewer.py.

export interface MoveScore {
  winProbBefore: number;
  winProbAfter: number;
}

// Harmonic mean of per-move scores 100*exp(-0.06*win%_lost); blunders bite.
export function accuracy(moves: MoveScore[]): number | null {
  if (moves.length === 0) return null;
  const accs = moves.map((m) => {
    const wl = Math.max(0, m.winProbBefore - m.winProbAfter) * 100;
    return Math.max(1, Math.min(100, 100 * Math.exp(-0.06 * wl)));
  });
  const hm = accs.length / accs.reduce((s, a) => s + 1 / a, 0);
  return Math.round(hm * 10) / 10;
}

// Rating-anchored: base = your real rating that game, par = your average
// accuracy over the batch, +/-22 rating pts per accuracy point, clamped.
export function eloEstimate(
  acc: number | null, myRating: number | null,
  avgAcc: number | null, avgRating: number | null,
): number | null {
  if (acc == null || avgAcc == null) return null;
  const base = myRating ?? avgRating;
  if (base == null) return null;
  return Math.trunc(Math.max(100, Math.min(base + 800, Math.round(base + 22 * (acc - avgAcc)))));
}
