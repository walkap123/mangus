// Validates the TS engine math against Python reference values.
//   npx tsx src/engine/validate.ts <ref.json>
import * as fs from 'fs';
import { winProb, classifyBucket } from './classify';
import { accuracy, eloEstimate, MoveScore } from './stats';

const ref = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));

const wp = ([[-500, null], [-100, null], [0, null], [100, null], [300, null], [600, null], [null, 3], [null, -2], [null, null]] as [number | null, number | null][])
  .map(([cp, m]) => winProb(cp, m));
const buckets = ([[0, false], [0.02, false], [0.05, false], [0.15, false], [0.25, false], [0.4, false], [0.015, true]] as [number, boolean][])
  .map(([l, pb]) => classifyBucket(l, pb));
const accCases: MoveScore[][] = [
  [{ winProbBefore: 0.6, winProbAfter: 0.6 }, { winProbBefore: 0.6, winProbAfter: 0.55 }, { winProbBefore: 0.5, winProbAfter: 0.2 }],
  [{ winProbBefore: 0.9, winProbAfter: 0.9 }],
  [],
];
const accs = accCases.map((c) => accuracy(c));
const elos = ([[65.2, 627, 55.2, 653], [83.4, 667, 55.2, 653], [20.9, 627, 55.2, 653], [null, 653, 55.2, 653]] as [number | null, number | null, number | null, number | null][])
  .map(([a, mr, aa, ar]) => eloEstimate(a, mr, aa, ar));

const close = (a: any, b: any) => (a == null || b == null ? a === b : Math.abs(a - b) < 1e-9);
let ok = true;
const check = (name: string, got: any[], want: any[], eq: (a: any, b: any) => boolean) =>
  got.forEach((v, i) => { if (!eq(v, want[i])) { ok = false; console.log(`${name}[${i}] TS=${v} PY=${want[i]}`); } });

check('winProb', wp, ref.wp, close);
check('bucket', buckets, ref.buckets, (a, b) => a === b);
check('accuracy', accs, ref.accs, close);
check('elo', elos, ref.elos, (a, b) => a === b);

console.log(ok ? 'ALL MATCH ✓' : 'MISMATCHES ✗');
process.exit(ok ? 0 : 1);
