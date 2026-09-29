import { browserApi } from '../browser/abstraction';
import { MIN_SELECTION, type CancelMessage, type SelectionRect } from '../types';

// The persistent content script (manifest content_scripts, all http/https pages).
// Renders the floating iDIG launcher, the selection surface (on click or on a
// toolbar-icon message), and the docked review panel (an iframe onto the
// extension's own review.html, so that page's logic is unchanged).

const NAVY = '#14233A';
const GOLD = '#D9B45A';
const GOLD_HOVER = '#E6C472';
const CREAM = '#F4F1EA';
const MUTED = '#C9D2DE';
const BLUE = '#2563EB';

const LAUNCHER_TOP_KEY = 'idig:launcherTop'; // fraction 0..1 of viewport height
// An observer's opt-out. This is a real, working toggle, not a one-way door —
// removing and re-adding the extension does NOT reliably clear
// chrome.storage.local in practice (confirmed: it survives a real Chrome
// remove-and-reinstall of the unpacked build), so that can't be the only way
// back. The panel keeps a "Show button" control reachable via the toolbar icon.
const LAUNCHER_REMOVED_KEY = 'idig:launcherRemoved';
const ONBOARDED_KEY = 'idig:onboarded';

// The icon's own geometry, shared with the panel math below so the panel can
// butt up flush against it regardless of how the icon is styled.
const ICON_WIDTH = 60;
const ICON_RIGHT_MARGIN = 4;
const PANEL_RIGHT_OFFSET = ICON_RIGHT_MARGIN + ICON_WIDTH;

// `<body>` renders more reliably than `<html>` for a fixed-position host created
// right at page load, before the page's own layout has fully settled.
function attachHost(host: HTMLElement) {
  (document.body ?? document.documentElement).appendChild(host);
}

// ---------------------------------------------------------------------------
// Floating launcher icon
// ---------------------------------------------------------------------------

