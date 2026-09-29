import { browserApi } from '../browser/abstraction';
import {
  captureKey,
  HISTORY_KEY,
  HISTORY_LIMIT,
  type Capture,
  type HistoryEntry,
  type ReviewError,
} from '../types';
import { MOCK_DIG, type HeadlineDig, type TrailCandidate } from './mockDig';
import { MOCK_DEEPER, type DeeperResource, type ResourceType } from './mockDeeper';
import { sendSnip, digUrl, pollSnip, type DigApiDig, type DigApiResponse } from '../api/idig';
import { recognize } from '../ocr/ocr';

// Phase A: shows only the cropped image (sprint A7). OCR, the editable
// headline and Send arrive in Phases B and C. History is local-only, filled
// by an explicit Save — Cancel still discards immediately (SPEC §11).

const PROBLEMS: Record<ReviewError | 'expired', { title: string; text: string }> = {
  unsupported: {
    title: "iDIG can't run on this page.",
    text: "Chrome doesn't let extensions work on its own pages, the Web Store or some built-in viewers. Open an article and try again.",
  },
  'capture-failed': {
    title: "We couldn't capture your selection.",
    text: 'Close this window and try the snip again.',
  },
  expired: {
    title: 'This snip has expired.',
    text: 'Snip the headline again.',
  },
};

const params = new URLSearchParams(location.search);
const captureId = params.get('capture');
let currentCapture: Capture | undefined;
// The most recently completed real dig for this capture, if any — Save attaches it to the
// HistoryEntry so History holds the actual research, not just the screenshot (SPEC §11:
// History is filled only by an explicit Save, so this doesn't save on its own).
let lastDig: DigApiDig | null = null;

function $(id: string) {
  return document.getElementById(id)!;
}

function showProblem(kind: keyof typeof PROBLEMS) {
  $('problem-title').textContent = PROBLEMS[kind].title;
  $('problem-text').textContent = PROBLEMS[kind].text;
  $('problem').hidden = false;
}

async function discardCapture() {
  if (captureId) await browserApi.session.remove(captureKey(captureId));
}

// This page normally runs inside the docked panel's iframe, which can't close
// itself — it asks the launcher content script to remove it instead.
function closeSelf() {
  if (window.self !== window.top) window.parent.postMessage({ type: 'idig:close-panel' }, '*');
  else window.close();
}

// ---------------------------------------------------------------------------
// Tabs
// ---------------------------------------------------------------------------

function selectTab(name: string) {
  for (const tab of document.querySelectorAll<HTMLButtonElement>('.tab')) {
    tab.setAttribute('aria-selected', String(tab.dataset.tab === name));
  }
  for (const panel of document.querySelectorAll<HTMLElement>('[data-panel]')) {
    panel.hidden = panel.id !== name;
  }
  ($('save') as HTMLButtonElement).hidden = name !== 'capture' || !currentCapture;
}

document.querySelectorAll<HTMLButtonElement>('.tab').forEach((tab) => {
  tab.addEventListener('click', () => selectTab(tab.dataset.tab!));
});

// ---------------------------------------------------------------------------
// History (local-only; written by Save, never by Cancel)
// ---------------------------------------------------------------------------

async function loadHistory(): Promise<HistoryEntry[]> {
  return (await browserApi.local.get<HistoryEntry[]>(HISTORY_KEY)) ?? [];
}

async function saveHistory(entries: HistoryEntry[]) {
  await browserApi.local.set(HISTORY_KEY, entries.slice(0, HISTORY_LIMIT));
}

function relativeTime(iso: string): string {
  const seconds = Math.max(0, (Date.now() - Date.parse(iso)) / 1000);
  const units: [string, number][] = [
    ['day', 86400],
    ['hour', 3600],
    ['minute', 60],
  ];
  for (const [unit, secondsPerUnit] of units) {
    const value = Math.floor(seconds / secondsPerUnit);
    if (value >= 1) return `${value} ${unit}${value === 1 ? '' : 's'} ago`;
  }
  return 'just now';
}

