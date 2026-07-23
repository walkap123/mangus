// Validate TS detectors (classify + tag) against Python across many games.
//   npx tsx src/engine/validateTag.ts <refTag.json>
import * as fs from 'fs';
import { classifyGame } from './classify';
import { tagGame } from './tag';
import { Evaluation, Game } from './model';

const games = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
let ok = true;
const fail = (m: string) => { ok = false; console.log(m); };
let total = 0, ties = 0;

for (const g of games) {
  const game: Game = {
    gameId: '', url: g.url, playedAt: null, timeClass: '', timeControl: '', rated: false,
    rules: 'chess', eco: null, white: g.white, black: g.black,
    perspective: g.perspective, moves: g.plies, pgn: '',
  };
  const evaluator = (fen: string): Evaluation => {
    const e = g.evalmap[fen];
    if (!e) throw new Error('no eval ' + fen);
    return { fen, depth: 16, cp: e.cp, mate: e.mate, bestMove: e.bestMove };
  };
  const judgments = classifyGame(game, evaluator, true);
  const tsTags = tagGame(game, judgments);

  if (tsTags.length !== g.tags.length) { fail(`${g.url}: tag count TS=${tsTags.length} PY=${g.tags.length}`); continue; }
  tsTags.forEach((t, i) => {
    const e = g.tags[i];
    total++;
    if (t.name !== e.name) fail(`${g.url}[${i}] name TS=${t.name} PY=${e.name}`);
    if (t.plyNumber !== e.plyNumber) fail(`${g.url}[${i}] ply TS=${t.plyNumber} PY=${e.plyNumber}`);
    if (t.punished !== e.punished) fail(`${g.url}[${i}] punished TS=${t.punished} PY=${e.punished}`);
    if (t.materialCp !== e.materialCp) fail(`${g.url}[${i}] material TS=${t.materialCp} PY=${e.materialCp}`);
    // same material but different victim square/detail = equal-SEE tie (equivalent)
    if (t.detail !== e.detail || t.victimSquare !== e.victimSquare) {
      if (t.materialCp === e.materialCp) ties++;
      else fail(`${g.url}[${i}] detail TS="${t.detail}" PY="${e.detail}"`);
    }
  });
}
if (ties) console.log(`(${ties} equal-SEE tie(s): same material, different square)`);
console.log(ok ? `ALL MATCH ✓ (${total} tags across ${games.length} games)` : 'MISMATCHES ✗');
process.exit(ok ? 0 : 1);