function createLauncher(onActivate: () => void, onMove: (centerY: number) => void) {
  const host = document.createElement('div');
  host.setAttribute('style', 'all: initial; position: fixed; inset: 0; pointer-events: none; z-index: 2147483645;');
  const root = host.attachShadow({ mode: 'closed' });
  root.innerHTML = `
    <style>
      :host { all: initial; }
      * { box-sizing: border-box; }
      .icon {
        position: fixed; right: ${ICON_RIGHT_MARGIN}px; width: ${ICON_WIDTH}px; height: 40px;
        border-radius: 12px; display: flex; align-items: center; justify-content: center;
        background: #ffffff; border: 1px solid rgba(20, 35, 58, 0.12);
        font: 800 13px/1 system-ui, -apple-system, "Segoe UI", Roboto, sans-serif;
        letter-spacing: 0.03em; cursor: pointer; pointer-events: auto; user-select: none;
        box-shadow: 0 6px 20px rgba(8, 12, 20, 0.22), 0 0 0 1px rgba(20, 35, 58, 0.04);
        transition: transform 0.18s ease, box-shadow 0.18s ease, opacity 0.2s ease;
        opacity: 0; transform: translateX(16px) scale(0.85);
      }
      .icon .i { color: ${BLUE}; }
      .icon .dig { color: ${NAVY}; }
      .icon.ready { opacity: 1; transform: translateX(0) scale(1); }
      .icon:hover {
        transform: scale(1.06);
        box-shadow: 0 8px 26px rgba(8, 12, 20, 0.3), 0 0 0 1px rgba(20, 35, 58, 0.08);
      }
      .icon.dragging { cursor: move; transition: none; }
      .icon:focus-visible { outline: 2px solid ${GOLD}; outline-offset: 2px; }
      .icon.hidden { opacity: 0; pointer-events: none; transform: translateX(16px) scale(0.85); }
    </style>
    <button type="button" class="icon" aria-label="iDIG — select something you dig">
      <span class="i">i</span><span class="dig">DIG</span>
    </button>
  `;

  const icon = root.querySelector<HTMLButtonElement>('.icon')!;
  attachHost(host);

  const MARGIN = 8;
  function clampTop(top: number) {
    return Math.min(Math.max(top, MARGIN), window.innerHeight - icon.offsetHeight - MARGIN);
  }
  function applyTop(top: number) {
    // Whole CSS pixels keep the rounded corners and gradient crisp — a
    // fractional top otherwise leaves the edges softly anti-aliased.
    icon.style.top = `${Math.round(clampTop(top))}px`;
    onMove(icon.getBoundingClientRect().top + icon.offsetHeight / 2);
  }

  // Show at a default position right away — never let visibility depend on the
  // storage round-trip finishing. Nudge to the saved spot once it resolves.
  applyTop(0.45 * window.innerHeight);
  requestAnimationFrame(() => icon.classList.add('ready'));
  browserApi.local
    .get<number>(LAUNCHER_TOP_KEY)
    .then((fraction) => {
      if (fraction !== undefined) applyTop(fraction * window.innerHeight);
    })
    .catch(() => {});
  window.addEventListener('resize', () => applyTop(parseFloat(icon.style.top) || 0));

  // An observer who doesn't want the button can remove it (panel's tab bar).
  // That's a deliberate, persisted, one-way choice — show() must not silently
  // undo it, so it stays off across the transient hide/show calls elsewhere.
  let removed = false;
  browserApi.local
    .get<boolean>(LAUNCHER_REMOVED_KEY)
    .then((value) => {
      removed = !!value;
      icon.classList.toggle('hidden', removed);
    })
    .catch(() => {});

  let dragStart: { pointerY: number; iconTop: number } | null = null;
  let dragged = false;

  icon.addEventListener('pointerdown', (event) => {
    if (event.button !== 0) return;
    dragStart = { pointerY: event.clientY, iconTop: icon.offsetTop };
    dragged = false;
    icon.setPointerCapture(event.pointerId);
    icon.classList.add('dragging');
  });

  icon.addEventListener('pointermove', (event) => {
    if (!dragStart) return;
    const delta = event.clientY - dragStart.pointerY;
    if (Math.abs(delta) > 3) dragged = true;
    applyTop(dragStart.iconTop + delta);
  });

  function endDrag() {
    if (!dragStart) return;
    dragStart = null;
    icon.classList.remove('dragging');
    void browserApi.local.set(LAUNCHER_TOP_KEY, icon.offsetTop / window.innerHeight);
  }

  icon.addEventListener('pointerup', () => {
    const wasDragged = dragged;
    endDrag();
    if (!wasDragged) onActivate();
  });
  icon.addEventListener('pointercancel', endDrag);

  return {
    hide: () => icon.classList.add('hidden'),
    show: () => {
      if (!removed) icon.classList.remove('hidden');
    },
    setActive: (active: boolean) => icon.classList.toggle('active', active),
    getCenterY: () => icon.getBoundingClientRect().top + icon.offsetHeight / 2,
    isRemoved: () => removed,
    setRemoved: (value: boolean) => {
      removed = value;
      icon.classList.toggle('hidden', value);
      void browserApi.local.set(LAUNCHER_REMOVED_KEY, value);
    },
  };
}

// ---------------------------------------------------------------------------
// Selection surface (drag a box around the headline)
// ---------------------------------------------------------------------------

const SELECTION_STYLES = `
  :host { all: initial; }
  * { box-sizing: border-box; }
  .surface {
    position: fixed; inset: 0; cursor: crosshair; user-select: none;
    font: 14px/1.4 system-ui, -apple-system, "Segoe UI", Roboto, sans-serif;
    -webkit-font-smoothing: antialiased;
  }
  .dim { position: fixed; background: rgba(8, 12, 20, 0.55); pointer-events: none; }
  .box {
    position: fixed; display: none; pointer-events: none;
    border: 2px solid ${GOLD}; border-radius: 3px;
    box-shadow: 0 0 0 1px rgba(8, 12, 20, 0.6);
  }
  .banner {
    position: fixed; top: 16px; left: 50%; transform: translateX(-50%);
    max-width: calc(100vw - 32px); padding: 10px 16px; border-radius: 10px;
    background: ${NAVY}; color: ${CREAM}; text-align: center; pointer-events: none;
    box-shadow: 0 6px 24px rgba(0, 0, 0, 0.35);
  }
  .banner strong { display: block; font-size: 15px; font-weight: 600; letter-spacing: 0.01em; }
  .banner span { display: block; font-size: 12.5px; color: ${MUTED}; margin-top: 2px; }
  .banner.warn strong { color: #F2C66D; }
  .toolbar {
    position: fixed; display: none; gap: 8px; padding: 6px; border-radius: 10px;
    background: ${NAVY}; box-shadow: 0 6px 24px rgba(0, 0, 0, 0.35); cursor: default;
  }
  button {
    font: inherit; font-weight: 600; border: 0; border-radius: 7px; padding: 7px 14px;
    cursor: pointer; min-height: 34px;
  }
  button:focus-visible { outline: 2px solid ${GOLD}; outline-offset: 2px; }
  .cancel { background: transparent; color: #E4E8EE; }
  .cancel:hover { background: rgba(255, 255, 255, 0.1); }
  .confirm { background: ${GOLD}; color: ${NAVY}; }
  .confirm:hover { background: ${GOLD_HOVER}; }
`;

