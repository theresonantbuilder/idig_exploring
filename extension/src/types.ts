/** A rectangle in CSS pixels, relative to the viewport's top-left corner. */
export interface SelectionRect {
  x: number;
  y: number;
  width: number;
  height: number;
}

/** Sent by the overlay after it has removed itself from the page. */
export interface SelectionMessage {
  type: 'idig:selection';
  rect: SelectionRect;
  viewport: { width: number; height: number };
  devicePixelRatio: number;
  /** The page URL when the selection started, in case an SPA navigates mid-drag. */
  url: string;
}

export interface CancelMessage {
  type: 'idig:cancel';
  reason: 'user' | 'scroll' | 'resize';
}

export type OverlayMessage = SelectionMessage | CancelMessage;

export function isOverlayMessage(value: unknown): value is OverlayMessage {
  const type = (value as { type?: unknown } | null)?.type;
  return type === 'idig:selection' || type === 'idig:cancel';
}

/** Background → content script: the toolbar icon was clicked, start a selection. */
export interface StartSelectionMessage {
  type: 'idig:start-selection';
}

/** Background → content script: open the docked panel, either on a capture or an error. */
export interface ShowPanelMessage {
  type: 'idig:show-panel';
  capture?: string;
  error?: ReviewError;
}

export type BackgroundMessage = StartSelectionMessage | ShowPanelMessage;

export function isBackgroundMessage(value: unknown): value is BackgroundMessage {
  const type = (value as { type?: unknown } | null)?.type;
  return type === 'idig:start-selection' || type === 'idig:show-panel';
}

/** One snip, held in session storage until the review window sends or cancels it. */
export interface Capture {
  id: string;
  image: string; // PNG data URL of the cropped selection only
  url: string;
  domain: string;
  capturedAt: string;
}

export type ReviewError = 'unsupported' | 'capture-failed';

export const captureKey = (id: string) => `capture:${id}`;

/** Smallest selection the overlay accepts, in CSS pixels (SPEC §4.3). */
export const MIN_SELECTION = { width: 24, height: 12 };

/**
 * A snip the observer chose to keep, in `chrome.storage.local` (the panel's
 * History tab). Written only by an explicit Save — Cancel never creates one.
 */
export interface HistoryEntry {
  id: string;
  image: string;
  url: string;
  domain: string;
  savedAt: string;
}

export const HISTORY_KEY = 'idig:history';
export const HISTORY_LIMIT = 24;
