import React, { useMemo, useState } from 'react';
import {
  SafeAreaView, ScrollView, View, Text, TextInput, Pressable,
  ActivityIndicator, StyleSheet, Dimensions, StatusBar,
} from 'react-native';
import { analyze, defaultApiBase } from './src/api';
import { Board, Slide } from './src/Board';
import { C, CLS, accColor, resultColor } from './src/theme';
import type { Payload, Game, Finding } from './src/types';

const sqOf = (uci: string) => [uci.slice(0, 2), uci.slice(2, 4)];

// ---- small shared UI ----
function Bubble({ value, label, color = C.accent }: { value: string; label?: string; color?: string }) {
  return (
    <View style={[styles.bubble, { backgroundColor: color + '22', borderColor: color + '55' }]}>
      <Text style={[styles.bubbleVal, { color }]}>{value}</Text>
      {label ? <Text style={styles.bubbleLabel}>{label}</Text> : null}
    </View>
  );
}

function GameStats({ g, size = 'md' }: { g: Game; size?: 'sm' | 'md' }) {
  if (g.accuracy == null) return null;
  return (
    <View style={styles.bubbleRow}>
      <Bubble value={`${g.accuracy}%`} label={size === 'md' ? 'accuracy' : undefined} color={accColor(g.accuracy)} />
      {g.elo != null && <Bubble value={`~${g.elo}`} label={size === 'md' ? 'played like' : undefined} color={C.accent} />}
    </View>
  );
}

export default function App() {
  const [screen, setScreen] = useState<'home' | 'loading' | 'main' | 'review'>('home');
  const [tab, setTab] = useState<'games' | 'patterns'>('games');
  const [username, setUsername] = useState('mastapate');
  const [apiBase, setApiBase] = useState(defaultApiBase());
  const [payload, setPayload] = useState<Payload | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [gameIndex, setGameIndex] = useState(0);
  const [initialPly, setInitialPly] = useState(0);

  async function run() {
    setError(null);
    setScreen('loading');
    try {
      const p = await analyze(username.trim(), apiBase.trim());
      setPayload(p);
      setTab('games');
      setScreen('main');
    } catch (e: any) {
      setError(e.message || 'Could not reach the server.');
      setScreen('home');
    }
  }

  function openGame(gi: number, ply: number) {
    setGameIndex(gi);
    setInitialPly(ply);
    setScreen('review');
  }

  return (
    <SafeAreaView style={styles.app}>
      <StatusBar barStyle="light-content" />
      {screen === 'home' && (
        <Home username={username} setUsername={setUsername} apiBase={apiBase}
          setApiBase={setApiBase} error={error} onRun={run} />
      )}
      {screen === 'loading' && (
        <View style={styles.center}>
          <ActivityIndicator color={C.accent} size="large" />
          <Text style={[styles.muted, { marginTop: 14 }]}>Analyzing {username}'s games…</Text>
          <Text style={[styles.muted, { fontSize: 12 }]}>first run is slower — Stockfish is thinking</Text>
        </View>
      )}
      {screen === 'main' && payload && (
        <View style={{ flex: 1 }}>
          <View style={styles.topBar}>
            <View style={{ flex: 1 }}>
              <Text style={styles.topUser}>{payload.username}</Text>
              <Record payload={payload} />
            </View>
            <Pressable onPress={() => setScreen('home')} hitSlop={10}>
              <Text style={styles.back}>change</Text>
            </Pressable>
          </View>
          {tab === 'games'
            ? <GamesTab payload={payload} onOpen={openGame} />
            : <PatternsTab payload={payload} onOpen={openGame} />}
          <TabBar tab={tab} setTab={setTab} />
        </View>
      )}
      {screen === 'review' && payload && (
        <Review game={payload.games[gameIndex]} initialPly={initialPly} onBack={() => setScreen('main')} />
      )}
    </SafeAreaView>
  );
}

function Record({ payload }: { payload: Payload }) {
  const wins = payload.games.filter((g) => g.result === 'win').length;
  const losses = payload.games.filter((g) => g.result === 'loss').length;
  const draws = payload.games.length - wins - losses;
  return (
    <View style={styles.recordRow}>
      <Text style={[styles.record, { color: C.green }]}>{wins}W</Text>
      <Text style={[styles.record, { color: C.red }]}>{losses}L</Text>
      <Text style={[styles.record, { color: C.muted }]}>{draws}D</Text>
      <Text style={[styles.muted, { marginLeft: 4 }]}>· {payload.games.length} games</Text>
    </View>
  );
}