function startSelection(onDone: (rect: SelectionRect, viewport: { width: number; height: number }, dpr: number) => void, onCancel: (reason: CancelMessage['reason']) => void) {
  const host = document.createElement('div');
  host.setAttribute('style', 'all: initial; position: fixed; inset: 0; z-index: 2147483647;');
  const root = host.attachShadow({ mode: 'closed' });
  root.innerHTML = `
    <style>${SELECTION_STYLES}</style>
    <div class="surface">
      <div class="dim" data-side="top"></div>
      <div class="dim" data-side="left"></div>
      <div class="dim" data-side="right"></div>
      <div class="dim" data-side="bottom"></div>
      <div class="box"></div>
      <div class="banner" role="status">
        <strong>Select the headline</strong>
        <span>Drag a box around it. Drag again to redo. Esc cancels.</span>
      </div>
      <div class="toolbar" role="toolbar" aria-label="iDIG selection">
        <button class="cancel" type="button">Cancel</button>
        <button class="confirm" type="button">iDIG</button>
      </div>
    </div>`;

  const surface = root.querySelector<HTMLDivElement>('.surface')!;
  const box = root.querySelector<HTMLDivElement>('.box')!;
  const banner = root.querySelector<HTMLDivElement>('.banner')!;
  const bannerTitle = banner.querySelector('strong')!;
  const bannerHint = banner.querySelector('span')!;
  const toolbar = root.querySelector<HTMLDivElement>('.toolbar')!;
  const confirmButton = root.querySelector<HTMLButtonElement>('.confirm')!;
  const cancelButton = root.querySelector<HTMLButtonElement>('.cancel')!;
  const dims = Object.fromEntries(
    [...root.querySelectorAll<HTMLDivElement>('.dim')].map((el) => [el.dataset.side!, el]),
  ) as Record<'top' | 'left' | 'right' | 'bottom', HTMLDivElement>;

  let selection: SelectionRect | null = null;
  let dragStart: { x: number; y: number } | null = null;
  let finished = false;

  function place(el: HTMLElement, x: number, y: number, width: number, height: number) {
    el.style.left = `${x}px`;
    el.style.top = `${y}px`;
    el.style.width = `${Math.max(0, width)}px`;
    el.style.height = `${Math.max(0, height)}px`;
  }

  function render() {
    const vw = window.innerWidth;
    const vh = window.innerHeight;
    if (!selection) {
      place(dims.top, 0, 0, vw, vh);
      for (const side of ['left', 'right', 'bottom'] as const) place(dims[side], 0, 0, 0, 0);
      box.style.display = 'none';
      return;
    }
    const { x, y, width, height } = selection;
    place(dims.top, 0, 0, vw, y);
    place(dims.bottom, 0, y + height, vw, vh - y - height);
    place(dims.left, 0, y, x, height);
    place(dims.right, x + width, y, vw - x - width, height);
    place(box, x - 2, y - 2, width + 4, height + 4);
    box.style.display = 'block';
  }

  function setBanner(title: string, hint: string, warn = false) {
    bannerTitle.textContent = title;
    bannerHint.textContent = hint;
    banner.classList.toggle('warn', warn);
    banner.style.display = 'block';
  }

  function showToolbar(rect: SelectionRect) {
    toolbar.style.display = 'flex';
    const { width: tw, height: th } = toolbar.getBoundingClientRect();
    const gap = 8;
    let top = rect.y + rect.height + gap;
    if (top + th > window.innerHeight - gap) top = rect.y - th - gap;
    if (top < gap) top = rect.y + rect.height - th - gap;
    const left = Math.min(Math.max(gap, rect.x + rect.width - tw), window.innerWidth - tw - gap);
    toolbar.style.left = `${left}px`;
    toolbar.style.top = `${Math.max(gap, top)}px`;
    confirmButton.focus({ preventScroll: true });
  }

  function onPointerDown(event: PointerEvent) {
    if (event.button !== 0 || event.composedPath().includes(toolbar)) return;
    event.preventDefault();
    dragStart = { x: event.clientX, y: event.clientY };
    selection = null;
    toolbar.style.display = 'none';
    banner.style.display = 'none';
    surface.setPointerCapture(event.pointerId);
    render();
  }

  function onPointerMove(event: PointerEvent) {
    if (!dragStart) return;
    const x = Math.max(0, Math.min(dragStart.x, event.clientX));
    const y = Math.max(0, Math.min(dragStart.y, event.clientY));
    const right = Math.min(window.innerWidth, Math.max(dragStart.x, event.clientX));
    const bottom = Math.min(window.innerHeight, Math.max(dragStart.y, event.clientY));
    selection = { x, y, width: right - x, height: bottom - y };
    render();
  }

  function onPointerUp(event: PointerEvent) {
    if (!dragStart) return;
    onPointerMove(event);
    dragStart = null;
    if (!selection || selection.width < MIN_SELECTION.width || selection.height < MIN_SELECTION.height) {
      selection = null;
      render();
      setBanner('Please select the headline.', 'Drag a box around the headline text.', true);
      return;
    }
    showToolbar(selection);
  }

  function onKeyDown(event: KeyboardEvent) {
    if (event.key === 'Escape') {
      event.preventDefault();
      event.stopPropagation();
      cancel('user');
    } else if (event.key === 'Enter' && selection && !dragStart) {
      event.preventDefault();
      event.stopPropagation();
      void confirm();
    }
  }

  const onScroll = () => cancel('scroll');
  const onResize = () => cancel('resize');

  function teardown() {
    finished = true;
    window.removeEventListener('keydown', onKeyDown, true);
    window.removeEventListener('scroll', onScroll, true);
    window.removeEventListener('resize', onResize);
    host.remove();
  }

  function cancel(reason: CancelMessage['reason']) {
    if (finished) return;
    teardown();
    onCancel(reason);
  }

  async function confirm() {
    if (finished || !selection) return;
    const rect = selection;
    const viewport = { width: window.innerWidth, height: window.innerHeight };
    const dpr = window.devicePixelRatio;
    // Remove the overlay and let the page repaint before the background takes
    // its screenshot, so none of the overlay ends up in the capture.
    teardown();
    await new Promise<void>((resolve) => requestAnimationFrame(() => requestAnimationFrame(() => resolve())));
    await new Promise((resolve) => setTimeout(resolve, 30));
    onDone(rect, viewport, dpr);
  }

  surface.addEventListener('pointerdown', onPointerDown);
  surface.addEventListener('pointermove', onPointerMove);
  surface.addEventListener('pointerup', onPointerUp);
  surface.addEventListener('pointercancel', () => (dragStart = null));
  cancelButton.addEventListener('click', () => cancel('user'));
  confirmButton.addEventListener('click', () => void confirm());
  window.addEventListener('keydown', onKeyDown, true);
  // Capture phase also catches scrolling inside page elements. Only the
  // viewport is captured, so any scroll invalidates the selection.
  window.addEventListener('scroll', onScroll, { capture: true, passive: true });
  window.addEventListener('resize', onResize);

  render();
  attachHost(host);
}

