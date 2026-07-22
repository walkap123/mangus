import React, { useMemo, useState } from 'react';
import {
  SafeAreaView, ScrollView, View, Text, TextInput, Pressable,
  ActivityIndicator, StyleSheet, Dimensions, StatusBar,
} from 'react-native';
import { analyze, defaultApiBase } from './src/api';
import { Board, Slide } from './src/Board';
import { C, CLS } from './src/theme';
import type { Payload, Game } from './src/types';

const sqOf = (uci: string) => [uci.slice(0, 2), uci.slice(2, 4)];

export default function App() {
  const [screen, setScreen] = useState<'home' | 'loading' | 'games' | 'review'>('home');
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
      setScreen('games');
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
        <Home
          username={username} setUsername={setUsername}
          apiBase={apiBase} setApiBase={setApiBase}
          error={error} onRun={run}
        />
      )}
      {screen === 'loading' && (
        <View style={styles.center}>
          <ActivityIndicator color={C.accent} size="large" />
          <Text style={styles.muted}>Analyzing {username}'s games…</Text>
          <Text style={[styles.muted, { fontSize: 12 }]}>(first run is slower — Stockfish is thinking)</Text>
        </View>
      )}
      {screen === 'games' && payload && (
        <Games payload={payload} onOpen={openGame} onBack={() => setScreen('home')} />
      )}
      {screen === 'review' && payload && (
        <Review game={payload.games[gameIndex]} initialPly={initialPly} onBack={() => setScreen('games')} />
      )}
    </SafeAreaView>
  );
}

function Home({ username, setUsername, apiBase, setApiBase, error, onRun }: any) {
  return (
    <ScrollView contentContainerStyle={styles.homeWrap}>
      <Text style={styles.h1}>
        mangus <Text style={{ color: C.accent }}>review</Text>
      </Text>
      <Text style={styles.muted}>Your chess.com games, analyzed.</Text>

      <Text style={styles.label}>chess.com username</Text>
      <TextInput
        style={styles.input} value={username} onChangeText={setUsername}
        autoCapitalize="none" autoCorrect={false} placeholder="username"
        placeholderTextColor={C.muted}
      />
      <Text style={styles.label}>server</Text>
      <TextInput
        style={styles.input} value={apiBase} onChangeText={setApiBase}
        autoCapitalize="none" autoCorrect={false}
      />
      {error ? <Text style={styles.error}>{error}</Text> : null}
      <Pressable style={styles.primary} onPress={onRun}>
        <Text style={styles.primaryText}>Analyze my games</Text>
      </Pressable>
    </ScrollView>
  );
}

function Games({ payload, onOpen, onBack }: {
  payload: Payload; onOpen: (gi: number, ply: number) => void; onBack: () => void;
}) {
  const wins = payload.games.filter((g) => g.result === 'win').length;
  const losses = payload.games.filter((g) => g.result === 'loss').length;
  const draws = payload.games.length - wins - losses;
  const rc = (r: string) => (r === 'win' ? C.green : r === 'loss' ? C.red : C.muted);
  const recent = payload.games[0];
  const boardSize = Math.min(Dimensions.get('window').width - 36, 380);
  const lastPly = recent && recent.plies.length ? recent.plies[recent.plies.length - 1] : null;
  const recentFen = lastPly ? lastPly.fen : recent?.startFen;
  const recentHl: Record<string, string> = {};
  if (lastPly) {
    recentHl[lastPly.uci.slice(0, 2)] = '#f6f069';
    recentHl[lastPly.uci.slice(2, 4)] = '#f6f069';
  }

  return (
    <ScrollView contentContainerStyle={styles.wrap}>
      <Pressable onPress={onBack} hitSlop={10}><Text style={styles.back}>‹ back</Text></Pressable>
      <Text style={styles.h1}>{payload.username}</Text>
      <Text style={styles.muted}>{payload.games.length} games · {wins}W {losses}L {draws}D</Text>

      {recent && recentFen && (
        <>
          <Text style={styles.h2}>Most recent</Text>
          <Pressable onPress={() => onOpen(0, 0)}>
            <Board fen={recentFen} flip={recent.perspective === 'black'} size={boardSize} highlights={recentHl} />
            <View style={styles.recentMeta}>
              <Text style={styles.rowTitle}>{recent.timeClass} · {recent.opponent}</Text>
              <Text style={[styles.pill, { color: rc(recent.result) }]}>{recent.result} · review ›</Text>
            </View>
          </Pressable>
        </>
      )}

      <Text style={styles.h2}>Past games</Text>
      {payload.games.slice(1).map((g, i) => (
        <Pressable key={i} style={styles.row} onPress={() => onOpen(i + 1, 0)}>
          <View style={styles.rowMain}>
            <Text style={styles.rowTitle} numberOfLines={1}>{g.timeClass} · {g.opponent}</Text>
          </View>
          <Text style={[styles.pill, { color: rc(g.result) }]}>{g.result}</Text>
        </Pressable>
      ))}

      {payload.findings.length > 0 && (
        <>
          <Text style={styles.h2}>Patterns</Text>
          {payload.findings.map((f, i) => (
            <View key={i} style={styles.finding}>
              <Text style={styles.findingH}>{f.headline}</Text>
            </View>
          ))}
        </>
      )}
    </ScrollView>
  );
}