function TabBar({ tab, setTab }: { tab: 'games' | 'patterns'; setTab: (t: 'games' | 'patterns') => void }) {
  const items: [typeof tab, string][] = [['games', '♟  Games'], ['patterns', '◔  Patterns']];
  return (
    <View style={styles.tabBar}>
      {items.map(([t, label]) => (
        <Pressable key={t} style={styles.tabBtn} onPress={() => setTab(t)}>
          <Text style={[styles.tabLabel, tab === t && styles.tabActive]}>{label}</Text>
        </Pressable>
      ))}
    </View>
  );
}

function Home({ username, setUsername, apiBase, setApiBase, error, onRun }: any) {
  return (
    <ScrollView contentContainerStyle={styles.homeWrap}>
      <Text style={styles.brand}>♞ mangus</Text>
      <Text style={[styles.muted, { marginBottom: 28 }]}>Your chess.com games, coached.</Text>

      <View style={styles.card}>
        <Text style={styles.label}>chess.com username</Text>
        <TextInput style={styles.input} value={username} onChangeText={setUsername}
          autoCapitalize="none" autoCorrect={false} placeholder="username" placeholderTextColor={C.muted} />
        <Text style={[styles.label, { marginTop: 14 }]}>server</Text>
        <TextInput style={styles.input} value={apiBase} onChangeText={setApiBase}
          autoCapitalize="none" autoCorrect={false} />
        {error ? <Text style={styles.error}>{error}</Text> : null}
        <Pressable style={styles.primary} onPress={onRun}>
          <Text style={styles.primaryText}>Analyze my games</Text>
        </Pressable>
      </View>
    </ScrollView>
  );
}

function GamesTab({ payload, onOpen }: {
  payload: Payload; onOpen: (gi: number, ply: number) => void;
}) {
  const recent = payload.games[0];
  const boardSize = Math.min(Dimensions.get('window').width - 32, 400);
  const lastPly = recent && recent.plies.length ? recent.plies[recent.plies.length - 1] : null;
  const recentFen = lastPly ? lastPly.fen : recent?.startFen;
  const recentHl: Record<string, string> = {};
  if (lastPly) {
    recentHl[lastPly.uci.slice(0, 2)] = '#f6f069';
    recentHl[lastPly.uci.slice(2, 4)] = '#f6f069';
  }

  return (
    <ScrollView style={{ flex: 1 }} contentContainerStyle={styles.wrap}>
      {recent && recentFen && (
        <>
          <Text style={styles.h2}>Most recent</Text>
          <Pressable onPress={() => onOpen(0, 0)} style={styles.recentCard}>
            <Board fen={recentFen} flip={recent.perspective === 'black'} size={boardSize} highlights={recentHl} />
            <View style={styles.recentFooter}>
              <View style={{ flex: 1 }}>
                <Text style={styles.cardTitle}>{recent.timeClass} · {recent.opponent}</Text>
                <Text style={[styles.resultText, { color: resultColor(recent.result) }]}>{recent.result.toUpperCase()}</Text>
              </View>
              <GameStats g={recent} />
            </View>
          </Pressable>
        </>
      )}

      <Text style={styles.h2}>Past games</Text>
      {payload.games.slice(1).map((g, i) => (
        <Pressable key={i} style={styles.gameRow} onPress={() => onOpen(i + 1, 0)}>
          <View style={{ flex: 1 }}>
            <Text style={styles.rowTitle} numberOfLines={1}>{g.timeClass} · {g.opponent}</Text>
            <GameStats g={g} size="sm" />
          </View>
          <View style={[styles.dot, { backgroundColor: resultColor(g.result) }]} />
        </Pressable>
      ))}
    </ScrollView>
  );
}