// ---------------------------------------------------------------------------
// Docked review panel (iframe onto review.html, slides in from the right)
// ---------------------------------------------------------------------------

// Opens at a fixed default width — but the resize handle's ceiling is the
// viewport itself (see setUpPanelResize), not a small fixed max, so it can
// still be dragged out much further. A manual drag overrides this default
// with a fixed px value from then on (PANEL_WIDTH_KEY) — same as the icon's
// own remembered position.
const DEFAULT_PANEL_WIDTH_STYLE = panelWidthStyle(520);
const MIN_PANEL_WIDTH = 320;
const PANEL_WIDTH_KEY = 'idig:panelWidth';

function panelWidthStyle(px: number): string {
  return `min(${px}px, calc(100vw - 32px))`;
}

const PANEL_MARGIN = 16;
const MAX_PANEL_HEIGHT = 728; // 560 + 30%

function createPanelHost() {
  const host = document.createElement('div');
  host.setAttribute('style', 'all: initial; position: fixed; inset: 0; z-index: 2147483646; pointer-events: none;');
  const root = host.attachShadow({ mode: 'closed' });
  root.innerHTML = `
    <style>
      :host { all: initial; }
      * { box-sizing: border-box; }
      .scrim {
        position: fixed; inset: 0; background: rgba(8, 12, 20, 0);
        transition: background 0.25s ease; pointer-events: none;
      }
      .scrim.open { background: rgba(8, 12, 20, 0.25); pointer-events: auto; }
      .panel {
        position: fixed; right: ${PANEL_RIGHT_OFFSET}px;
        width: ${DEFAULT_PANEL_WIDTH_STYLE};
        border-radius: 18px;
        transform: translateX(calc(100% + 32px));
        transition: transform 0.32s cubic-bezier(0.16, 1, 0.3, 1), top 0.32s cubic-bezier(0.16, 1, 0.3, 1);
        box-shadow: 0 20px 60px rgba(8, 12, 20, 0.45), 0 0 0 1px rgba(217, 180, 90, 0.16);
        pointer-events: auto;
      }
      .panel.open { transform: translateX(0); }
      /* Clips just the iframe to the rounded corners, so the resize notch
         (a sibling, not a child of this) is free to poke past the edge. */
      .panel-inner { width: 100%; height: 100%; overflow: hidden; border-radius: inherit; }
      iframe { width: 100%; height: 100%; border: 0; display: block; }
      .resize-handle {
        position: absolute; top: 0; left: -14px; width: 28px; height: 100%;
        cursor: ew-resize; touch-action: none;
        display: flex; align-items: center; justify-content: center;
      }
      .resize-grip {
        pointer-events: none; letter-spacing: 1px;
        width: 22px; height: 44px; border-radius: 11px;
        display: flex; align-items: center; justify-content: center;
        background: #ffffff; box-shadow: 0 2px 8px rgba(8, 12, 20, 0.28), 0 0 0 1px rgba(20, 35, 58, 0.08);
        color: ${GOLD}; font-size: 12px; font-weight: 700; line-height: 1;
        opacity: 0.85; transition: opacity 0.15s ease, transform 0.15s ease;
      }
      .resize-handle:hover .resize-grip, .resize-handle.dragging .resize-grip {
        opacity: 1; transform: scaleX(1.12);
      }
    </style>
    <div class="scrim"></div>
    <div class="panel">
      <div class="panel-inner"><iframe title="iDIG review"></iframe></div>
      <div class="resize-handle" aria-hidden="true"><span class="resize-grip">&#10094;&#10094;</span></div>
    </div>
  `;
  attachHost(host);
  const panel = root.querySelector<HTMLDivElement>('.panel')!;
  const handle = root.querySelector<HTMLDivElement>('.resize-handle')!;
  setUpPanelResize(panel, handle);

  function reposition(centerY: number) {
    const height = Math.min(MAX_PANEL_HEIGHT, window.innerHeight - PANEL_MARGIN * 2);
    const top = Math.min(
      Math.max(centerY - height / 2, PANEL_MARGIN),
      window.innerHeight - height - PANEL_MARGIN,
    );
    panel.style.height = `${height}px`;
    panel.style.top = `${Math.round(top)}px`;
  }

  return {
    scrim: root.querySelector<HTMLDivElement>('.scrim')!,
    panel,
    iframe: root.querySelector<HTMLIFrameElement>('iframe')!,
    host,
    reposition,
  };
}

