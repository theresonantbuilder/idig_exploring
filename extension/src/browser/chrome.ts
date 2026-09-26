import { isBackgroundMessage, isOverlayMessage } from '../types';
import type { BrowserApi, TabInfo } from './abstraction';

// The only file allowed to call chrome.* (SPEC §4.1).

function toTabInfo(tab: chrome.tabs.Tab | undefined): TabInfo | undefined {
  if (tab?.id === undefined) return undefined;
  return { id: tab.id, windowId: tab.windowId, url: tab.url };
}

export const chromeApi: BrowserApi = {
  onActionClicked(handler) {
    chrome.action.onClicked.addListener((tab) => {
      const info = toTabInfo(tab);
      if (info) handler(info);
    });
  },

  async startSelection(tabId) {
    await chrome.tabs.sendMessage(tabId, { type: 'idig:start-selection' });
  },

  captureVisibleTab(windowId) {
    return chrome.tabs.captureVisibleTab(windowId, { format: 'png' });
  },

  sendToBackground(message) {
    chrome.runtime.sendMessage(message).catch(() => {
      // The background wakes on demand; a failure here means the extension was reloaded mid-selection.
    });
  },

  onOverlayMessage(handler) {
    chrome.runtime.onMessage.addListener((message, sender) => {
      if (sender.id !== chrome.runtime.id || !isOverlayMessage(message)) return;
      handler(message, toTabInfo(sender.tab));
    });
  },

  async showPanel(tabId, query) {
    const clean = Object.fromEntries(Object.entries(query).filter(([, v]) => v !== undefined)) as Record<
      string,
      string
    >;
    await chrome.tabs.sendMessage(tabId, { type: 'idig:show-panel', ...clean });
  },

  onBackgroundMessage(handler) {
    chrome.runtime.onMessage.addListener((message, sender) => {
      if (sender.id !== chrome.runtime.id || !isBackgroundMessage(message)) return;
      handler(message);
    });
  },

  reviewPanelUrl(query) {
    return `${chrome.runtime.getURL('review/review.html')}?${new URLSearchParams(query)}`;
  },

  async downloadFile(blob, filename) {
    const url = URL.createObjectURL(blob);
    try {
      await chrome.downloads.download({ url, filename, saveAs: false });
    } finally {
      // The download reads the blob asynchronously; revoke once it's had time to finish.
      setTimeout(() => URL.revokeObjectURL(url), 30_000);
    }
  },

  async setBadge(tabId, text) {
    await chrome.action.setBadgeText({ tabId, text });
    if (text) await chrome.action.setBadgeBackgroundColor({ tabId, color: '#B3261E' });
  },

  session: {
    async get<T>(key: string) {
      const result = await chrome.storage.session.get(key);
      return result[key] as T | undefined;
    },
    async getAll() {
      return chrome.storage.session.get(null);
    },
    async set(key, value) {
      await chrome.storage.session.set({ [key]: value });
    },
    async remove(keys) {
      await chrome.storage.session.remove(keys);
    },
  },

  local: {
    async get<T>(key: string) {
      const result = await chrome.storage.local.get(key);
      return result[key] as T | undefined;
    },
    async set(key, value) {
      await chrome.storage.local.set({ [key]: value });
    },
  },
};
