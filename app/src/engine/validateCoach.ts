// Capstone: validate the whole TS pipeline (viewerData) against Python viewer_data.
//   npx tsx src/engine/validateCoach.ts <refCoach.json>
import * as fs from 'fs';
import { Evaluation, Game } from './model';
import { analyzeGame, viewerData } from './coach';

const data = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
const evaluator = (fen: string): Evaluation => {
  const e = data.evalmap[fen];
  if (!e) throw new Error('no eval ' + fen);
  return { fen, depth: 16, cp: e.cp, mate: e.mate, bestMove: e.bestMove };
};

const analyses = data.games.map((g: any) => {
  const game: Game = {
    gameId: '', url: g.url, playedAt: null, timeClass: g.timeClass, timeControl: '', rated: false,
    rules: 'chess', eco: null, white: g.white, black: g.black, perspective: g.perspective, moves: g.plies, pgn: '',
  };
  return analyzeGame(game, evaluator);
});
const ts = viewerData('mastapate', analyses, evaluator);

// deep compare (order-sensitive for arrays, key-set for objects); report first diffs
let diffs = 0;
function cmp(a: any, b: any, path: string) {
  if (diffs > 15) return;
  if (a === b) return;
  if (a == null || b == null || typeof a !== typeof b) { console.log(`${path}: TS=${JSON.stringify(a)} PY=${JSON.stringify(b)}`); diffs++; return; }
  if (Array.isArray(a)) {
    if (a.length !== b.length) { console.log(`${path}: len TS=${a.length} PY=${b.length}`); diffs++; return; }
    a.forEach((x, i) => cmp(x, b[i], `${path}[${i}]`));
  } else if (typeof a === 'object') {
    const keys = new Set([...Object.keys(a), ...Object.keys(b)]);
    for (const k of keys) cmp(a[k], b[k], `${path}.${k}`);
  } else {
    console.log(`${path}: TS=${JSON.stringify(a)} PY=${JSON.stringify(b)}`); diffs++;
  }
}
cmp(ts, data.payload, 'payload');
console.log(diffs === 0 ? `ALL MATCH ✓ (full pipeline, ${ts.games.length} games)` : `${diffs}+ MISMATCHES ✗`);
process.exit(diffs === 0 ? 0 : 1);
