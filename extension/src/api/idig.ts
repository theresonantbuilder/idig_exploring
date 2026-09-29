import { IDIG_API_URL } from '../config';
import type { TrailCandidate } from '../review/mockDig';

// SPEC.md §4.7/§5.1. `{API}` is always just the origin — this file owns the
// only fetch to it. 8s timeout: generation happens async on the server side
// (a background worker for now, SPEC's real queue later), so this call should
// return almost immediately either way.
const TIMEOUT_MS = 8000;

export interface SnipPayload {
  headline: string;
  source_url: string;
  source_domain: string;
  captured_at: string;
  source: 'idig-browser-extension';
}

export type SnipResult =
  | { ok: true; id: string; delete_token: string }
  | { ok: false; kind: 'network' | 'timeout' | 'server'; message?: string };

export async function sendSnip(payload: SnipPayload): Promise<SnipResult> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), TIMEOUT_MS);
  try {
    const res = await fetch(`${IDIG_API_URL}/exploring/api/snips`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
      signal: controller.signal,
    });
    if (res.status === 201) {
      const data = (await res.json()) as { id: string; delete_token: string };
      return { ok: true, id: data.id, delete_token: data.delete_token };
    }
    let message: string | undefined;
    try {
      message = ((await res.json()) as { error?: string }).error;
    } catch {
      // response wasn't JSON — leave message undefined, fallback UI still works
    }
    return { ok: false, kind: 'server', message };
  } catch (e) {
    return { ok: false, kind: (e as Error).name === 'AbortError' ? 'timeout' : 'network' };
  } finally {
    clearTimeout(timer);
  }
}

export function digUrl(id: string, deleteToken: string): string {
  return `${IDIG_API_URL}/exploring/${id}#t=${deleteToken}`;
}

// SPEC.md §5.2/§5.3, as currently served by the local dev server (dev_server/server.py) —
// simplified (no separate snip/dig ids, no match_type) until the real backend exists.
export interface DigApiDig {
  id: string;
  headline: string;
  source_url: string;
  source_domain: string;
  result: {
    claim: string;
    what_happened: string;
    why_now: string;
    established: string[];
    contested: { held_by: string; position: string }[];
    left_out: string;
    still_unknown: string[];
    usage: { prompt: number; tool_use_prompt: number; output: number; thinking: number; total: number };
  };
  sources: { title: string; url: string }[];
  trails: TrailCandidate[];
  more_trails: TrailCandidate[];
  explorer_count: number;
}

export interface DigApiResponse {
  status: 'received' | 'researching' | 'ready' | 'unverified' | 'error';
  dig: DigApiDig | null;
  error?: string;
}

export async function pollSnip(id: string): Promise<DigApiResponse> {
  const res = await fetch(`${IDIG_API_URL}/exploring/api/snips/${id}`);
  return (await res.json()) as DigApiResponse;
}
