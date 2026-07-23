import React, { useRef, useState } from 'react';
import { View, Text, Pressable, StyleSheet, ScrollView } from 'react-native';
import { WebView } from 'react-native-webview';
import { C } from './theme';
import { SF_HTML } from './engine/sfInline'; // engine inlined — no network/hosting

// A real middlegame position (Italian) so the engine has to actually think.
const TEST_FEN = 'r1bqk2r/pppp1ppp/2n2n2/2b1p3/2B1P3/2NP1N2/PPP2PPP/R1BQK2R w KQkq - 0 6';

export function EngineTest({ onBack }: { onBack: () => void }) {
  const ref = useRef<WebView>(null);
  const [status, setStatus] = useState('loading engine…');
  const [rows, setRows] = useState<string[]>([]);
  const pending = useRef<number | null>(null);

  const onMessage = (e: any) => {
    let m: any = {};
    try { m = JSON.parse(e.nativeEvent.data); } catch { return; }
    if (m.type === 'ready') setStatus('✓ engine ready — pick a depth');
    else if (m.type === 'error') setStatus('✗ ' + m.msg);
    else if (m.type === 'result') {
      const sc = m.scoreType === 'mate' ? `mate ${m.score}` : `${(m.score / 100).toFixed(2)}`;
      setRows((r) => [`depth ${pending.current}:  best ${m.bestmove}  ·  ${m.ms} ms  ·  eval ${sc}`, ...r]);
      setStatus('✓ done');
    } else if (m.type === 'watchdog') {
      setRows((r) => [`⏱ still thinking after ${m.ms} ms (engine emitted ${m.lines} lines total)`, ...r]);
    }
  };

  const run = (depth: number) => {
    pending.current = depth;
    setStatus(`thinking… depth ${depth}`);
    ref.current?.injectJavaScript(`window.runEval(${JSON.stringify(TEST_FEN)}, ${depth}); true;`);
  };

  return (
    <View style={{ flex: 1, backgroundColor: C.bg }}>
      <ScrollView contentContainerStyle={{ padding: 18, paddingTop: 40 }}>
        <Pressable onPress={onBack}><Text style={{ color: C.accent, marginBottom: 10 }}>‹ back</Text></Pressable>
        <Text style={{ color: C.fg, fontSize: 22, fontWeight: '800' }}>On-device engine test</Text>
        <Text style={{ color: C.muted, marginTop: 4 }}>Stockfish (WASM) running inside the app — no server.</Text>
        <Text style={{ color: C.fg, marginTop: 18, fontWeight: '700', fontSize: 16 }}>{status}</Text>
        <View style={{ flexDirection: 'row', gap: 8, marginTop: 16 }}>
          {[10, 14, 18].map((d) => (
            <Pressable key={d} onPress={() => run(d)} style={styles.btn}>
              <Text style={styles.btnText}>depth {d}</Text>
            </Pressable>
          ))}
        </View>
        <Text style={{ color: C.muted, fontSize: 12, marginTop: 8 }}>
          The key numbers: does it run, and how many ms per position?
        </Text>
        {rows.map((r, i) => <Text key={i} style={styles.row}>{r}</Text>)}

        <Text style={{ color: C.muted, fontSize: 13, marginTop: 20 }}>
          ↓ read-only engine output (don't tap in it — tap the depth buttons above):
        </Text>
        <View style={{ height: 320, borderWidth: 1, borderColor: C.line, borderRadius: 8, marginTop: 6, overflow: 'hidden' }}>
          <WebView
            ref={ref}
            source={{ html: SF_HTML }}
            originWhitelist={['*']}
            javaScriptEnabled
            onMessage={onMessage}
            onError={(e) => setStatus('✗ webview: ' + e.nativeEvent.description)}
            style={{ flex: 1, backgroundColor: '#1a1a1c' }}
          />
        </View>
      </ScrollView>
    </View>
  );
}

const styles = StyleSheet.create({
  btn: { backgroundColor: C.card, borderWidth: 1, borderColor: C.line, borderRadius: 10, paddingVertical: 12, paddingHorizontal: 16 },
  btnText: { color: C.fg, fontWeight: '700' },
  row: { color: C.fg, marginTop: 12, fontSize: 14 },
});
