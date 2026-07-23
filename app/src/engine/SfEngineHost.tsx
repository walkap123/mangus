import React, { useEffect, useRef } from 'react';
import { WebView } from 'react-native-webview';
import { sfEngine } from './sfEngine';
import { SF_HTML } from './sfInline';

// Hosts the inlined-Stockfish WebView and bridges it to sfEngine. Must be
// rendered visibly (non-zero size/opacity) while analyzing, or iOS throttles it.
export function SfEngineHost({ style }: { style?: any }) {
  const ref = useRef<WebView>(null);
  useEffect(() => {
    sfEngine.attach((js) => ref.current?.injectJavaScript(js));
    return () => sfEngine.reset();
  }, []);

  const onMessage = (e: any) => {
    let m: any;
    try { m = JSON.parse(e.nativeEvent.data); } catch { return; }
    if (m.type === 'ready') sfEngine.onReady();
    else if (m.type === 'result') {
      const best = m.bestmove && m.bestmove !== '(none)' ? m.bestmove : null;
      sfEngine.onResult(best, m.scoreType === 'cp' ? m.score : null, m.scoreType === 'mate' ? m.score : null);
    } else if (m.type === 'error') sfEngine.onError(m.msg);
  };

  return (
    <WebView
      ref={ref}
      source={{ html: SF_HTML }}
      originWhitelist={['*']}
      javaScriptEnabled
      onMessage={onMessage}
      onError={(e) => sfEngine.onError('webview: ' + e.nativeEvent.description)}
      style={style}
    />
  );
}