function renderHistoryRow(entry: HistoryEntry): HTMLLIElement {
  const li = document.createElement('li');
  li.className = 'history-row';
  li.innerHTML = `
    <button type="button" class="history-toggle">
      <img src="${entry.image}" alt="" />
      <span class="history-meta">
        <span class="history-domain"></span>
        <span class="history-time">${relativeTime(entry.savedAt)}</span>
      </span>
    </button>
    <button type="button" class="history-remove" aria-label="Remove">×</button>
    <div class="history-full" hidden>
      <img src="${entry.image}" alt="" />
      <a class="history-link" target="_blank" rel="noopener noreferrer"></a>
      <div class="history-dig-root"></div>
    </div>
  `;
  li.querySelector<HTMLElement>('.history-domain')!.textContent = entry.headline ?? entry.domain;
  const link = li.querySelector<HTMLAnchorElement>('.history-link')!;
  link.href = entry.url;
  link.textContent = entry.url;

  // Older entries (saved before the real pipeline existed) only ever had the crop image —
  // `dig` is optional specifically so those still render fine with just image + link.
  if (entry.dig) {
    renderDig(toHeadlineDig(entry.dig as DigApiDig), li.querySelector<HTMLElement>('.history-dig-root')!, {
      getDeeper: (t) => t.deeper,
    });
  }

  const full = li.querySelector<HTMLElement>('.history-full')!;
  li.querySelector('.history-toggle')!.addEventListener('click', () => {
    full.hidden = !full.hidden;
  });
  li.querySelector('.history-remove')!.addEventListener('click', async () => {
    await saveHistory((await loadHistory()).filter((e) => e.id !== entry.id));
    await renderHistory();
  });
  return li;
}

async function renderHistory() {
  const entries = await loadHistory();
  const list = $('history-list');
  list.replaceChildren(...entries.map(renderHistoryRow));
  $('history-empty').hidden = entries.length > 0;
  $('panel-status').hidden = true;
}

function showHistoryStatus(text: string) {
  const status = $('panel-status');
  status.textContent = text;
  status.hidden = false;
}

document.querySelectorAll<HTMLButtonElement>('.clear-btn').forEach((button) => {
  button.addEventListener('click', async () => {
    await saveHistory([]);
    await renderHistory();
  });
});

// ---------------------------------------------------------------------------
// Export / import (the only way History survives removing the extension —
// chrome.storage.local is wiped along with everything else on uninstall)
// ---------------------------------------------------------------------------

function isHistoryEntry(value: unknown): value is HistoryEntry {
  const v = value as Partial<HistoryEntry> | null;
  return (
    !!v &&
    typeof v.id === 'string' &&
    typeof v.image === 'string' &&
    typeof v.url === 'string' &&
    typeof v.domain === 'string' &&
    typeof v.savedAt === 'string'
  );
}

// Every export lands in the same Downloads subfolder, so Import always has one
// obvious place to look (Chrome also tends to reopen its file picker on the
// last folder used — but that's the browser remembering, not us forcing it).
const EXPORT_FOLDER = 'iDIG Exploring';

document.querySelectorAll<HTMLButtonElement>('.export-btn').forEach((button) => {
  button.addEventListener('click', async () => {
    const entries = await loadHistory();
    const blob = new Blob([JSON.stringify(entries, null, 2)], { type: 'application/json' });
    const filename = `${EXPORT_FOLDER}/idig-history-${new Date().toISOString().slice(0, 10)}.json`;
    await browserApi.downloadFile(blob, filename);
    showHistoryStatus(`Saved to Downloads/${EXPORT_FOLDER}.`);
  });
});

document.querySelectorAll<HTMLButtonElement>('.import-btn').forEach((button) => {
  button.addEventListener('click', () => ($('import-file') as HTMLInputElement).click());
});

$('import-file').addEventListener('change', async (event) => {
  const input = event.target as HTMLInputElement;
  const file = input.files?.[0];
  input.value = ''; // allow re-importing the same file later
  if (!file) return;

  let parsed: unknown;
  try {
    parsed = JSON.parse(await file.text());
  } catch {
    showHistoryStatus('That file is not valid JSON.');
    return;
  }
  const incoming = (Array.isArray(parsed) ? parsed : []).filter(isHistoryEntry);
  if (incoming.length === 0) {
    showHistoryStatus("That file doesn't look like an iDIG History export.");
    return;
  }

  const existing = await loadHistory();
  const byId = new Map(existing.map((entry) => [entry.id, entry]));
  for (const entry of incoming) byId.set(entry.id, entry);
  const merged = [...byId.values()].sort((a, b) => Date.parse(b.savedAt) - Date.parse(a.savedAt));
  await saveHistory(merged);
  await renderHistory();
  showHistoryStatus(`Imported ${incoming.length} snip${incoming.length === 1 ? '' : 's'}.`);
});

