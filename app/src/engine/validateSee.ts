// Validate TS SEE against Python over a whole real game.
//   npx tsx src/engine/validateSee.ts <refSee.json>
import * as fs from 'fs';
import { Square } from 'chess.js';
import { staticExchangeEval, bestFreeCapture, moveCaptureValue, myMaterial } from './see';

const NAME: Record<string, string> = { p: 'pawn', n: 'knight', b: 'bishop', r: 'rook', q: 'queen', k: 'king' };
const data = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
let ok = true;
const fail = (m: string) => { ok = false; console.log(m); };

for (const u of data.unitSee) {
  const see = staticExchangeEval(u.fen, u.uci.slice(0, 2) as Square, u.uci.slice(2, 4) as Square);
  if (see !== u.see) fail(`unit SEE ${u.uci}: TS=${see} PY=${u.see}`);
}

let ties = 0;
data.perGame.forEach((e: any, i: number) => {
  const bfc = bestFreeCapture(e.fen);
  if ((bfc == null) !== (e.bfc == null)) fail(`pos ${i} bfc presence: TS=${!!bfc} PY=${!!e.bfc}`);
  else if (bfc && e.bfc) {
    if (bfc.see !== e.bfc.see) fail(`pos ${i} bfc.see: TS=${bfc.see} PY=${e.bfc.see}`);
    // same SEE but different square/victim = equal-value tie (arbitrary order) — equivalent
    else if (bfc.to !== e.bfc.to || NAME[bfc.victim] !== e.bfc.victim) ties++;
  }
  if (myMaterial(e.fen, data.meWhite) !== e.mat) fail(`pos ${i} material: TS=${myMaterial(e.fen, data.meWhite)} PY=${e.mat}`);
  if (moveCaptureValue(e.fenBefore, e.uci) !== e.mcv) fail(`pos ${i} mcv: TS=${moveCaptureValue(e.fenBefore, e.uci)} PY=${e.mcv}`);
});

if (ties) console.log(`(${ties} equal-SEE tie(s): same material, different square — equivalent)`);
console.log(ok ? `ALL MATCH ✓ (${data.perGame.length} positions: SEE, best-capture, material, capture-value)` : 'MISMATCHES ✗');
process.exit(ok ? 0 : 1);