function PatternsTab({ payload, onOpen }: {
  payload: Payload; onOpen: (gi: number, ply: number) => void;
}) {
  const [selected, setSelected] = useState<Finding | null>(null);

  if (selected) {
    return (
      <ScrollView style={{ flex: 1 }} contentContainerStyle={styles.wrap}>
        <Pressable onPress={() => setSelected(null)} hitSlop={12}><Text style={styles.back}>‹ patterns</Text></Pressable>
        <Text style={styles.insightHead}>{selected.headline}</Text>
        {selected.detail ? <Text style={styles.patternDetail}>{selected.detail}</Text> : null}
        <Text style={styles.h2}>From your games</Text>
        {selected.examples.length ? selected.examples.map((e, i) => (
          <Pressable key={i} style={styles.gameRow} disabled={e.gameIndex == null}
            onPress={() => e.gameIndex != null && onOpen(e.gameIndex, e.ply ?? 0)}>
            <View style={{ flex: 1 }}>
              <Text style={styles.rowTitle} numberOfLines={2}>{e.detail}</Text>
              {e.result ? (
                <Text style={[styles.rowSub, { color: resultColor(e.result) }]}>{e.result}</Text>
              ) : null}
            </View>
            {e.gameIndex != null ? <Text style={styles.chev}>›</Text> : null}
          </Pressable>
        )) : <Text style={[styles.muted, { marginTop: 6 }]}>No move-by-move examples for this one.</Text>}
      </ScrollView>
    );
  }

  return (
    <ScrollView style={{ flex: 1 }} contentContainerStyle={styles.wrap}>
      <Text style={styles.h2}>Your patterns</Text>
      {payload.findings.length ? payload.findings.map((f, i) => {
        const hasEx = f.examples && f.examples.length > 0;
        return (
          <Pressable key={i} style={styles.patternCard} disabled={!hasEx} onPress={() => hasEx && setSelected(f)}>
            <View style={{ flexDirection: 'row', alignItems: 'center' }}>
              <Text style={[styles.findingH, { flex: 1 }]}>{f.headline}</Text>
              {hasEx ? <Text style={styles.chev}>›</Text> : null}
            </View>
            {f.detail ? <Text style={styles.patternDetail} numberOfLines={2}>{f.detail}</Text> : null}
            {hasEx ? (
              <Text style={styles.exHint}>{f.examples.length} example{f.examples.length > 1 ? 's' : ''} · tap to see</Text>
            ) : null}
          </Pressable>
        );
      }) : <Text style={[styles.muted, { marginTop: 6 }]}>No recurring patterns found in this batch.</Text>}
    </ScrollView>
  );
}