function setUpPanelResize(panel: HTMLElement, handle: HTMLElement) {
  let dragStart: { pointerX: number; width: number } | null = null;

  handle.addEventListener('pointerdown', (event) => {
    if (event.button !== 0) return;
    event.preventDefault();
    dragStart = { pointerX: event.clientX, width: panel.getBoundingClientRect().width };
    handle.setPointerCapture(event.pointerId);
    handle.classList.add('dragging');
  });

  handle.addEventListener('pointermove', (event) => {
    if (!dragStart) return;
    // Dragging left (toward the page) widens the panel, which is anchored to the right edge.
    // The ceiling is the viewport itself (minus margins), not a fixed number —
    // otherwise a 75vw default would immediately get clamped down on a wide screen.
    const width = dragStart.width + (dragStart.pointerX - event.clientX);
    const max = window.innerWidth - PANEL_MARGIN * 2;
    panel.style.width = panelWidthStyle(Math.min(max, Math.max(MIN_PANEL_WIDTH, width)));
  });

  function endDrag() {
    if (!dragStart) return;
    dragStart = null;
    handle.classList.remove('dragging');
    void browserApi.local.set(PANEL_WIDTH_KEY, Math.round(panel.getBoundingClientRect().width));
  }
  handle.addEventListener('pointerup', endDrag);
  handle.addEventListener('pointercancel', endDrag);
}

