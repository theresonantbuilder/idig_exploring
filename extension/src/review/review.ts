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
    </div>
  `;
  li.querySelector<HTMLElement>('.history-domain')!.textContent = entry.domain;
  const link = li.querySelector<HTMLAnchorElement>('.history-link')!;
  link.href = entry.url;
  link.textContent = entry.url;

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
  };
  await saveHistory([entry, ...(await loadHistory())]);
  await discardCapture();
  closeSelf();
});

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

function trailCard(trail: TrailCandidate): HTMLElement {
  const card = el('article', 'trail-card');
  card.append(
    el('span', 'move-badge', trail.move),
    el('p', 'trail-question', trail.question),
    el('p', 'trail-hook', trail.hook),
  );
  return card;
}

function renderDig(dig: HeadlineDig) {
  const root = $('dig-root');

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
  for (const trail of shown) trailList.append(trailCard(trail));

  const moreButton = el('button', 'link', 'More trails');
  moreButton.type = 'button';
  moreButton.addEventListener('click', () => {
    for (const trail of hidden) trailList.append(trailCard(trail));
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
  renderDig(MOCK_DIG);

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