function Review({ game, initialPly, onBack }: {
  game: Game; initialPly: number; onBack: () => void;
}) {
  const [ply, setPly] = useState(initialPly);
  const [showBest, setShowBest] = useState(false);
  const [slide, setSlide] = useState<Slide>(null);
  const positions = useMemo(() => [game.startFen, ...game.plies.map((p) => p.fen)], [game]);
  const flip = game.perspective === 'black';
  const mv = ply > 0 ? game.plies[ply - 1] : null;
  const boardSize = Math.min(Dimensions.get('window').width - 56, 420);

  const len = game.plies.length;
  const bestAt = game.bestMoves ? game.bestMoves[ply] : null;      // best move HERE
  const nextMove = ply < len ? game.plies[ply] : null;            // move played from here
  const showComparison = showBest && !!bestAt && !!nextMove && nextMove.mine
    && !!nextMove.cls && nextMove.cls !== 'best' && nextMove.cls !== 'good';

  const boardFen = positions[ply];
  const highlights: Record<string, string> = {};
  if (showBest && bestAt) {
    const [bf, bt] = sqOf(bestAt.uci); highlights[bf] = C.green; highlights[bt] = C.green;
    if (showComparison && nextMove) {
      const [pf, pt] = sqOf(nextMove.uci); highlights[pf] = C.red; highlights[pt] = C.red;
    }
  } else if (mv) {
    const [f, t] = sqOf(mv.uci); highlights[f] = '#f6f069'; highlights[t] = '#f6f069';
    if (mv.tagSquare) highlights[mv.tagSquare] = C.red;
  }
  const ev = game.posEvals ? game.posEvals[ply] : null;
  const go = (target: number, sl: Slide) => {
    if (target < 0 || target > len) return;
    setShowBest(false); setSlide(sl); setPly(target);
  };
  const step = (d: number) => {
    let sl: Slide = null;
    if (d === 1 && ply < len) { const u = game.plies[ply].uci; sl = { from: u.slice(0, 2), to: u.slice(2, 4) }; }
    else if (d === -1 && ply > 0) { const u = game.plies[ply - 1].uci; sl = { from: u.slice(2, 4), to: u.slice(0, 2) }; }
    go(ply + d, sl);
  };

  return (
    <ScrollView contentContainerStyle={styles.wrap}>
      <Pressable onPress={onBack} hitSlop={12}><Text style={styles.back}>‹ games</Text></Pressable>
      <View style={styles.reviewHead}>
        <View style={{ flex: 1 }}>
          <Text style={styles.cardTitle}>vs {game.opponent}</Text>
          <Text style={styles.muted}>{game.timeClass} · <Text style={{ color: resultColor(game.result) }}>{game.result}</Text></Text>
        </View>
        <GameStats g={game} size="sm" />
      </View>

      <View style={styles.boardRow}>
        {ev != null && (
          <View style={[styles.evalBar, { height: boardSize }]}>
            <View style={[styles.evalFill, { height: `${ev}%` }]} />
            <Text style={styles.evalNum}>{ev}%</Text>
          </View>
        )}
        <Board fen={boardFen} flip={flip} size={boardSize} highlights={highlights} slide={showBest ? null : slide} />
      </View>

      <View style={styles.controls}>
        {[['⏮', () => go(0, null)], ['◀', () => step(-1)], ['▶', () => step(1)], ['⏭', () => go(len, null)]]
          .map(([label, fn]: any, i) => (
            <Pressable key={i} style={styles.ctrl} onPress={fn}>
              <Text style={styles.ctrlText}>{label}</Text>
            </Pressable>
          ))}
      </View>

      <View style={styles.anno}>
        {showBest && bestAt ? (
          <>
            <Text style={styles.annoMove}>Best move: <Text style={{ color: C.green }}>{bestAt.san}</Text></Text>
            {showComparison && nextMove && nextMove.cls ? (
              <Text style={styles.tag}>you played {nextMove.san} · {CLS[nextMove.cls].l}</Text>
            ) : (
              <Text style={styles.muted}>the engine's top move in this position</Text>
            )}
          </>
        ) : !mv ? (
          <Text style={styles.annoMove}>Starting position — you are {game.perspective}</Text>
        ) : (
          <>
            <View style={styles.annoTop}>
              <Text style={styles.annoMove}>{mv.moveNo}.{mv.color === 'white' ? '' : '..'} {mv.san}</Text>
              {mv.mine && mv.cls ? (
                <View style={[styles.badge, { backgroundColor: CLS[mv.cls].c }]}>
                  <Text style={styles.badgeText}>{CLS[mv.cls].l}</Text>
                </View>
              ) : null}
            </View>
            {mv.mine && mv.winB != null ? (
              <Text style={styles.muted}>your win chance {mv.winB}% → {mv.winA}%</Text>
            ) : null}
            {mv.tag ? <Text style={styles.tag}>{mv.tag}</Text> : null}
          </>
        )}
        {bestAt ? (
          <Pressable style={[styles.bestBtn, showBest ? styles.bestBtnAlt : null]}
            onPress={() => { setSlide(null); setShowBest((s) => !s); }}>
            <Text style={[styles.bestBtnText, showBest ? { color: C.fg } : null]}>
              {showBest ? '↩ back to the game' : '💡 Show best move'}
            </Text>
          </Pressable>
        ) : null}
      </View>

      <View style={styles.moveList}>
        {game.plies.map((p, i) => (
          <Pressable key={i} onPress={() => go(i + 1, null)}>
            <Text style={[styles.moveItem, i + 1 === ply ? styles.moveCur : null]}>
              {p.color === 'white' ? `${p.moveNo}. ` : ''}{p.san}
              {p.mine && p.cls && p.cls !== 'best' && p.cls !== 'good'
                ? <Text style={{ color: CLS[p.cls].c }}> ●</Text> : null}
            </Text>
          </Pressable>
        ))}
      </View>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  app: { flex: 1, backgroundColor: C.bg },
  center: { flex: 1, alignItems: 'center', justifyContent: 'center' },
  wrap: { padding: 16, paddingBottom: 60 },
  homeWrap: { padding: 24, paddingTop: 90, flexGrow: 1 },
  brand: { color: C.fg, fontSize: 34, fontWeight: '900', letterSpacing: -0.5 },
  h1: { color: C.fg, fontSize: 26, fontWeight: '800', marginTop: 4 },
  h2: { color: C.muted, fontSize: 12, fontWeight: '700', letterSpacing: 0.6, textTransform: 'uppercase', marginTop: 22, marginBottom: 8 },
  muted: { color: C.muted, fontSize: 13 },
  label: { color: C.muted, fontSize: 12, fontWeight: '600', marginBottom: 6 },
  recordRow: { flexDirection: 'row', alignItems: 'center', gap: 10, marginTop: 4 },
  record: { fontSize: 15, fontWeight: '800' },

  card: { backgroundColor: C.card, borderRadius: 16, borderWidth: 1, borderColor: C.line, padding: 18 },
  input: { backgroundColor: C.bg, color: C.fg, borderWidth: 1, borderColor: C.line, borderRadius: 12, padding: 13, fontSize: 16 },
  error: { color: C.red, marginTop: 12 },
  primary: { backgroundColor: C.accent, borderRadius: 14, padding: 15, marginTop: 22, alignItems: 'center' },
  primaryText: { color: '#111', fontWeight: '800', fontSize: 16 },
  back: { color: C.accent, fontSize: 15, marginBottom: 6 },

  bubble: { flexDirection: 'row', alignItems: 'center', gap: 5, borderRadius: 20, borderWidth: 1, paddingHorizontal: 11, paddingVertical: 5 },
  bubbleVal: { fontWeight: '800', fontSize: 14 },
  bubbleLabel: { color: C.muted, fontSize: 11, fontWeight: '600' },
  bubbleRow: { flexDirection: 'row', gap: 6, alignItems: 'center', flexWrap: 'wrap', justifyContent: 'flex-end' },

  recentCard: {},
  recentFooter: { flexDirection: 'row', alignItems: 'center', marginTop: 12, gap: 8 },
  cardTitle: { color: C.fg, fontSize: 16, fontWeight: '700' },
  resultText: { fontSize: 12, fontWeight: '800', letterSpacing: 1, marginTop: 2 },

  gameRow: { flexDirection: 'row', alignItems: 'center', backgroundColor: C.card, borderRadius: 12, padding: 12, marginTop: 8, gap: 10 },
  rowTitle: { color: C.fg, fontSize: 15, fontWeight: '600', marginBottom: 4 },
  rowSub: { color: C.muted, fontSize: 12 },
  chev: { color: C.muted, fontSize: 22, marginLeft: 4 },
  dot: { width: 10, height: 10, borderRadius: 5 },

  findingH: { color: C.fg, fontWeight: '600', fontSize: 14 },
  patternCard: { backgroundColor: C.card, borderRadius: 12, padding: 14, marginTop: 8 },
  patternDetail: { color: C.muted, fontSize: 13, marginTop: 5, lineHeight: 19 },
  insightHead: { color: C.fg, fontSize: 19, fontWeight: '800', marginTop: 4, marginBottom: 6, lineHeight: 25 },
  exHint: { color: C.accent, fontSize: 12, fontWeight: '700', marginTop: 10 },

  topBar: { flexDirection: 'row', alignItems: 'center', paddingHorizontal: 16, paddingTop: 6, paddingBottom: 10, borderBottomWidth: 1, borderBottomColor: C.line },
  topUser: { color: C.fg, fontSize: 20, fontWeight: '800' },
  tabBar: { flexDirection: 'row', borderTopWidth: 1, borderTopColor: C.line, backgroundColor: C.card },
  tabBtn: { flex: 1, alignItems: 'center', paddingVertical: 14 },
  tabLabel: { color: C.muted, fontSize: 13, fontWeight: '700' },
  tabActive: { color: C.accent },

  reviewHead: { flexDirection: 'row', alignItems: 'center', gap: 8, marginBottom: 6 },
  boardRow: { flexDirection: 'row', gap: 8, marginTop: 8, alignItems: 'flex-start' },
  evalBar: { width: 18, backgroundColor: '#111', borderRadius: 5, overflow: 'hidden', justifyContent: 'flex-end' },
  evalFill: { backgroundColor: '#e8e8ea', width: '100%' },
  evalNum: { position: 'absolute', bottom: 2, left: 0, right: 0, textAlign: 'center', fontSize: 8, color: '#111', fontWeight: '700' },
  controls: { flexDirection: 'row', gap: 8, marginTop: 12 },
  ctrl: { flex: 1, backgroundColor: C.card, borderWidth: 1, borderColor: C.line, borderRadius: 12, paddingVertical: 13, alignItems: 'center' },
  ctrlText: { color: C.fg, fontSize: 18 },
  anno: { backgroundColor: C.card, borderWidth: 1, borderColor: C.line, borderRadius: 14, padding: 15, marginTop: 14, minHeight: 96 },
  annoTop: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  annoMove: { color: C.fg, fontSize: 18, fontWeight: '700' },
  badge: { borderRadius: 7, paddingHorizontal: 9, paddingVertical: 3 },
  badgeText: { color: '#111', fontWeight: '800', fontSize: 12 },
  tag: { color: C.red, fontWeight: '700', marginTop: 6 },
  bestInfo: { color: C.fg, marginTop: 8 },
  bestBtn: { backgroundColor: C.green, borderRadius: 10, paddingVertical: 11, alignItems: 'center', marginTop: 12 },
  bestBtnAlt: { backgroundColor: C.card, borderWidth: 1, borderColor: C.line },
  bestBtnText: { color: '#062', fontWeight: '800' },
  moveList: { flexDirection: 'row', flexWrap: 'wrap', marginTop: 16, gap: 2 },
  moveItem: { color: C.fg, fontSize: 14, paddingHorizontal: 4, paddingVertical: 2 },
  moveCur: { backgroundColor: C.accent, color: '#111', borderRadius: 4, fontWeight: '700', overflow: 'hidden' },
});