// ---------------------------------------------------------------------------
// Wiring
// ---------------------------------------------------------------------------

function main() {
  let panelHost: ReturnType<typeof createPanelHost> | null = null;
  let selecting = false;

  const launcher = createLauncher(
    () => togglePanel(),
    (centerY) => panelHost?.reposition(centerY),
  );

  // The button on the page toggles the panel (defaults to History if nothing's
  // been snipped yet) and stays visible — and draggable — while it's open, so
  // the panel can stay docked to it. The toolbar icon and the panel's own
  // "+ New snip" button both go straight to a selection instead, closing any
  // open panel first so it isn't in the way while drawing the box.
  function beginSelection() {
    if (selecting) return;
    // Deliberately starting a selection — via the toolbar icon, or "+ New
    // snip" in a panel reached via the toolbar — is a clear "I want this
    // back" signal from someone who'd previously removed the button. Don't
    // make them separately hunt for the toggle afterward.
    if (launcher.isRemoved()) launcher.setRemoved(false);
    if (panelHost) closePanel();
    selecting = true;
    launcher.hide();
    const startUrl = location.href;
    startSelection(
      (rect, viewport, devicePixelRatio) => {
        selecting = false;
        launcher.show();
        browserApi.sendToBackground({ type: 'idig:selection', rect, viewport, devicePixelRatio, url: startUrl });
      },
      (reason) => {
        selecting = false;
        launcher.show();
        browserApi.sendToBackground({ type: 'idig:cancel', reason });
      },
    );
  }

  function togglePanel() {
    if (selecting) return;
    if (panelHost) closePanel();
    else void openPanel({});
  }

  function closePanel() {
    if (!panelHost) return;
    const { scrim, panel, host } = panelHost;
    panelHost = null;
    scrim.classList.remove('open');
    panel.classList.remove('open');
    launcher.setActive(false);
    setTimeout(() => host.remove(), 320);
  }

  async function openPanel(query: Record<string, string>) {
    if (panelHost) closePanel();
    launcher.setActive(true);
    const created = createPanelHost();
    panelHost = created;
    created.reposition(launcher.getCenterY());
    created.iframe.src = browserApi.reviewPanelUrl({ ...query, removed: launcher.isRemoved() ? '1' : '0' });
    created.scrim.addEventListener('click', () => closePanel());
    // The panel is fully off-screen until 'open' is added, so there's time to
    // apply the saved width with no visible jump.
    const savedWidth = await browserApi.local.get<number>(PANEL_WIDTH_KEY).catch(() => undefined);
    if (savedWidth) created.panel.style.width = panelWidthStyle(savedWidth);
    if (panelHost !== created) return; // closed again while we were reading storage
    requestAnimationFrame(() => {
      created.scrim.classList.add('open');
      created.panel.classList.add('open');
    });
  }

  window.addEventListener('message', (event) => {
    if (!panelHost || event.source !== panelHost.iframe.contentWindow) return;
    const type = (event.data as { type?: string } | null)?.type;
    if (type === 'idig:close-panel') closePanel();
    else if (type === 'idig:start-selection-from-panel') beginSelection();
    else if (type === 'idig:remove-launcher') launcher.setRemoved(!launcher.isRemoved());
  });

  browserApi.onBackgroundMessage((message) => {
    if (message.type === 'idig:start-selection') beginSelection();
    else if (message.type === 'idig:show-panel') void openPanel({ ...(message.capture && { capture: message.capture }), ...(message.error && { error: message.error }) });
  });

  // First time ever on any page: show the button, then — once its entrance
  // animation has had a moment to land — open the panel so a brand-new
  // observer sees what the button does without having to guess. Once per
  // install; the flag persists like everything else here.
  browserApi.local
    .get<boolean>(ONBOARDED_KEY)
    .then((onboarded) => {
      if (onboarded) return;
      void browserApi.local.set(ONBOARDED_KEY, true);
      setTimeout(() => {
        if (!launcher.isRemoved()) void openPanel({});
      }, 900);
    })
    .catch(() => {});
}

main();
