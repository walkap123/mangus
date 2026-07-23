// On-device analysis orchestrator. Fetch games, warm every position through the
// WebView Stockfish (queued + cached), then run the synchronous pipeline.
import { Chess } from 'chess.js';
import { ChessComClient } from './ingest';
import { analyzeGame, viewerData } from './coach';
import { sfEngine } from './sfEngine';
import type { Evaluation } from './model';
import type { Payload } from '../types';

const UA = 'mangus/0.1 (walkerpate22@gmail.com)';

function terminalEval(fen: string, b: Chess): Evaluation {
  // checkmate: side to move is lost; stalemate/other: drawish
  return { fen, depth: sfEngine.depth, cp: b.isCheckmate() ? -100000 : 0, mate: null, bestMove: null };
}

export interface Progress { done: number; total: number; phase: string }

export async function analyzeOnDevice(
  username: string,
  opts: { maxGames?: number; depth?: number; onProgress?: (p: Progress) => void } = {},
): Promise<Payload> {
  const onProgress = opts.onProgress ?? (() => {});
  sfEngine.depth = opts.depth ?? 12;

  onProgress({ done: 0, total: 0, phase: 'fetching your games' });
  const games = await new ChessComClient(UA).fetchGames(username, { maxGames: opts.maxGames ?? 8 });
  if (!games.length) throw new Error(`No standard games found for ${username}`);

  onProgress({ done: 0, total: 0, phase: 'starting engine' });
  await sfEngine.waitReady();

  // every distinct position: start + each fenAfter covers all the engine needs
  const posSet = new Set<string>();
  for (const g of games) {
    if (!g.moves.length) continue;
    posSet.add(g.moves[0].fenBefore);
    for (const p of g.moves) posSet.add(p.fenAfter);
  }
  const positions = [...posSet];
  const evalMap = new Map<string, Evaluation>();
  let done = 0;
  for (const fen of positions) {
    const b = new Chess(fen);
    evalMap.set(fen, b.isGameOver() ? terminalEval(fen, b) : await sfEngine.evaluate(fen));
    onProgress({ done: ++done, total: positions.length, phase: 'analyzing' });
  }

  const evaluator = (fen: string): Evaluation => {
    const e = evalMap.get(fen);
    if (e) return e;
    const b = new Chess(fen);
    if (b.isGameOver()) return terminalEval(fen, b);
    throw new Error('missing eval for ' + fen);
  };

  const analyses = games.map((g) => analyzeGame(g, evaluator));
  return viewerData(username, analyses, evaluator) as Payload;
}
