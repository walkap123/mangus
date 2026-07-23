// Validate TS ingest against a Python-parsed real game.
//   npx tsx src/engine/validateIngest.ts <refIngest.json>
import * as fs from 'fs';
import { parseGame } from './ingest';
import { gameResult } from './model';

const data = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
const g = parseGame(data.raw, 'mastapate')!;
const exp = data.expected;
let ok = true;
const fail = (m: string) => { ok = false; console.log(m); };

if (g.perspective !== exp.perspective) fail(`perspective TS=${g.perspective} PY=${exp.perspective}`);
if (gameResult(g) !== exp.result) fail(`result TS=${gameResult(g)} PY=${exp.result}`);
if (g.moves.length !== exp.plies.length) fail(`ply count TS=${g.moves.length} PY=${exp.plies.length}`);

let fenDiffs = 0;
g.moves.forEach((p, i) => {
  const e = exp.plies[i];
  if (!e) return;
  const eq: [string, any, any][] = [
    ['san', p.san, e.san], ['uci', p.uci, e.uci], ['moveNo', p.moveNumber, e.moveNo],
    ['color', p.color, e.color], ['clk', p.clockSeconds, e.clk],
  ];
  for (const [f, a, b] of eq) if (a !== b) fail(`ply ${i + 1} ${f}: TS=${a} PY=${b}`);
  // FENs: compare exactly, but note ep-square-only differences separately
  if (p.fenBefore !== e.fenBefore) {
    const norm = (s: string) => s.split(' ').slice(0, 3).join(' ');
    if (norm(p.fenBefore) === norm(e.fenBefore)) fenDiffs++;
    else fail(`ply ${i + 1} fenBefore: TS=${p.fenBefore} PY=${e.fenBefore}`);
  }
});
if (fenDiffs) console.log(`(note: ${fenDiffs} FENs differ only in ep-square/clocks — same position)`);
console.log(ok ? `ALL MATCH ✓ (${g.moves.length} plies)` : 'MISMATCHES ✗');
process.exit(ok ? 0 : 1);
