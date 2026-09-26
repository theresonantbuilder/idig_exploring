# iDIG Exploring — browser extension

Snip a headline on any page and dig into it at `i-dig.io/exploring`. See
[`../SPEC.md` §4](../SPEC.md#4-extension) for the design and
[`../_sprints/SPRINT_1_Exploring_MVP.md`](../_sprints/SPRINT_1_Exploring_MVP.md) for progress.

**Current stage: Phase A (snip prototype).** A floating iDIG icon sits on the right edge of
every page (drag it up/down to reposition) — click it, or the toolbar icon, to draw a box
around a headline. A docked panel slides in from the right showing the cropped image. OCR,
editing and sending come in Phases B and C.

## Build

```
npm install
npm run build:dev    # API → http://localhost:3003 (.env.development)
npm run build        # API → https://i-dig.io     (.env.production)
```

Both write to `dist/`. Re-run after every change. There's no watch mode yet.

## Load in Chrome

1. Open `chrome://extensions` and turn on **Developer mode** (top right).
2. Click **Load unpacked** and pick the `dist/` folder.
3. Pin the iDIG icon to the toolbar (puzzle-piece menu → pin).
4. After rebuilding, click the reload arrow on the extension's card.

Edge and Brave use the same steps (`edge://extensions`, `brave://extensions`).

## Try it

1. Open a news article. A small iDIG icon floats on the right edge of the page — drag it up
   or down, or click it (or the toolbar icon) to start.
2. Drag a box around the headline. Drag again to redo it, or press Esc to cancel.
3. Click **iDIG** (or press Enter). A panel slides in from the right showing only your
   selection.

Scrolling or resizing the page while selecting cancels the selection, because only the
visible part of the page is captured.

**Debugging:**
- Background errors: `chrome://extensions` → the extension's card → **service worker**
  link → Console.
- Overlay errors: the article page's own DevTools console.

If you see "screenshot width does not match viewport × DPR" in the service worker
console, the crop may be offset. Note the page and zoom level in the sprint's gate results.

## Layout

| Path | What |
|---|---|
| `public/manifest.json` | MV3 manifest: `storage` + all-origin `host_permissions`, a persistent `content_scripts` entry running `launcher.js` |
| `src/browser/` | `abstraction.ts` (the interface everything uses) and `chrome.ts` (the only file that calls `chrome.*`) |
| `src/background/` | Capture + crop, then messages the tab's launcher to show the docked panel |
| `src/content/launcher.ts` | Persistent: floating draggable icon, selection surface (closed Shadow DOM), and the docked review panel's iframe host. Built standalone as `launcher.js` (`vite.content.config.ts`) |
| `src/review/` | The review UI, loaded inside the docked panel's iframe |
| `src/config.ts` | The only place the API URL is read |
| `scripts/make-icons.mjs` | Regenerates the placeholder icons (`npm run icons`) |
