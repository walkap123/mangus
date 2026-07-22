import Constants from 'expo-constants';
import type { Payload } from './types';

// The API runs on the same machine as the Metro dev server, port 8000. Expo
// exposes that machine's LAN host, so we can auto-derive the URL — no typing IPs.
export function defaultApiBase(): string {
  const hostUri: string | undefined =
    (Constants as any).expoConfig?.hostUri ||
    (Constants as any).manifest2?.extra?.expoGo?.debuggerHost ||
    (Constants as any).manifest?.debuggerHost;
  const host = hostUri ? hostUri.split(':')[0] : 'localhost';
  return `http://${host}:8000`;
}

export async function analyze(
  username: string,
  base: string,
  opts: { max?: number; depth?: number } = {}
): Promise<Payload> {
  const { max = 20, depth = 12 } = opts;
  const url = `${base}/analyze?username=${encodeURIComponent(username)}&max=${max}&depth=${depth}`;
  const res = await fetch(url);
  if (!res.ok) {
    let detail = `HTTP ${res.status}`;
    try {
      detail = (await res.json()).detail || detail;
    } catch {}
    throw new Error(detail);
  }
  return res.json();
}
