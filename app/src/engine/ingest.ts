// chess.com ingestion — TS port of chess_coach/ingest.py (uses chess.js).
import { Chess } from 'chess.js';
import type { Color, Game, Player, Ply } from './model';

const API_BASE = 'https://api.chess.com';
export const DEFAULT_UA = 'mangus/0.1 (https://github.com/walkap123/mangus; contact@example.com)';

export class PlayerNotFound extends Error {}
export class ChessComError extends Error {}

function parseClk(comment: string): number | null {
  const m = comment.match(/\[%clk (\d+):(\d+):(\d+(?:\.\d+)?)\]/);
  if (!m) return null;
  return parseInt(m[1], 10) * 3600 + parseInt(m[2], 10) * 60 + parseFloat(m[3]);
}

export function parseMoves(pgn: string): Ply[] {
  const chess = new Chess();
  try {
    chess.loadPgn(pgn);
  } catch {
    return [];
  }
  const clkByFen = new Map<string, number | null>();
  for (const c of chess.getComments()) clkByFen.set(c.fen, parseClk(c.comment));

  const plies: Ply[] = [];
  let plyNo = 0;
  for (const mv of chess.history({ verbose: true })) {
    plyNo++;
    plies.push({
      plyNumber: plyNo,
      moveNumber: parseInt(mv.before.split(' ')[5], 10), // fullmove no. before the move
      color: mv.color === 'w' ? 'white' : 'black',
      san: mv.san,
      uci: mv.lan,
      fenBefore: mv.before,
      fenAfter: mv.after,
      clockSeconds: clkByFen.get(mv.after) ?? null,
    });
  }
  return plies;
}

function playerFromRaw(side: any): Player {
  return {
    username: (side.username || '').toLowerCase(),
    rating: side.rating ?? null,
    resultRaw: side.result ?? null,
  };
}

export function parseGame(raw: any, perspectiveUsername: string): Game | null {
  const pgn = raw.pgn;
  if (!pgn) return null;
  const white = playerFromRaw(raw.white || {});
  const black = playerFromRaw(raw.black || {});
  const pu = perspectiveUsername.toLowerCase();
  const perspective: Color = pu === white.username ? 'white' : pu === black.username ? 'black' : 'white';
  return {
    gameId: raw.uuid || raw.url || '',
    url: raw.url || '',
    playedAt: raw.end_time ?? null,
    timeClass: raw.time_class || '',
    timeControl: raw.time_control || '',
    rated: !!raw.rated,
    rules: raw.rules || 'chess',
    eco: raw.eco ?? null,
    white,
    black,
    perspective,
    moves: parseMoves(pgn),
    pgn,
  };
}

export interface IterOpts {
  rules?: Set<string> | null;
  timeClasses?: Set<string> | null;
  ratedOnly?: boolean;
  maxGames?: number | null;
  newestFirst?: boolean;
}

export class ChessComClient {
  constructor(private userAgent: string = DEFAULT_UA, private maxRetries = 4) {}

  private async get(url: string): Promise<Response> {
    let backoff = 1000;
    for (let attempt = 0; attempt <= this.maxRetries; attempt++) {
      const resp = await fetch(url, {
        headers: { 'User-Agent': this.userAgent, Accept: 'application/json' },
      });
      if (resp.status === 200) return resp;
      if (resp.status === 404) throw new PlayerNotFound(`404 Not Found: ${url}`);
      if ((resp.status === 429 || resp.status >= 500) && attempt < this.maxRetries) {
        const ra = parseFloat(resp.headers.get('Retry-After') || '') * 1000;
        await new Promise((r) => setTimeout(r, Number.isFinite(ra) && ra > 0 ? ra : backoff));
        backoff = Math.min(backoff * 2, 30000);
        continue;
      }
      throw new ChessComError(`${resp.status} for ${url}`);
    }
    throw new ChessComError(`Exhausted retries for ${url}`);
  }

  async listArchiveUrls(username: string): Promise<string[]> {
    const url = `${API_BASE}/pub/player/${username.toLowerCase()}/games/archives`;
    return (await (await this.get(url)).json()).archives || [];
  }

  private async fetchArchive(url: string): Promise<any[]> {
    return (await (await this.get(url)).json()).games || [];
  }

  async fetchGames(username: string, opts: IterOpts = {}): Promise<Game[]> {
    username = username.toLowerCase();
    const newestFirst = opts.newestFirst ?? true;
    const rules = opts.rules === undefined ? new Set(['chess']) : opts.rules;
    let archives = await this.listArchiveUrls(username);
    if (newestFirst) archives = archives.slice().reverse();

    const out: Game[] = [];
    for (const archiveUrl of archives) {
      let raws = await this.fetchArchive(archiveUrl);
      if (newestFirst) raws = raws.slice().reverse();
      for (const raw of raws) {
        if (rules && !rules.has(raw.rules)) continue;
        if (opts.timeClasses && !opts.timeClasses.has(raw.time_class)) continue;
        if (opts.ratedOnly && !raw.rated) continue;
        const g = parseGame(raw, username);
        if (!g) continue;
        out.push(g);
        if (opts.maxGames != null && out.length >= opts.maxGames) return out;
      }
    }
    return out;
  }
}
