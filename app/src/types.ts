// Shapes returned by the mangus API (mirror of chess_coach/viewer.py viewer_data).

export type Color = 'white' | 'black';

export interface Ply {
  moveNo: number;
  color: Color;
  san: string;
  uci: string;
  fen: string;
  fenBefore: string;
  mine: boolean;
  cls: 'best' | 'good' | 'inaccuracy' | 'mistake' | 'blunder' | null;
  winB: number | null;
  winA: number | null;
  punished: boolean | null;
  tag: string | null;
  tagSquare: string | null;
  bestUci: string | null;
  bestSan: string | null;
}

export interface Game {
  white: string;
  black: string;
  opponent: string;
  perspective: Color;
  result: string;
  timeClass: string;
  url: string;
  startFen: string;
  plies: Ply[];
  posEvals: number[] | null;
  bestMoves: ({ uci: string; san: string } | null)[] | null;
  accuracy: number | null;
  elo: number | null;
}

export interface FindingExample {
  url?: string;
  move?: string;
  detail?: string;
  ply?: number;
  result?: string;
  punished?: boolean;
  gameIndex?: number | null;
}

export interface Finding {
  key: string;
  headline: string;
  detail: string;
  examples: FindingExample[];
}

export interface DecisiveLoss {
  url: string;
  opponent: string;
  decisive: boolean;
  detail: string;
  gameIndex: number | null;
  ply?: number;
  move_number?: number;
  san?: string;
  kind?: string;
  win_before?: number;
  win_after?: number;
}

export interface Payload {
  username: string;
  games: Game[];
  findings: Finding[];
  decisiveLosses: DecisiveLoss[];
}
