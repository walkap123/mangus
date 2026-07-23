// Validate TS classifyGame against Python (cached evals as the evaluator).
//   npx tsx src/engine/validateClassify.ts <refClassify.json>
import * as fs from 'fs';
import { parseGame } from './ingest';
import { classifyGame } from './classify';
import { Evaluation } from './model';

const data = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
const g = parseGame(data.raw, 'mastapate')!;
const evaluator = (fen: string): Evaluation => {
  const e = data.evalmap[fen];
  if (!e) throw new Error('no eval for ' + fen);
  return { fen, depth: 16, cp: e.cp, mate: e.mate, bestMove: e.bestMove };
};

const js = classifyGame(g, evaluator, true);
const exp = data.judgments;
let ok = true;
const fail = (m: string) => { ok = false; console.log(m); };
const close = (a: any, b: any) => (a == null || b == null ? a === b : Math.abs(a - b) < 1e-9);

if (js.length !== exp.length) fail(`count TS=${js.length} PY=${exp.length}`);
js.forEach((j, i) => {
  const e = exp[i];
  if (j.plyNumber !== e.ply) fail(`[${i}] ply TS=${j.plyNumber} PY=${e.ply}`);
  if (j.moveClass !== e.cls) fail(`[${i}] cls TS=${j.moveClass} PY=${e.cls}`);
  if (!close(j.winProbBefore, e.wpB)) fail(`[${i}] wpB TS=${j.winProbBefore} PY=${e.wpB}`);
  if (!close(j.winProbAfter, e.wpA)) fail(`[${i}] wpA TS=${j.winProbAfter} PY=${e.wpA}`);
  if (!close(j.winProbLost, e.lost)) fail(`[${i}] lost TS=${j.winProbLost} PY=${e.lost}`);
  if (j.bestMove !== e.best) fail(`[${i}] best TS=${j.bestMove} PY=${e.best}`);
  if (j.playedBest !== e.playedBest) fail(`[${i}] playedBest TS=${j.playedBest} PY=${e.playedBest}`);
  if (!close(j.winProbAfterReply, e.wpReply)) fail(`[${i}] wpReply TS=${j.winProbAfterReply} PY=${e.wpReply}`);
  if (!close(j.retainedLoss, e.retained)) fail(`[${i}] retained TS=${j.retainedLoss} PY=${e.retained}`);
  if (j.punished !== e.punished) fail(`[${i}] punished TS=${j.punished} PY=${e.punished}`);
});
console.log(ok ? `ALL MATCH ✓ (${js.length} judgments)` : 'MISMATCHES ✗');
process.exit(ok ? 0 : 1);
