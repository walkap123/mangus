// Internal engine data model — TS port of chess_coach/models.py.

export type Color = 'white' | 'black';
export type GameResult = 'win' | 'loss' | 'draw' | 'unknown';

export interface Player {
  username: string;
  rating: number | null;
  resultRaw: string | null;
}

export interface Ply {
  plyNumber: number;   // 1-based half-move index
  moveNumber: number;  // full-move number
  color: Color;
  san: string;
  uci: string;
  fenBefore: string;
  fenAfter: string;
  clockSeconds: number | null;
}

export interface Evaluation {
  fen: string;
  depth: number;
  cp: number | null;
  mate: number | null;
  bestMove: string | null;
}

export interface Game {
  gameId: string;
  url: string;
  playedAt: number | null; // unix epoch (UTC)
  timeClass: string;
  timeControl: string;
  rated: boolean;
  rules: string;
  eco: string | null;
  white: Player;
  black: Player;
  perspective: Color;
  moves: Ply[];
  pgn: string;
}

const DRAW_RESULTS = new Set([
  'agreed', 'stalemate', 'repetition', 'insufficient', '50move', 'timevsinsufficient',
]);

export function resultFor(p: Player): GameResult {
  const r = (p.resultRaw || '').toLowerCase();
  if (r === 'win') return 'win';
  if (DRAW_RESULTS.has(r)) return 'draw';
  if (r === '') return 'unknown';
  return 'loss';
}

export const me = (g: Game): Player => (g.perspective === 'white' ? g.white : g.black);
export const opponent = (g: Game): Player => (g.perspective === 'white' ? g.black : g.white);
export const gameResult = (g: Game): GameResult => resultFor(me(g));
export const myRating = (g: Game): number | null => me(g).rating;
export const opponentRating = (g: Game): number | null => opponent(g).rating;
export const myPlies = (g: Game): Ply[] => g.moves.filter((p) => p.color === g.perspective);

// Evaluation from side-to-move POV -> from `mover`'s POV (negate if it's not their turn).
export function evalPov(e: Evaluation, mover: Color): Evaluation {
  const stm: Color = e.fen.split(' ')[1] === 'w' ? 'white' : 'black';
  if (stm === mover) return e;
  return {
    ...e,
    cp: e.cp == null ? null : -e.cp,
    mate: e.mate == null ? null : -e.mate,
  };
}
