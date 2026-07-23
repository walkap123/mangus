// Semantic tag detectors — TS port of chess_coach/tag.py, on top of see.ts.
import { Chess } from 'chess.js';
import { Color, Game } from './model';
import { MoveJudgment } from './classify';
import { bestFreeCapture, moveCaptureValue, myMaterial } from './see';

const PIECE_NAME: Record<string, string> = {
  p: 'pawn', n: 'knight', b: 'bishop', r: 'rook', q: 'queen', k: 'king',
};

export interface Tag {
  name: string;
  plyNumber: number;
  color: Color;
  san: string;
  detail: string;
  winProbLost: number | null;
  materialCp: number | null;
  victimSquare: string | null;
  victimPiece: string | null;
  punished: boolean | null;
}

function byNumMap(game: Game) {
  return new Map(game.moves.map((p) => [p.plyNumber, p]));
}
function maxPly(game: Game): number {
  return game.moves.length ? Math.max(...game.moves.map((p) => p.plyNumber)) : 0;
}

export function hungPieceDetect(
  game: Game, judgments: MoveJudgment[], minSwing = 0.15, minMaterial = 300,
): Tag[] {
  const jmap = new Map(judgments.map((j) => [j.plyNumber, j]));
  const byNum = byNumMap(game);
  const tags: Tag[] = [];
  for (const ply of game.moves) {
    const j = jmap.get(ply.plyNumber);
    if (!j || j.winProbLost < minSwing) continue;
    const cap = bestFreeCapture(ply.fenAfter);
    if (!cap) continue;
    const netCp = cap.see - moveCaptureValue(ply.fenBefore, ply.uci);
    if (netCp < minMaterial) continue;
    const piece = PIECE_NAME[cap.victim];
    const square = cap.to;
    const nxt = byNum.get(ply.plyNumber + 1);
    const punished = !!nxt && nxt.uci.slice(2, 4) === square;
    const note = punished ? '' : ' — opponent missed it';
    tags.push({
      name: 'hung_piece', plyNumber: ply.plyNumber, color: ply.color, san: ply.san,
      detail: `hung a ${piece} on ${square} (-${Math.trunc(netCp / 100)})${note}`,
      winProbLost: j.winProbLost, materialCp: netCp, victimSquare: square, victimPiece: piece, punished,
    });
  }
  return tags;
}

export function allowedTacticDetect(
  game: Game, judgments: MoveJudgment[], minSwing = 0.15, minMaterial = 300, lookahead = 6,
): Tag[] {
  const jmap = new Map(judgments.map((j) => [j.plyNumber, j]));
  const byNum = byNumMap(game);
  if (!game.moves.length) return [];
  const mp = maxPly(game);
  const meWhite = game.perspective === 'white';
  const tags: Tag[] = [];
  for (const ply of game.moves) {
    const j = jmap.get(ply.plyNumber);
    if (!j || !j.punished || j.winProbLost < minSwing) continue;
    const cap = bestFreeCapture(ply.fenAfter);
    if (cap) {
      const net = cap.see - moveCaptureValue(ply.fenBefore, ply.uci);
      if (net >= minMaterial) continue; // a one-move hang -> hung-piece owns it
    }
    const endPly = byNum.get(Math.min(ply.plyNumber + lookahead, mp));
    if (!endPly || endPly.plyNumber <= ply.plyNumber) continue;
    const lost = myMaterial(ply.fenAfter, meWhite) - myMaterial(endPly.fenAfter, meWhite);
    if (lost < minMaterial) continue;
    tags.push({
      name: 'allowed_tactic', plyNumber: ply.plyNumber, color: ply.color, san: ply.san,
      detail: `allowed a tactic (-${Math.trunc(lost / 100)})`,
      winProbLost: j.winProbLost, materialCp: lost, victimSquare: null, victimPiece: null, punished: true,
    });
  }
  return tags;
}

function kingPressure(
  byNum: Map<number, Game['moves'][number]>, start: number, mp: number, me: Color, lookahead: number,
): [number, boolean] {
  let checks = 0, mate = false;
  for (let n = start + 1; n <= Math.min(start + lookahead, mp); n++) {
    const p = byNum.get(n);
    if (!p) break;
    if (p.color === me) continue; // only the opponent's moves attack me
    const b = new Chess(p.fenAfter);
    if (b.inCheck()) {
      const side: Color = b.turn() === 'w' ? 'white' : 'black';
      if (side === me) { checks++; if (b.isCheckmate()) mate = true; }
    }
  }
  return [checks, mate];
}

export function allowedAttackDetect(
  game: Game, judgments: MoveJudgment[],
  minSwing = 0.20, collapseTo = 0.30, materialCeiling = 100, lookahead = 6,
): Tag[] {
  const jmap = new Map(judgments.map((j) => [j.plyNumber, j]));
  const byNum = byNumMap(game);
  if (!game.moves.length) return [];
  const mp = maxPly(game);
  const meWhite = game.perspective === 'white';
  const tags: Tag[] = [];
  for (const ply of game.moves) {
    const j = jmap.get(ply.plyNumber);
    if (!j || !j.punished || j.winProbLost < minSwing) continue;
    if (j.winProbAfterReply == null || j.winProbAfterReply > collapseTo) continue;
    const endPly = byNum.get(Math.min(ply.plyNumber + lookahead, mp));
    const lost = endPly && endPly.plyNumber > ply.plyNumber
      ? myMaterial(ply.fenAfter, meWhite) - myMaterial(endPly.fenAfter, meWhite) : 0;
    if (lost >= materialCeiling) continue;
    const [checks, mate] = kingPressure(byNum, ply.plyNumber, mp, game.perspective, lookahead);
    if (!mate && checks === 0) continue;
    tags.push({
      name: 'allowed_attack', plyNumber: ply.plyNumber, color: ply.color, san: ply.san,
      detail: mate ? 'allowed a mating attack' : 'allowed an attack on your king',
      winProbLost: j.winProbLost, materialCp: null, victimSquare: null, victimPiece: null, punished: true,
    });
  }
  return tags;
}

export function tagGame(game: Game, judgments: MoveJudgment[]): Tag[] {
  const tags = [
    ...hungPieceDetect(game, judgments),
    ...allowedTacticDetect(game, judgments),
    ...allowedAttackDetect(game, judgments),
  ];
  tags.sort((a, b) => a.plyNumber - b.plyNumber);
  return tags;
}
