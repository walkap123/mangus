"""Interactive board viewer — the prototype of the game-review screen.

Generates a single self-contained HTML file (no external assets) that lets you
pick an analyzed game and step through it on a board. Features:

  * evaluation bar (your win chance) beside the board,
  * board auto-flipped to your side,
  * every one of your moves labelled best/good/inaccuracy/mistake/blunder with
    its win% swing and any semantic tag (hung a piece, allowed a tactic, ...),
  * the tag's square ringed on the board,
  * a "What should I have played?" button that draws the engine's best move
    (green) next to what you actually played (red),
  * the two coaching lenses (habits to fix / why you actually lost) below,
    click a loss to jump straight to the deciding move.

It reads the same per-move data the future SwiftUI review screen will render,
so it doubles as the UI spec for the iOS port.
"""

from __future__ import annotations

import json
import math
from typing import TYPE_CHECKING, Optional

import chess

from .classify import MoveJudgment, win_prob
from .models import Color

if TYPE_CHECKING:
    from .coach import CoachReport, GameAnalysis
    from .eval import StockfishEval

START_FEN = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"


def _white_winprob(fen: str, evaluator) -> float:
    """White-POV win probability for a position (0..1)."""
    b = chess.Board(fen)
    if b.is_game_over():
        if b.is_checkmate():
            return 0.0 if b.turn == chess.WHITE else 1.0
        return 0.5
    ev = evaluator.evaluate(fen)
    wp = win_prob(ev.cp, ev.mate)          # side-to-move POV
    return wp if b.turn == chess.WHITE else 1.0 - wp


def _accuracy(judgments: "list[MoveJudgment]") -> Optional[float]:
    """Our own per-game accuracy over the user's moves (0-100).

    Each move scores by how much win% it lost vs. best play (exponential decay,
    our own constant); the game score is their mean. Not identical to chess.com's
    number, but the same idea: clean play scores high, blunders drag it down.
    """
    if not judgments:
        return None
    accs = []
    for j in judgments:
        wl = max(0.0, j.win_prob_before - j.win_prob_after) * 100.0  # win% points lost
        accs.append(max(1.0, min(100.0, 100.0 * math.exp(-0.06 * wl))))
    # harmonic mean: your worst moves weigh heaviest, so blunders actually bite.
    # k=0.06 calibrated so a blunder-heavy game lands near chess.com's number.
    return round(len(accs) / sum(1.0 / a for a in accs), 1)


def _elo_estimate(accuracy: Optional[float]) -> Optional[int]:
    """Rough 'you played like ~N' rating from accuracy. An estimate, not a rating.
    Anchored to chess.com: ~20% accuracy ≈ ~100, scaling up from there."""
    if accuracy is None:
        return None
    return int(max(100, min(2600, round(100 + 30 * (accuracy - 20)))))


def _best_san(fen_before: str, uci: Optional[str]) -> Optional[str]:
    if not uci:
        return None
    try:
        b = chess.Board(fen_before)
        return b.san(chess.Move.from_uci(uci))
    except Exception:
        return uci


def _game_data(a: "GameAnalysis", evaluator) -> dict:
    game = a.game
    jmap = {j.ply_number: j for j in a.judgments}
    tmap = {}
    for t in a.tags:
        tmap.setdefault(t.ply_number, t)

    plies = []
    for p in game.moves:
        j = jmap.get(p.ply_number)
        tg = tmap.get(p.ply_number)
        best_uci = j.best_move if j else None
        plies.append({
            "moveNo": p.move_number, "color": p.color.value,
            "san": p.san, "uci": p.uci, "fen": p.fen_after,
            "fenBefore": p.fen_before,
            "mine": p.color is game.perspective,
            "cls": j.move_class.value if j else None,
            "winB": round(j.win_prob_before * 100) if j else None,
            "winA": round(j.win_prob_after * 100) if j else None,
            "punished": (j.punished if j else None),
            "tag": tg.detail if tg else None,
            "tagSquare": tg.victim_square if tg else None,
            "bestUci": best_uci,
            "bestSan": _best_san(p.fen_before, best_uci) if (j and best_uci) else None,
        })

    pos_evals = None
    if evaluator is not None and game.moves:
        my_white = game.perspective is Color.WHITE
        fens = [game.moves[0].fen_before] + [p.fen_after for p in game.moves]
        pos_evals = []
        for f in fens:
            w = _white_winprob(f, evaluator)
            pos_evals.append(round((w if my_white else 1.0 - w) * 100))

    accuracy = _accuracy(a.judgments)
    return {
        "white": game.white.username, "black": game.black.username,
        "opponent": game.opponent.username, "perspective": game.perspective.value,
        "result": game.result.value, "timeClass": game.time_class, "url": game.url,
        "startFen": game.moves[0].fen_before if game.moves else START_FEN,
        "plies": plies, "posEvals": pos_evals,
        "accuracy": accuracy, "elo": _elo_estimate(accuracy),
    }


