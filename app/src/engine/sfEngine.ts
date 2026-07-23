// Async controller for the WebView Stockfish. The engine (classify/tag/coach) is
// synchronous, so we warm every position through this queue into a Map first,
// then run the sync pipeline against that Map. One position at a time (Stockfish
// is a single search), FIFO, with an in-memory cache keyed by fen@depth.
import type { Evaluation } from './model';

interface Job {
  fen: string;
  depth: number;
  resolve: (e: Evaluation) => void;
  reject: (err: Error) => void;
}

class SfEngine {
  depth = 12;
  private inject: ((js: string) => void) | null = null;
  private ready = false;
  private failed: string | null = null;
  private queue: Job[] = [];
  private current: Job | null = null;
  private cache = new Map<string, Evaluation>();
  private readyWaiters: Array<() => void> = [];

  // --- wired up by the WebView host component ---
  attach(inject: (js: string) => void) {
    this.inject = inject;
  }
  reset() {
    this.ready = false;
    this.failed = null;
    this.current = null;
    this.queue = [];
    // keep the cache — positions are engine/depth-stable within a session
  }
  onReady() {
    this.ready = true;
    this.readyWaiters.splice(0).forEach((w) => w());
    this.pump();
  }
  onResult(bestmove: string | null, cp: number | null, mate: number | null) {
    if (!this.current) return;
    const ev: Evaluation = { fen: this.current.fen, depth: this.current.depth, cp, mate, bestMove: bestmove };
    this.cache.set(`${this.current.fen}@${this.current.depth}`, ev);
    this.current.resolve(ev);
    this.current = null;
    this.pump();
  }
  onError(msg: string) {
    if (this.current) {
      this.current.reject(new Error(msg));
      this.current = null;
      this.pump();
    } else if (!this.ready) {
      this.failed = msg; // init failure — fail everyone waiting
      this.queue.splice(0).forEach((j) => j.reject(new Error(msg)));
      this.readyWaiters.splice(0).forEach((w) => w());
    }
  }

  waitReady(timeoutMs = 20000): Promise<void> {
    if (this.ready) return Promise.resolve();
    if (this.failed) return Promise.reject(new Error(this.failed));
    return new Promise((resolve, reject) => {
      const t = setTimeout(() => reject(new Error('engine did not start (timeout)')), timeoutMs);
      this.readyWaiters.push(() => { clearTimeout(t); this.failed ? reject(new Error(this.failed)) : resolve(); });
    });
  }

  evaluate(fen: string, depth = this.depth): Promise<Evaluation> {
    const cached = this.cache.get(`${fen}@${depth}`);
    if (cached) return Promise.resolve(cached);
    if (this.failed) return Promise.reject(new Error(this.failed));
    return new Promise((resolve, reject) => {
      const t = setTimeout(() => reject(new Error('eval timeout')), 30000);
      this.queue.push({
        fen, depth,
        resolve: (e) => { clearTimeout(t); resolve(e); },
        reject: (err) => { clearTimeout(t); reject(err); },
      });
      this.pump();
    });
  }

  private pump() {
    if (!this.ready || this.current || !this.inject || !this.queue.length) return;
    this.current = this.queue.shift()!;
    this.inject(`window.runEval(${JSON.stringify(this.current.fen)}, ${this.current.depth}); true;`);
  }
}

export const sfEngine = new SfEngine();