function Review({ game, initialPly, onBack }: {
  game: Game; initialPly: number; onBack: () => void;
}) {
  const [ply, setPly] = useState(initialPly);
  const [showBest, setShowBest] = useState(false);
  const [slide, setSlide] = useState<Slide>(null);
  const positions = useMemo(
    () => [game.startFen, ...game.plies.map((p) => p.fen)], [game]
  );
  const flip = game.perspective === 'black';
  const mv = ply > 0 ? game.plies[ply - 1] : null;
  const boardSize = Math.min(Dimensions.get('window').width - 56, 420);

  let boardFen = positions[ply];
  const highlights: Record<string, string> = {};
  if (showBest && mv && mv.mine && mv.bestUci) {
    boardFen = positions[ply - 1];
    const [pf, pt] = sqOf(mv.uci); highlights[pf] = C.red; highlights[pt] = C.red;
    const [bf, bt] = sqOf(mv.bestUci); highlights[bf] = C.green; highlights[bt] = C.green;
  } else if (mv) {
    const [f, t] = sqOf(mv.uci); highlights[f] = '#f6f069'; highlights[t] = '#f6f069';
    if (mv.tagSquare) highlights[mv.tagSquare] = C.red;
  }
  const ev = game.posEvals ? game.posEvals[ply] : null;
  const len = game.plies.length;
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
      <Pressable onPress={onBack}><Text style={styles.back}>‹ games</Text></Pressable>
      <Text style={styles.muted}>vs {game.opponent} · {game.timeClass} · {game.result}</Text>

      <View style={styles.boardRow}>
        {ev != null && (
          <View style={[styles.evalBar, { height: boardSize }]}>
            <View style={[styles.evalFill, { height: `${ev}%` }]} />
            <Text style={styles.evalNum}>{ev}%</Text>
          </View>
        )}
        <Board fen={boardFen} flip={flip} size={boardSize} highlights={highlights}
          slide={showBest ? null : slide} />
      </View>

      <View style={styles.controls}>
        {[['⏮', () => go(0, null)], ['◀', () => step(-1)],
          ['▶', () => step(1)], ['⏭', () => go(len, null)],
        ].map(([label, fn]: any, i) => (
          <Pressable key={i} style={styles.ctrl} onPress={fn}>
            <Text style={styles.ctrlText}>{label}</Text>
          </Pressable>
        ))}
      </View>

      <View style={styles.anno}>
        {!mv ? (
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
            {showBest && mv.mine && mv.bestUci ? (
              <Text style={styles.bestInfo}>
                <Text style={{ color: C.red }}>You played {mv.san}</Text> — best was{' '}
                <Text style={{ color: C.green, fontWeight: '700' }}>{mv.bestSan}</Text>
              </Text>
            ) : null}
            {mv.mine && mv.bestUci && mv.cls !== 'best' && mv.cls !== 'good' ? (
              <Pressable style={styles.bestBtn} onPress={() => { setSlide(null); setShowBest((s) => !s); }}>
                <Text style={styles.bestBtnText}>
                  {showBest ? '↩ back to the game' : 'What should I have played?'}
                </Text>
              </Pressable>
            ) : null}
          </>
        )}
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
  center: { flex: 1, alignItems: 'center', justifyContent: 'center', gap: 8 },
  wrap: { padding: 18, paddingBottom: 60 },
  homeWrap: { padding: 24, paddingTop: 80, gap: 8 },
  h1: { color: C.fg, fontSize: 26, fontWeight: '800' },
  h2: { color: C.fg, fontSize: 15, fontWeight: '700', marginTop: 18, marginBottom: 4 },
  muted: { color: C.muted, fontSize: 13 },
  label: { color: C.muted, fontSize: 12, marginTop: 16, marginBottom: 4 },
  input: {
    backgroundColor: C.card, color: C.fg, borderWidth: 1, borderColor: C.line,
    borderRadius: 10, padding: 12, fontSize: 16,
  },
  error: { color: C.red, marginTop: 12 },
  primary: { backgroundColor: C.accent, borderRadius: 12, padding: 15, marginTop: 24, alignItems: 'center' },
  primaryText: { color: '#111', fontWeight: '800', fontSize: 16 },
  back: { color: C.accent, fontSize: 15, marginBottom: 8 },
  boardRow: { flexDirection: 'row', gap: 8, marginTop: 12, alignItems: 'flex-start' },
  evalBar: { width: 18, backgroundColor: '#111', borderRadius: 5, overflow: 'hidden', justifyContent: 'flex-end' },
  evalFill: { backgroundColor: '#e8e8ea', width: '100%' },
  evalNum: { position: 'absolute', bottom: 2, left: 0, right: 0, textAlign: 'center', fontSize: 8, color: '#111', fontWeight: '700' },
  controls: { flexDirection: 'row', gap: 8, marginTop: 12 },
  ctrl: { flex: 1, backgroundColor: C.card, borderWidth: 1, borderColor: C.line, borderRadius: 10, paddingVertical: 12, alignItems: 'center' },
  ctrlText: { color: C.fg, fontSize: 18 },
  anno: { backgroundColor: C.card, borderWidth: 1, borderColor: C.line, borderRadius: 12, padding: 14, marginTop: 14, minHeight: 96 },
  annoTop: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  annoMove: { color: C.fg, fontSize: 18, fontWeight: '700' },
  badge: { borderRadius: 6, paddingHorizontal: 8, paddingVertical: 2 },
  badgeText: { color: '#111', fontWeight: '800', fontSize: 12 },
  tag: { color: C.red, fontWeight: '700', marginTop: 6 },
  bestInfo: { color: C.fg, marginTop: 8 },
  bestBtn: { backgroundColor: C.green, borderRadius: 8, paddingVertical: 10, alignItems: 'center', marginTop: 12 },
  bestBtnText: { color: '#062', fontWeight: '800' },
  moveList: { flexDirection: 'row', flexWrap: 'wrap', marginTop: 16, gap: 2 },
  moveItem: { color: C.fg, fontSize: 14, paddingHorizontal: 4, paddingVertical: 2 },
  moveCur: { backgroundColor: C.accent, color: '#111', borderRadius: 4, fontWeight: '700', overflow: 'hidden' },
  row: { flexDirection: 'row', alignItems: 'center', backgroundColor: C.card,
         borderRadius: 10, paddingVertical: 9, paddingHorizontal: 12, marginTop: 6 },
  rowMain: { flex: 1 },
  rowTitle: { color: C.fg, fontSize: 14, fontWeight: '600' },
  rowSub: { color: C.muted, fontSize: 12, marginTop: 1 },
  chev: { color: C.muted, fontSize: 20, marginLeft: 8 },
  pill: { fontWeight: '700', fontSize: 13, marginLeft: 8 },
  recentMeta: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginTop: 8, marginBottom: 4 },
  finding: { borderLeftWidth: 3, borderLeftColor: C.accent, paddingLeft: 10, paddingVertical: 2, marginTop: 8 },
  findingH: { color: C.fg, fontWeight: '600', fontSize: 14 },
});