def viewer_data(report: "CoachReport", evaluator: "StockfishEval | None" = None) -> dict:
    """The per-move + coaching payload the review UI renders.

    Single source of truth shared by the HTML viewer and the HTTP API (and the
    eventual React Native app), so all clients read the same shape.
    """
    url_to_idx = {a.game.url: i for i, a in enumerate(report.analyses)}
    dl = report.decisive_losses()
    for e in dl:
        e["gameIndex"] = url_to_idx.get(e["url"])
    return {
        "username": report.username,
        "games": [_game_data(a, evaluator) for a in report.analyses],
        "findings": [f.to_dict() for f in report.findings()],
        "decisiveLosses": dl,
    }


def render_viewer(report: "CoachReport", evaluator: "StockfishEval | None" = None) -> str:
    return _TEMPLATE.replace("/*__DATA__*/", json.dumps(viewer_data(report, evaluator)))


_TEMPLATE = r"""<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>mangus — review</title>
<style>
  :root { color-scheme: light dark; --bg:#1a1a1c; --card:#242427; --fg:#e8e8ea;
          --muted:#9a9aa2; --line:#33333a; --accent:#e0803a; --green:#4ade80;
          --lt:#ebecd0; --dk:#6f9350; --hl:rgba(246,240,90,.55); }
  * { box-sizing: border-box; }
  body { margin:0; background:var(--bg); color:var(--fg);
         font:15px/1.5 -apple-system, system-ui, sans-serif; }
  .wrap { max-width:980px; margin:0 auto; padding:1.2rem 1rem 3rem; }
  h1 { font-size:1.3rem; margin:0 0 .1rem; } h1 span { color:var(--accent); }
  h2 { font-size:1rem; margin:1.4rem 0 .5rem; }
  .sub { color:var(--muted); font-size:.85rem; margin-bottom:1rem; }
  select { background:var(--card); color:var(--fg); border:1px solid var(--line);
           border-radius:8px; padding:.5rem .6rem; font-size:.9rem; width:100%;
           margin-bottom:1rem; }
  .main { display:flex; gap:1.2rem; flex-wrap:wrap; align-items:flex-start; }
  .left { flex:1 1 380px; min-width:300px; }
  .right { flex:1 1 300px; min-width:260px; }
  .boardrow { display:flex; gap:8px; align-items:stretch; }
  .evalbar { width:20px; border-radius:6px; overflow:hidden; background:#111;
             position:relative; flex:none; }
  .evalfill { position:absolute; left:0; right:0; bottom:0; background:#e8e8ea;
              transition:height .15s; }
  .evalnum { position:absolute; bottom:2px; left:0; right:0; text-align:center;
             font-size:.55rem; color:#111; font-weight:700; }
  .boardwrap { position:relative; flex:1; }
  #board { width:100%; aspect-ratio:1; display:grid;
           grid-template-columns:repeat(8,1fr); grid-template-rows:repeat(8,1fr);
           border-radius:10px; overflow:hidden; box-shadow:0 6px 24px rgba(0,0,0,.4); }
  #ov { position:absolute; inset:0; pointer-events:none; }
  .sq { display:flex; align-items:center; justify-content:center;
        font-size:min(6.5vw,42px); line-height:1; user-select:none; position:relative; }
  .sq.lt { background:var(--lt); } .sq.dk { background:var(--dk); }
  .sq.hl::after { content:""; position:absolute; inset:0; background:var(--hl); }
  .pc { position:relative; z-index:1; }
  .pc.w { color:#fff; text-shadow:0 0 2px #000,0 1px 2px rgba(0,0,0,.6); }
  .pc.b { color:#111; text-shadow:0 0 1px #000; }
  .controls { display:flex; gap:.4rem; margin-top:.7rem; }
  .controls button { flex:1; background:var(--card); color:var(--fg);
        border:1px solid var(--line); border-radius:8px; padding:.6rem 0;
        font-size:1rem; cursor:pointer; }
  .controls button:hover { border-color:var(--accent); }
  .anno { background:var(--card); border:1px solid var(--line); border-radius:10px;
          padding:.8rem .9rem; min-height:120px; margin-bottom:.9rem; }
  .anno .mv { font-size:1.1rem; font-weight:600; }
  .badge { display:inline-block; padding:.1rem .5rem; border-radius:6px;
           font-size:.8rem; font-weight:700; color:#111; margin-left:.4rem; }
  .swing { color:var(--muted); font-size:.9rem; margin-top:.3rem; }
  .tagline { margin-top:.4rem; font-weight:600; color:#f66; }
  .miss { color:var(--muted); font-weight:400; }
  .bestbtn { margin-top:.6rem; background:var(--green); color:#062; border:none;
             border-radius:7px; padding:.45rem .7rem; font-weight:700; cursor:pointer; }
  .bestinfo { margin-top:.5rem; font-size:.92rem; }
  .bestinfo .g { color:var(--green); font-weight:700; }
  .bestinfo .r { color:#f66; font-weight:700; }
  .moves { background:var(--card); border:1px solid var(--line); border-radius:10px;
           padding:.6rem .7rem; max-height:300px; overflow:auto; font-size:.9rem; }
  .moves .mn { color:var(--muted); margin-right:.2rem; }
  .mv-item { cursor:pointer; padding:.05rem .3rem; border-radius:5px; display:inline-block; }
  .mv-item:hover { background:#0003; }
  .mv-item.cur { background:var(--accent); color:#111; font-weight:700; }
  .dot { display:inline-block; width:.5rem; height:.5rem; border-radius:50%;
         margin-left:.15rem; vertical-align:middle; }
  .lenses { display:flex; gap:1.2rem; flex-wrap:wrap; }
  .lens { flex:1 1 320px; }
  .finding { border-left:3px solid var(--accent); padding:.35rem .8rem; margin:.6rem 0; }
  .finding .h { font-weight:600; }
  .finding .d { color:var(--muted); font-size:.85rem; }
  .loss { background:var(--card); border:1px solid var(--line); border-radius:8px;
          padding:.5rem .7rem; margin:.5rem 0; cursor:pointer; }
  .loss:hover { border-color:var(--accent); }
  .loss.flat { cursor:default; opacity:.7; }
  .loss .k { font-weight:600; }
  a { color:var(--accent); }
</style></head><body><div class="wrap">
<h1>mangus <span>review</span></h1>
<div class="sub" id="sub"></div>
<select id="gamesel"></select>
<div class="main">
  <div class="left">
    <div class="boardrow">
      <div class="evalbar"><div class="evalfill" id="evalfill"></div>
        <div class="evalnum" id="evalnum"></div></div>
      <div class="boardwrap"><div id="board"></div>
        <svg id="ov" viewBox="0 0 8 8" preserveAspectRatio="none">
          <defs>
            <marker id="ahG" markerWidth="4" markerHeight="4" refX="2.4" refY="2"
                    orient="auto"><path d="M0,0 L4,2 L0,4 z" fill="#4ade80"/></marker>
            <marker id="ahR" markerWidth="4" markerHeight="4" refX="2.4" refY="2"
                    orient="auto"><path d="M0,0 L4,2 L0,4 z" fill="#f66"/></marker>
          </defs></svg>
      </div>
    </div>
    <div class="controls">
      <button id="bStart">&#124;&#9664;</button><button id="bPrev">&#9664;</button>
      <button id="bNext">&#9654;</button><button id="bEnd">&#9654;&#124;</button>
    </div>
  </div>
  <div class="right">
    <div class="anno" id="anno"></div>
    <div class="moves" id="moves"></div>
  </div>
</div>
<h2>Coaching</h2>
<div class="lenses">
  <div class="lens"><h2>All your mistakes</h2><div id="habits"></div></div>
  <div class="lens"><h2>Why you actually lost</h2><div id="losses"></div></div>
</div>
<script>
const DATA = /*__DATA__*/;
const GLYPH={p:'♟',n:'♞',b:'♝',r:'♜',q:'♛',k:'♚'}, FILES='abcdefgh';
const CLS={best:{l:'Best',c:'#4ade80'},good:{l:'Good',c:'#93c5a0'},
  inaccuracy:{l:'Inaccuracy',c:'#fbbf24'},mistake:{l:'Mistake',c:'#fb923c'},
  blunder:{l:'Blunder',c:'#ef4444'}};
let gi=0, ply=0, showBest=false;
const $=id=>document.getElementById(id);
const boardEl=$('board'), ov=$('ov'), annoEl=$('anno'), movesEl=$('moves'),
      subEl=$('sub'), sel=$('gamesel');

DATA.games.forEach((g,i)=>{ const o=document.createElement('option'); o.value=i;
  o.textContent=`${g.timeClass} vs ${g.opponent} — ${g.result} (${g.plies.length} plies)`;
  sel.appendChild(o); });
sel.onchange=()=>{ gi=+sel.value; ply=0; showBest=false; renderAll(); };

function game(){ return DATA.games[gi]; }
function flip(){ return game().perspective==='black'; }
function positions(){ const g=game(),a=[g.startFen]; g.plies.forEach(p=>a.push(p.fen)); return a; }
function fenGrid(fen){ const rows=fen.split(' ')[0].split('/');
  const grid=Array.from({length:8},()=>Array(8).fill(null));
  for(let r=0;r<8;r++){ let f=0; for(const ch of rows[r]){
    if(/\d/.test(ch)) f+=+ch; else { grid[7-r][f]=ch; f++; } } } return grid; }
function coord(name){ const file=name.charCodeAt(0)-97, rank=+name[1];
  const col=flip()?7-file:file, row=flip()?rank-1:8-rank; return {x:col+0.5,y:row+0.5}; }

function renderBoard(fen,lastUci){
  const grid=fenGrid(fen), fr=lastUci?lastUci.slice(0,2):null, to=lastUci?lastUci.slice(2,4):null;
  let html='';
  for(let dr=0;dr<8;dr++) for(let dc=0;dc<8;dc++){
    const file=flip()?7-dc:dc, rank=flip()?dr+1:8-dr, ch=grid[rank-1][file];
    const name=FILES[file]+rank, dark=(file+rank)%2===1;
    const hl=(name===fr||name===to)?' hl':'';
    const pc=ch?`<span class="pc ${ch===ch.toUpperCase()?'w':'b'}">${GLYPH[ch.toLowerCase()]}</span>`:'';
    html+=`<div class="sq ${dark?'dk':'lt'}${hl}">${pc}</div>`;
  }
  boardEl.innerHTML=html;
}
function drawOverlay(arrows,marker){
  let s='';
  arrows.forEach(a=>{ const f=coord(a.uci.slice(0,2)), t=coord(a.uci.slice(2,4));
    const col=a.k==='best'?'#4ade80':'#f66', mk=a.k==='best'?'ahG':'ahR';
    const op=a.k==='best'?1:.65;
    s+=`<line x1="${f.x}" y1="${f.y}" x2="${t.x}" y2="${t.y}" stroke="${col}"
        stroke-width="0.17" opacity="${op}" marker-end="url(#${mk})"/>`; });
  if(marker){ const c=coord(marker);
    s+=`<circle cx="${c.x}" cy="${c.y}" r="0.45" fill="none" stroke="#ef4444" stroke-width="0.11"/>`; }
  ov.innerHTML=ov.querySelector('defs').outerHTML+s;
}
function renderEval(){
  const pe=game().posEvals; if(!pe){ $('evalfill').style.height='50%'; $('evalnum').textContent=''; return; }
  const v=pe[ply]; $('evalfill').style.height=v+'%'; $('evalnum').textContent=v+'%';
}
function renderAnno(){
  const g=game(), mv=ply>0?g.plies[ply-1]:null;
  if(!mv){ annoEl.innerHTML='<div class="mv">Starting position</div>'+
    `<div class="swing">You are <b>${g.perspective}</b> vs ${g.opponent} · `+
    `<a href="${g.url}" target="_blank">open on chess.com</a></div>`; return; }
  const num=`${mv.moveNo}.${mv.color==='white'?'':'..'} `;
  let h=`<div class="mv">${num}${mv.san}`;
  if(mv.mine&&mv.cls){ const c=CLS[mv.cls]; h+=`<span class="badge" style="background:${c.c}">${c.l}</span>`; }
  h+='</div>';
  if(mv.mine&&mv.winB!=null) h+=`<div class="swing">your win chance ${mv.winB}% &rarr; ${mv.winA}%</div>`;
  if(mv.tag) h+=`<div class="tagline">${mv.tag}</div>`;
  else if(mv.mine&&(mv.cls==='blunder'||mv.cls==='mistake')&&mv.punished===false)
    h+=`<div class="tagline miss">your opponent didn't punish it</div>`;
  if(mv.mine&&mv.bestUci&&mv.cls!=='best'&&mv.cls!=='good'){
    if(!showBest) h+=`<button class="bestbtn" onclick="toggleBest()">What should I have played?</button>`;
    else { h+=`<div class="bestinfo"><span class="r">You played ${mv.san}</span> — `+
      `best was <span class="g">${mv.bestSan}</span></div>`+
      `<button class="bestbtn" onclick="toggleBest()" style="background:var(--card);color:var(--fg)">&#8617; back</button>`; }
  }
  annoEl.innerHTML=h;
}
function renderMoves(){
  const g=game(); let html='';
  g.plies.forEach((p,i)=>{ if(p.color==='white') html+=`<span class="mn">${p.moveNo}.</span>`;
    const dot=(p.mine&&p.cls&&p.cls!=='best'&&p.cls!=='good')?`<span class="dot" style="background:${CLS[p.cls].c}"></span>`:'';
    html+=`<span class="mv-item${i+1===ply?' cur':''}" data-ply="${i+1}">${p.san}${dot}</span> `; });
  movesEl.innerHTML=html;
  movesEl.querySelectorAll('.mv-item').forEach(el=>el.onclick=()=>{ply=+el.dataset.ply;showBest=false;render();});
  const cur=movesEl.querySelector('.cur'); if(cur) cur.scrollIntoView({block:'nearest'});
}
function render(){
  const g=game(), pos=positions(), mv=ply>0?g.plies[ply-1]:null;
  let boardPly=ply, arrows=[], marker=null, lastUci=(mv?mv.uci:null);
  if(showBest&&mv&&mv.mine&&mv.bestUci){
    boardPly=ply-1; lastUci=null;
    arrows=[{uci:mv.uci,k:'played'},{uci:mv.bestUci,k:'best'}];
  } else if(mv&&mv.tagSquare){ marker=mv.tagSquare; }
  renderBoard(pos[boardPly],lastUci); drawOverlay(arrows,marker);
  renderAnno(); renderMoves(); renderEval();
}
function renderAll(){ const g=game();
  subEl.textContent=`${DATA.username} · ${g.white} vs ${g.black} · ${g.timeClass} · ${g.result}`;
  render(); }
function toggleBest(){ showBest=!showBest; render(); }
function step(d){ ply=Math.max(0,Math.min(game().plies.length,ply+d)); showBest=false; render(); }
$('bStart').onclick=()=>{ply=0;showBest=false;render();};
$('bEnd').onclick=()=>{ply=game().plies.length;showBest=false;render();};
$('bPrev').onclick=()=>step(-1); $('bNext').onclick=()=>step(1);
document.addEventListener('keydown',e=>{
  if(e.key==='ArrowLeft'){step(-1);e.preventDefault();}
  if(e.key==='ArrowRight'){step(1);e.preventDefault();}
  if(e.key==='ArrowUp'){ply=0;showBest=false;render();e.preventDefault();}
  if(e.key==='ArrowDown'){ply=game().plies.length;showBest=false;render();e.preventDefault();}});

// lenses
(function(){
  let h='';
  DATA.findings.forEach(f=>{ h+=`<div class="finding"><div class="h">${f.headline}</div>`+
    (f.detail?`<div class="d">${f.detail}</div>`:'')+`</div>`; });
  $('habits').innerHTML=h||'<div class="d" style="color:var(--muted)">No recurring habits found.</div>';
  let l='';
  DATA.decisiveLosses.forEach(e=>{
    if(e.decisive){ l+=`<div class="loss" data-gi="${e.gameIndex}" data-ply="${e.ply}">`+
      `<div class="k">vs ${e.opponent}: ${e.move_number}. ${e.san} — ${e.detail}</div>`+
      `<div class="d" style="color:var(--muted);font-size:.85rem">win ${e.win_before}% &rarr; ${e.win_after}% · click to jump</div></div>`; }
    else { l+=`<div class="loss flat"><div class="k">vs ${e.opponent}</div>`+
      `<div class="d" style="color:var(--muted);font-size:.85rem">${e.detail}</div></div>`; }
  });
  $('losses').innerHTML=l||'<div class="d" style="color:var(--muted)">No losses in this sample.</div>';
  $('losses').querySelectorAll('.loss[data-gi]').forEach(el=>el.onclick=()=>{
    gi=+el.dataset.gi; sel.value=gi; ply=+el.dataset.ply; showBest=false; renderAll();
    document.querySelector('.main').scrollIntoView({behavior:'smooth',block:'start'}); });
})();
renderAll();
</script></div></body></html>"""