$('save').addEventListener('click', async () => {
  if (!currentCapture) return;
  const entry: HistoryEntry = {
    id: currentCapture.id,
    image: currentCapture.image,
    url: currentCapture.url,
    domain: currentCapture.domain,
    savedAt: new Date().toISOString(),
    headline: lastDig?.headline,
    dig: lastDig ?? undefined,
  };
  await saveHistory([entry, ...(await loadHistory())]);
  await discardCapture();
  closeSelf();
});

// ---------------------------------------------------------------------------
// Send (SPEC §4.7): real snips go to the dev server, which opens a new tab on
// the real page once the pipeline finishes. The extension keeps nothing.
// ---------------------------------------------------------------------------

const SEND_ERROR_TEXT: Record<'network' | 'timeout' | 'server', string> = {
  network: "Couldn't reach iDIG — is the local dev server running?",
  timeout: 'iDIG took too long to respond.',
  server: 'iDIG rejected this snip.',
};

// Hidden by default (SPEC's real path is snip -> OCR -> auto-render, no form to fill in) —
// this only ever appears as a fallback, when OCR couldn't produce a usable headline or a
// send attempt failed and the observer needs to see/fix what's about to be (re)sent.
function revealManualEntry() {
  $('manual-entry').hidden = false;
}

function showSendStatus(text: string, payload?: object) {
  revealManualEntry();
  const status = $('send-status');
  status.textContent = '';
  status.append(el('span', undefined, `● iDIG unavailable — ${text} `));
  const retry = el('button', 'link', 'Retry');
  retry.type = 'button';
  retry.addEventListener('click', () => void sendSnipFlow());
  status.append(retry);
  if (payload) {
    const copy = el('button', 'link', 'Copy payload');
    copy.type = 'button';
    copy.addEventListener('click', () => void navigator.clipboard.writeText(JSON.stringify(payload, null, 2)));
    status.append(copy);
  }
  status.hidden = false;
}

// Running total for this panel session only (resets when the panel closes) — enough to
// tune prompts/thresholds against real cost as you go, not a durable spend tracker.
let sessionTokens = 0;
function addToTokenCounter(total: number) {
  sessionTokens += total;
  const counter = $('token-counter');
  counter.textContent = `${sessionTokens.toLocaleString()} tokens this session`;
  counter.hidden = false;
}

function toHeadlineDig(dig: DigApiDig): HeadlineDig {
  return {
    sourceUrl: dig.source_url,
    sourceDomain: dig.source_domain,
    headline: dig.headline,
    claim: dig.result.claim,
    what_happened: dig.result.what_happened,
    why_now: dig.result.why_now,
    established: dig.result.established,
    contested: dig.result.contested,
    left_out: dig.result.left_out,
    still_unknown: dig.result.still_unknown,
    sources: dig.sources,
    trails: [...dig.trails, ...dig.more_trails],
    explorerCount: dig.explorer_count,
  };
}

// Polls every 3s (SPEC §5.2's cadence) until the background pipeline finishes. No
// per-poll timeout — a slow poll just tries again in 3s — but caps total wait so a
// stuck dev server doesn't poll forever.
async function pollUntilDone(id: string, onProgress: (status: string) => void): Promise<DigApiResponse> {
  const MAX_ATTEMPTS = 40; // ~2 minutes
  for (let i = 0; i < MAX_ATTEMPTS; i++) {
    let data: DigApiResponse;
    try {
      data = await pollSnip(id);
    } catch {
      return { status: 'error', dig: null, error: "Couldn't reach iDIG while waiting for a result." };
    }
    if (data.status !== 'received' && data.status !== 'researching') return data;
    onProgress(data.status);
    await new Promise((resolve) => setTimeout(resolve, 3000));
  }
  return { status: 'error', dig: null, error: 'Timed out waiting for a result.' };
}

