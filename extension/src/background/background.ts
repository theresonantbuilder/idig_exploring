import { browserApi } from '../browser/abstraction';
import { captureKey, type Capture, type ReviewError, type SelectionMessage } from '../types';
import { cropScreenshot } from './crop';

// Snips nobody sent or cancelled are removed after this long.
const CAPTURE_TTL_MS = 15 * 60 * 1000;

function isInjectable(url: string | undefined): url is string {
  return !!url && /^(https?|file):/.test(url);
}

function domainOf(url: string): string {
  return new URL(url).hostname.replace(/^www\./, '');
}

async function showError(tabId: number, error: ReviewError) {
  await browserApi.setBadge(tabId, '!');
  try {
    await browserApi.showPanel(tabId, { error });
  } catch {
    // No content script on this tab to show it in (e.g. opened before install/reload).
    // The badge is the only feedback available.
  }
}

async function sweepStaleCaptures() {
  const all = await browserApi.session.getAll();
  const cutoff = Date.now() - CAPTURE_TTL_MS;
  const stale = Object.entries(all)
    .filter(([key, value]) => key.startsWith('capture:') && Date.parse((value as Capture).capturedAt) < cutoff)
    .map(([key]) => key);
  if (stale.length) await browserApi.session.remove(stale);
}

browserApi.onActionClicked(async (tab) => {
  await browserApi.setBadge(tab.id, '');
  if (!isInjectable(tab.url)) {
    await showError(tab.id, 'unsupported');
    return;
  }
  try {
    await browserApi.startSelection(tab.id);
  } catch {
    // No persistent content script on this tab yet (opened before install/reload).
    await showError(tab.id, 'unsupported');
  }
});

browserApi.onOverlayMessage(async (message, tab) => {
  if (!tab) return;
  if (message.type === 'idig:cancel') return;
  await handleSelection(message, tab.id, tab.windowId);
});

async function handleSelection(selection: SelectionMessage, tabId: number, windowId: number) {
  try {
    const screenshot = await browserApi.captureVisibleTab(windowId);
    const capture: Capture = {
      id: crypto.randomUUID(),
      image: await cropScreenshot(screenshot, selection),
      url: selection.url,
      domain: domainOf(selection.url),
      capturedAt: new Date().toISOString(),
    };
    await sweepStaleCaptures();
    await browserApi.session.set(captureKey(capture.id), capture);
    await browserApi.showPanel(tabId, { capture: capture.id });
  } catch (error) {
    console.error('iDIG: capture failed', error);
    await showError(tabId, 'capture-failed');
  }
}
