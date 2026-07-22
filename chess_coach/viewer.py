"""Interactive board viewer — the prototype of the game-review screen.

Generates a single self-contained HTML file (no external assets) that lets you
pick an analyzed game, step through every move with arrows or the keyboard, and
see what each of *your* moves did: best / good / inaccuracy / mistake / blunder,
the win% swing, and any semantic tag (hung a piece, allowed a tactic, allowed a
mating attack, ...). It reads the same per-move data the future SwiftUI review
screen will render, so this doubles as the UI spec.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .coach import CoachReport, GameAnalysis

START_FEN = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"


def _game_data(a: "GameAnalysis") -> dict:
    game = a.game
    jmap = {j.ply_number: j for j in a.judgments}
    tmap: dict[int, str] = {}
    for t in a.tags:
        tmap.setdefault(t.ply_number, t.detail)  # first tag per ply

    plies = []
    for p in game.moves:
        j = jmap.get(p.ply_number)
        plies.append({
            "moveNo": p.move_number,
            "color": p.color.value,
            "san": p.san,
            "uci": p.uci,
            "fen": p.fen_after,
            "mine": p.color is game.perspective,
            "cls": j.move_class.value if j else None,
            "winB": round(j.win_prob_before * 100) if j else None,
            "winA": round(j.win_prob_after * 100) if j else None,
            "punished": (j.punished if j else None),
            "tag": tmap.get(p.ply_number),
        })
    return {
        "white": game.white.username, "black": game.black.username,
        "opponent": game.opponent.username, "perspective": game.perspective.value,
        "result": game.result.value, "timeClass": game.time_class,
        "url": game.url,
        "startFen": game.moves[0].fen_before if game.moves else START_FEN,
        "plies": plies,
    }


def render_viewer(report: "CoachReport") -> str:
    data = {"username": report.username,
            "games": [_game_data(a) for a in report.analyses]}
    return _TEMPLATE.replace("/*__DATA__*/", json.dumps(data))


_TEMPLATE = r"""<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>mangus — review</title>
<style>
  :root { color-scheme: light dark; --bg:#1a1a1c; --card:#242427; --fg:#e8e8ea;
          --muted:#9a9aa2; --line:#33333a; --accent:#e0803a;
          --lt:#ebecd0; --dk:#6f9350; --hl:rgba(246,240,90,.55); }
  * { box-sizing: border-box; }
  body { margin:0; background:var(--bg); color:var(--fg);
         font:15px/1.5 -apple-system, system-ui, sans-serif; }
  .wrap { max-width:900px; margin:0 auto; padding:1.2rem 1rem 3rem; }
  h1 { font-size:1.3rem; margin:0 0 .1rem; }
  h1 span { color:var(--accent); }
  .sub { color:var(--muted); font-size:.85rem; margin-bottom:1rem; }
  select { background:var(--card); color:var(--fg); border:1px solid var(--line);
           border-radius:8px; padding:.5rem .6rem; font-size:.9rem; width:100%;
           margin-bottom:1rem; }
  .main { display:flex; gap:1.2rem; flex-wrap:wrap; align-items:flex-start; }
  .left { flex:1 1 360px; min-width:300px; }
  .right { flex:1 1 300px; min-width:260px; }
  #board { width:100%; aspect-ratio:1; display:grid;
           grid-template-columns:repeat(8,1fr); grid-template-rows:repeat(8,1fr);
           border-radius:10px; overflow:hidden; box-shadow:0 6px 24px rgba(0,0,0,.4); }
  .sq { display:flex; align-items:center; justify-content:center;
        font-size:min(7vw,44px); line-height:1; user-select:none; position:relative; }
  .sq.lt { background:var(--lt); } .sq.dk { background:var(--dk); }
  .sq.hl::after { content:""; position:absolute; inset:0; background:var(--hl); }
  .pc { position:relative; z-index:1; }
  .pc.w { color:#fff; text-shadow:0 0 2px #000, 0 1px 2px rgba(0,0,0,.6); }
  .pc.b { color:#111; text-shadow:0 0 1px #000; }
  .controls { display:flex; gap:.4rem; margin-top:.7rem; }
  .controls button { flex:1; background:var(--card); color:var(--fg);
        border:1px solid var(--line); border-radius:8px; padding:.6rem 0;
        font-size:1rem; cursor:pointer; }
  .controls button:hover { border-color:var(--accent); }
  .anno { background:var(--card); border:1px solid var(--line); border-radius:10px;
          padding:.8rem .9rem; min-height:96px; margin-bottom:.9rem; }
  .anno .mv { font-size:1.1rem; font-weight:600; }
  .badge { display:inline-block; padding:.1rem .5rem; border-radius:6px;
           font-size:.8rem; font-weight:700; color:#111; margin-left:.4rem; }
  .swing { color:var(--muted); font-size:.9rem; margin-top:.3rem; }
  .tagline { margin-top:.4rem; font-weight:600; }
  .tagline.bad { color:#f0a; } .miss { color:var(--muted); font-weight:400; }
  .moves { background:var(--card); border:1px solid var(--line); border-radius:10px;
           padding:.6rem .7rem; max-height:340px; overflow:auto; font-size:.9rem; }
  .moves .mn { color:var(--muted); margin-right:.2rem; }
  .mv-item { cursor:pointer; padding:.05rem .3rem; border-radius:5px;
             display:inline-block; }
  .mv-item:hover { background:#0003; }
  .mv-item.cur { background:var(--accent); color:#111; font-weight:700; }
  .dot { display:inline-block; width:.5rem; height:.5rem; border-radius:50%;
         margin-left:.15rem; vertical-align:middle; }
  a { color:var(--accent); }
</style></head><body><div class="wrap">
<h1>mangus <span>review</span></h1>
<div class="sub" id="sub"></div>
<select id="gamesel"></select>
<div class="main">
  <div class="left">
    <div id="board"></div>
    <div class="controls">
      <button id="bStart">&#124;&#9664;</button>
      <button id="bPrev">&#9664;</button>
      <button id="bNext">&#9654;</button>
      <button id="bEnd">&#9654;&#124;</button>
    </div>
  </div>
  <div class="right">
    <div class="anno" id="anno"></div>
    <div class="moves" id="moves"></div>
  </div>
</div>
<script>
const DATA = /*__DATA__*/;
const GLYPH = {p:'♟',n:'♞',b:'♝',r:'♜',q:'♛',k:'♚'};
const CLS = {
  best:{l:'Best',c:'#4ade80'}, good:{l:'Good',c:'#93c5a0'},
  inaccuracy:{l:'Inaccuracy',c:'#fbbf24'}, mistake:{l:'Mistake',c:'#fb923c'},
  blunder:{l:'Blunder',c:'#ef4444'}
};
let gi = 0, ply = 0;

const boardEl=document.getElementById('board'), annoEl=document.getElementById('anno'),
      movesEl=document.getElementById('moves'), subEl=document.getElementById('sub'),
      sel=document.getElementById('gamesel');

DATA.games.forEach((g,i)=>{
  const o=document.createElement('option'); o.value=i;
  o.textContent=`${g.timeClass} vs ${g.opponent} — ${g.result} (${g.plies.length} plies)`;
  sel.appendChild(o);
});
sel.onchange=()=>{ gi=+sel.value; ply=0; renderAll(); };

function game(){ return DATA.games[gi]; }
function positions(){
  const g=game(); const arr=[g.startFen]; g.plies.forEach(p=>arr.push(p.fen)); return arr;
}
function renderBoard(fen, uci){
  const place=fen.split(' ')[0], rows=place.split('/');
  const from=uci?uci.slice(0,2):null, to=uci?uci.slice(2,4):null;
  let html='';
  for(let r=0;r<8;r++){ const rank=8-r; let file=0;
    for(const ch of rows[r]){
      if(/\d/.test(ch)){ for(let k=0;k<+ch;k++){ html+=sq(file,rank,null,from,to); file++; } }
      else { html+=sq(file,rank,ch,from,to); file++; }
    }
  }
  boardEl.innerHTML=html;
}
function sq(file,rank,ch,from,to){
  const name='abcdefgh'[file]+rank;
  const dark=(file+rank)%2===1;
  const hl=(name===from||name===to)?' hl':'';
  let inner='';
  if(ch){ const w=ch===ch.toUpperCase();
    inner=`<span class="pc ${w?'w':'b'}">${GLYPH[ch.toLowerCase()]}</span>`; }
  return `<div class="sq ${dark?'dk':'lt'}${hl}">${inner}</div>`;
}
function renderAnno(){
  const g=game();
  if(ply===0){ annoEl.innerHTML='<div class="mv">Starting position</div>'+
    `<div class="swing">You are <b>${g.perspective}</b> vs ${g.opponent} · `+
    `<a href="${g.url}" target="_blank">open on chess.com</a></div>`; return; }
  const p=g.plies[ply-1];
  const num=`${p.moveNo}.${p.color==='white'?'':'..'} `;
  let h=`<div class="mv">${num}${p.san}`;
  if(p.mine && p.cls){ const c=CLS[p.cls];
    h+=`<span class="badge" style="background:${c.c}">${c.l}</span>`; }
  h+='</div>';
  if(p.mine && p.winB!=null){ h+=`<div class="swing">win chance ${p.winB}% &rarr; ${p.winA}%</div>`; }
  if(p.tag){ h+=`<div class="tagline bad">${p.tag}</div>`; }
  else if(p.mine && (p.cls==='blunder'||p.cls==='mistake') && p.punished===false){
    h+=`<div class="tagline miss">your opponent didn't punish it</div>`; }
  annoEl.innerHTML=h;
}
function renderMoves(){
  const g=game(); let html='';
  g.plies.forEach((p,i)=>{
    if(p.color==='white') html+=`<span class="mn">${p.moveNo}.</span>`;
    const dot = (p.mine&&p.cls&&p.cls!=='best'&&p.cls!=='good')
      ? `<span class="dot" style="background:${CLS[p.cls].c}"></span>`:'';
    html+=`<span class="mv-item${i+1===ply?' cur':''}" data-ply="${i+1}">${p.san}${dot}</span> `;
  });
  movesEl.innerHTML=html;
  movesEl.querySelectorAll('.mv-item').forEach(el=>{
    el.onclick=()=>{ ply=+el.dataset.ply; render(); };
  });
  const cur=movesEl.querySelector('.cur'); if(cur) cur.scrollIntoView({block:'nearest'});
}
function render(){
  const g=game(), pos=positions();
  const uci = ply>0 ? g.plies[ply-1].uci : null;
  renderBoard(pos[ply], uci); renderAnno(); renderMoves();
}
function renderAll(){
  const g=game();
  subEl.textContent=`${DATA.username} · ${g.white} vs ${g.black} · ${g.timeClass} · ${g.result}`;
  render();
}
function step(d){ const max=game().plies.length; ply=Math.max(0,Math.min(max,ply+d)); render(); }
document.getElementById('bStart').onclick=()=>{ply=0;render();};
document.getElementById('bEnd').onclick=()=>{ply=game().plies.length;render();};
document.getElementById('bPrev').onclick=()=>step(-1);
document.getElementById('bNext').onclick=()=>step(1);
document.addEventListener('keydown',e=>{
  if(e.key==='ArrowLeft'){step(-1);e.preventDefault();}
  if(e.key==='ArrowRight'){step(1);e.preventDefault();}
  if(e.key==='ArrowUp'){ply=0;render();e.preventDefault();}
  if(e.key==='ArrowDown'){ply=game().plies.length;render();e.preventDefault();}
});
renderAll();
</script></div></body></html>"""
