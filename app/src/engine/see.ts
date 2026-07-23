// Static exchange evaluation + material helpers — TS port of the SEE in
// chess_coach/tag.py. Uses chess.js for board state; captures are simulated with
// put/remove (bypassing legality, like python-chess push) on a throwaway board.
import { Chess, Square } from 'chess.js';

export const PIECE_VALUE: Record<string, number> = {
  p: 100, n: 300, b: 300, r: 500, q: 900, k: 10000,
};

function leastValuableAttacker(b: Chess, sq: Square, color: 'w' | 'b'): Square | null {
  const atk = b.attackers(sq, color);
  if (!atk.length) return null;
  return atk.reduce((best, s) => (PIECE_VALUE[b.get(s)!.type] < PIECE_VALUE[b.get(best)!.type] ? s : best));
}

// Best material `side` can gain by (optionally) recapturing on `sq`.
function seeRecapture(b: Chess, sq: Square, side: 'w' | 'b'): number {
  const lva = leastValuableAttacker(b, sq, side);
  if (!lva) return 0;
  const piece = b.get(lva)!;
  const other = side === 'w' ? 'b' : 'w';
  if (piece.type === 'k' && b.attackers(sq, other).length) return 0; // king can't take into defense
  const capturedValue = PIECE_VALUE[b.get(sq)!.type];
  const fen = b.fen();
  b.remove(sq);
  b.remove(lva);
  const promo = piece.type === 'p' && (sq[1] === '8' || sq[1] === '1');
  b.put({ type: promo ? 'q' : piece.type, color: piece.color }, sq);
  const gain = capturedValue - seeRecapture(b, sq, other);
  b.load(fen, { skipValidation: true });
  return Math.max(0, gain);
}

// Net material (centipawns) for the side making the capture `from`->`to`.
export function staticExchangeEval(fen: string, from: Square, to: Square): number {
  const b = new Chess(fen);
  const mover = b.get(from);
  if (!mover) return 0;
  const target = b.get(to);
  const isEp = mover.type === 'p' && from[0] !== to[0] && !target;
  let capturedValue: number;
  if (isEp) capturedValue = PIECE_VALUE.p;
  else if (!target) return 0;
  else capturedValue = PIECE_VALUE[target.type];
  const other = mover.color === 'w' ? 'b' : 'w';
  if (isEp) b.remove((to[0] + from[1]) as Square);
  b.remove(to);
  b.remove(from);
  const promo = mover.type === 'p' && (to[1] === '8' || to[1] === '1');
  b.put({ type: promo ? 'q' : mover.type, color: mover.color }, to);
  return capturedValue - seeRecapture(b, to, other);
}

// Best material-winning capture for the side to move: {see, to, victim} or null.
export function bestFreeCapture(fen: string): { see: number; to: Square; victim: string } | null {
  const b = new Chess(fen);
  let best: { see: number; to: Square; victim: string } | null = null;
  for (const mv of b.moves({ verbose: true })) {
    if (!(mv.flags.includes('c') || mv.flags.includes('e'))) continue;
    const see = staticExchangeEval(fen, mv.from, mv.to);
    if (see <= 0) continue;
    const victim = mv.flags.includes('e') ? 'p' : mv.captured!;
    if (!best || see > best.see) best = { see, to: mv.to, victim };
  }
  return best;
}

// Material the mover captured with their own move (0 if not a capture).
export function moveCaptureValue(fenBefore: string, uci: string): number {
  const b = new Chess(fenBefore);
  const from = uci.slice(0, 2) as Square, to = uci.slice(2, 4) as Square;
  const mover = b.get(from);
  if (!mover) return 0;
  const target = b.get(to);
  if (mover.type === 'p' && from[0] !== to[0] && !target) return PIECE_VALUE.p; // ep
  return target ? PIECE_VALUE[target.type] : 0;
}

// (my material − opponent material) in centipawns, from my POV.
export function myMaterial(fen: string, meWhite: boolean): number {
  const b = new Chess(fen);
  let diff = 0;
  for (const row of b.board()) {
    for (const sq of row) {
      if (!sq || sq.type === 'k') continue;
      diff += (sq.color === 'w' ? 1 : -1) * PIECE_VALUE[sq.type];
    }
  }
  return meWhite ? diff : -diff;
}