async function sendSnipFlow() {
  if (!currentCapture) return;
  const headline = ($('headline-input') as HTMLInputElement).value.trim();
  if (headline.length < 3 || headline.length > 300) {
    return showSendStatus('Type the headline (3-300 characters) first.');
  }
  const sendButton = $('send') as HTMLButtonElement;
  const progress = $('dig-progress');
  const shareLink = $('dig-share-link') as HTMLAnchorElement;
  sendButton.disabled = true;
  sendButton.textContent = 'Sending…';
  $('send-status').hidden = true;
  shareLink.hidden = true;
  $('capture-dig-root').replaceChildren();
  lastDig = null;

  const payload = {
    headline,
    source_url: currentCapture.url,
    source_domain: currentCapture.domain,
    captured_at: currentCapture.capturedAt,
    source: 'idig-browser-extension' as const,
  };
  const result = await sendSnip(payload);
  sendButton.disabled = false;
  sendButton.textContent = 'Send to iDIG';

  if (!result.ok) {
    return showSendStatus(result.message ?? SEND_ERROR_TEXT[result.kind], payload);
  }

  progress.hidden = false;
  progress.textContent = 'Researching your dig… (usually 10-20s)';
  const data = await pollUntilDone(result.id, (status) => {
    progress.textContent = status === 'researching' ? 'Researching your dig… (usually 10-20s)' : 'Queued…';
  });

  if (data.status === 'unverified') {
    progress.textContent = "We couldn't confirm this against search results. Treat it with care.";
    return;
  }
  if (data.status === 'error' || !data.dig) {
    progress.hidden = true;
    return showSendStatus(data.error ?? 'Something went wrong while researching this.', payload);
  }

  progress.hidden = true;
  shareLink.href = digUrl(result.id, result.delete_token);
  shareLink.hidden = false;
  lastDig = data.dig;
  renderDig(toHeadlineDig(data.dig), $('capture-dig-root'), { getDeeper: (t) => t.deeper });
  addToTokenCounter(data.dig.result.usage.total);
}

$('send').addEventListener('click', () => void sendSnipFlow());

// ---------------------------------------------------------------------------
// Dig preview (mock content, laid out per SPEC §5.6/§7.1 — see mockDig.ts)
// ---------------------------------------------------------------------------

