import type { BackgroundMessage, OverlayMessage } from '../types';
import { chromeApi } from './chrome';

export interface TabInfo {
  id: number;
  windowId: number;
  url?: string;
}

/**
 * Every browser API the extension uses. Application code imports `browserApi`
 * from here and never touches `chrome.*` directly, so a Safari or Firefox
 * implementation only has to replace chrome.ts.
 */
export interface BrowserApi {
  onActionClicked(handler: (tab: TabInfo) => void): void;
  /** Tells the persistent content script already on that tab to start a selection. */
  startSelection(tabId: number): Promise<void>;
  /** PNG data URL of the visible part of the window's active tab. */
  captureVisibleTab(windowId: number): Promise<string>;
  sendToBackground(message: OverlayMessage): void;
  onOverlayMessage(handler: (message: OverlayMessage, tab: TabInfo | undefined) => void): void;
  /** Tells the content script on that tab to open the docked review panel. */
  showPanel(tabId: number, query: { capture?: string; error?: string }): Promise<void>;
  /** Content script side: listens for `startSelection`/`showPanel` requests from the background. */
  onBackgroundMessage(handler: (message: BackgroundMessage) => void): void;
  /** The extension-page URL for the review panel's iframe. */
  reviewPanelUrl(query: Record<string, string>): string;
  /** Saves to Downloads/<a fixed subfolder>/<filename> — chrome.downloads is the only
   *  way to target a specific folder; a plain <a download> can't. */
  downloadFile(blob: Blob, filename: string): Promise<void>;
  setBadge(tabId: number, text: string): Promise<void>;
  /** Cleared when the browser closes, and readable only by extension pages. */
  session: {
    get<T>(key: string): Promise<T | undefined>;
    getAll(): Promise<Record<string, unknown>>;
    set(key: string, value: unknown): Promise<void>;
    remove(keys: string | string[]): Promise<void>;
  };
  /** Persists across restarts. Used only for the floating icon's dragged position. */
  local: {
    get<T>(key: string): Promise<T | undefined>;
    set(key: string, value: unknown): Promise<void>;
  };
}

export const browserApi: BrowserApi = chromeApi;