function el<K extends keyof HTMLElementTagNameMap>(
  tag: K,
  className?: string,
  text?: string,
): HTMLElementTagNameMap[K] {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

function digBlock(heading: string, body: HTMLElement): HTMLElement {
  const section = el('section', 'dig-block');
  section.append(el('h2', undefined, heading), body);
  return section;
}

function listOf(items: string[]): HTMLUListElement {
  const ul = el('ul', 'dig-list');
  for (const item of items) ul.append(el('li', undefined, item));
  return ul;
}

const RESOURCE_TYPE_LABEL: Record<ResourceType, string> = {
  book: 'Book',
  course: 'Course',
  podcast: 'Podcast',
  video: 'Video',
  article: 'Article',
  exhibit: 'Exhibit',
};

// "iDIG Deeper": 2-3 resources attached under THIS trail specifically —
// mixed sources (not only affiliate links), so it reads as genuinely useful
// rather than a merchandising rail. See mockDeeper.ts.
function deeperResourceItem(resource: DeeperResource): HTMLElement {
  const item = el('li', 'deeper-item');
  const head = el('div', 'deeper-item-head');
  head.append(
    el('span', `deeper-type deeper-type-${resource.type}`, RESOURCE_TYPE_LABEL[resource.type]),
    el('span', 'deeper-title', resource.title),
  );
  const link = el('a', 'deeper-source', `${resource.source} ↗`);
  link.href = resource.url;
  link.target = '_blank';
  link.rel = 'noopener noreferrer';
  item.append(head, el('p', 'deeper-reason', resource.reason), link);
  return item;
}

function deeperCallout(resources: DeeperResource[] | undefined): HTMLElement | null {
  if (!resources || resources.length === 0) return null;
  const list = el('ul', 'deeper-list');
  for (const resource of resources) list.append(deeperResourceItem(resource));
  const callout = el('div', 'deeper-callout');
  callout.append(el('div', 'deeper-label', 'iDIG Deeper'), list);
  return callout;
}

// Mock rendering passes MOCK_DEEPER[trail.move] (hand-written for one headline, fine since
// the Preview tab is clearly labeled mock); real digs pass trail.deeper, the real per-trail
// resources the Deeper pipeline found for THIS specific headline (pipeline.py's run_deeper).
function trailCard(trail: TrailCandidate, resources: DeeperResource[] | undefined): HTMLElement {
  const card = el('article', 'trail-card');
  card.append(
    el('span', 'pattern-badge', trail.pattern),
    el('p', 'move-badge', trail.angle),
    el('p', 'trail-question', trail.question),
    el('p', 'trail-hook', trail.hook),
  );
  const deeper = deeperCallout(resources);
  if (deeper) card.append(deeper);
  return card;
}

// AI-disclosure + Report (SPEC §5.6/§5.7) — a disclaimer nobody can act on
// isn't a safeguard, it's decoration, so this pairs the text with a real
// (if backend-less, for now) action rather than just a line of copy.
function renderDisclosure(): HTMLElement {
  const bar = el('div', 'ai-disclosure');
  const text = el(
    'p',
    'ai-disclosure-text',
    'Written by AI from real search results, not a human editor. Check the sources below — and tell us if something looks wrong.',
  );
  const reportButton = el('button', 'link ai-report-toggle', 'Report this');
  reportButton.type = 'button';

  const reasons = el('div', 'ai-report-reasons');
  reasons.hidden = true;
  const options: { label: string; value: string }[] = [
    { label: 'Inaccurate', value: 'inaccurate' },
    { label: 'Concerning', value: 'concerning' },
    { label: 'Broken link', value: 'broken_link' },
    { label: 'Other', value: 'other' },
  ];
  for (const option of options) {
    const button = el('button', 'link ai-report-reason', option.label);
    button.type = 'button';
    button.addEventListener('click', () => {
      // No backend yet (Phase D/E) — this just demonstrates the interaction.
      reasons.replaceChildren(el('span', 'ai-report-thanks', 'Thanks — noted.'));
    });
    reasons.append(button);
  }

  reportButton.addEventListener('click', () => {
    reasons.hidden = !reasons.hidden;
  });

  bar.append(text, reportButton, reasons);
  return bar;
}

function renderDig(
  dig: HeadlineDig,
  root: HTMLElement,
  options: { getDeeper?: (trail: TrailCandidate) => DeeperResource[] | undefined } = {},
) {
  const getDeeper = options.getDeeper ?? ((trail) => MOCK_DEEPER[trail.move]);
  const source = el('p', 'source');
  source.append('From ', el('span', undefined, dig.sourceDomain), ' ');
  const sourceLink = el('a', 'url', dig.sourceUrl);
  sourceLink.href = dig.sourceUrl;
  sourceLink.target = '_blank';
  sourceLink.rel = 'noopener noreferrer';
  source.append(sourceLink);

  const headline = el('h1', 'dig-headline', dig.headline);
  const claim = el('p', 'dig-claim', dig.claim);

  const contestedList = el('ul', 'dig-list contested-list');
  for (const entry of dig.contested) {
    const li = el('li', 'contested-item');
    li.append(el('span', 'held-by', entry.held_by), el('p', undefined, entry.position));
    contestedList.append(li);
  }

  const sourcesList = el('ul', 'dig-list sources-list');
  for (const source of dig.sources) {
    const li = el('li');
    const a = el('a', undefined, source.title);
    a.href = source.url;
    a.target = '_blank';
    a.rel = 'noopener noreferrer';
    li.append(a);
    sourcesList.append(li);
  }

  const shown = dig.trails.filter((t) => t.rank !== null).sort((a, b) => (a.rank ?? 0) - (b.rank ?? 0));
  const hidden = dig.trails.filter((t) => t.rank === null);
  const trailList = el('div', 'trail-list');
  for (const trail of shown) trailList.append(trailCard(trail, getDeeper(trail)));

  const moreButton = el('button', 'link', 'More trails');
  moreButton.type = 'button';
  moreButton.addEventListener('click', () => {
    for (const trail of hidden) trailList.append(trailCard(trail, getDeeper(trail)));
    moreButton.remove();
  });

  const trailsSection = el('section', 'dig-trails');
  trailsSection.append(
    el('h2', undefined, 'Trails'),
    trailList,
    moreButton,
    el('p', 'explorer-count', `${dig.explorerCount} explorers dug this`),
  );

  root.replaceChildren(
    source,
    headline,
    renderDisclosure(),
    claim,
    digBlock('What happened', el('p', undefined, dig.what_happened)),
    digBlock('Why now', el('p', undefined, dig.why_now)),
    digBlock('Established', listOf(dig.established)),
    digBlock('Contested', contestedList),
    digBlock('Left out', el('p', undefined, dig.left_out)),
    digBlock('Still unknown', listOf(dig.still_unknown)),
    digBlock('Sources', sourcesList),
    trailsSection,
  );
}

// ---------------------------------------------------------------------------
// Init
// ---------------------------------------------------------------------------

const captureTab = document.querySelector<HTMLButtonElement>('[data-tab="capture"]')!;

async function init() {
  await renderHistory();
  renderDig(MOCK_DIG, $('dig-root'));

  const error = params.get('error') as ReviewError | null;
  if (error && error in PROBLEMS) return showProblem(error);

  // Opened directly from the launcher icon, with nothing snipped yet — just
  // browsing. There's no "expired" error here; nothing was ever pending.
  if (!captureId) {
    captureTab.hidden = true;
    $('tabs').hidden = false;
    selectTab('history');
    return;
  }

  const capture = await browserApi.session.get<Capture>(captureKey(captureId));
  if (!capture) return showProblem('expired');
  currentCapture = capture;

  ($('crop') as HTMLImageElement).src = capture.image;
  $('domain').textContent = capture.domain;
  ($('url') as HTMLAnchorElement).href = capture.url;
  $('url').textContent = capture.url;
  $('url').title = capture.url;

  $('tabs').hidden = false;
  selectTab('capture');
  void runOcr(capture.image);
}

// Phase B (SPEC §4.6): fills the editable headline field so there's usually nothing to
// type — but it stays editable because OCR on small, low-contrast header text is never
// perfectly reliable, and a wrong headline is worse than a slow one.
async function runOcr(image: string) {
  const input = $('headline-input') as HTMLInputElement;
  const debug = $('ocr-debug');
  input.disabled = true;
  input.placeholder = 'Recognizing headline…';
  debug.hidden = false;
  debug.textContent = 'OCR: starting…';
  try {
    const { text, confidence } = await recognize(image);
    const cleaned = text.replace(/\s+/g, ' ').trim();
    debug.textContent = `OCR: confidence ${confidence} — raw text: ${JSON.stringify(text)}`;
    if (cleaned.length >= 3) {
      input.value = cleaned;
      // OCR got something usable — go straight to the pipeline, no form, no click.
      void sendSnipFlow();
    } else {
      // Too short/empty to trust — fall back to letting the observer type it themselves.
      revealManualEntry();
    }
  } catch (e) {
    // OCR failed outright — same fallback as an unusable result.
    debug.textContent = `OCR failed: ${e instanceof Error ? `${e.name}: ${e.message}` : String(e)}`;
    revealManualEntry();
  } finally {
    input.disabled = false;
    input.placeholder = 'Type the headline exactly as it appears in your snip';
  }
}

$('cancel').addEventListener('click', async () => {
  await discardCapture();
  closeSelf();
});

$('new-snip').addEventListener('click', async () => {
  await discardCapture();
  window.parent.postMessage({ type: 'idig:start-selection-from-panel' }, '*');
});

// A real toggle: removing and re-adding the extension doesn't reliably clear
// chrome.storage.local in practice, so it can't be the only way back. The
// launcher passes its current state in the URL each time it opens the panel;
// clicking here just flips the label optimistically — the launcher (outside
// this iframe) owns and persists the actual state.
let launcherRemoved = params.get('removed') === '1';
const removeLauncherButton = $('remove-launcher') as HTMLButtonElement;

function renderRemoveLabel() {
  removeLauncherButton.textContent = launcherRemoved ? 'Show button' : 'Remove button';
}
renderRemoveLabel();

removeLauncherButton.addEventListener('click', () => {
  launcherRemoved = !launcherRemoved;
  renderRemoveLabel();
  window.parent.postMessage({ type: 'idig:remove-launcher' }, '*');
});

// Closing the window any other way also discards the unsaved snip (SPEC §11).
window.addEventListener('pagehide', () => void discardCapture());

void init();
