# iDIG Exploring — MVP Specification (v3.5)

**Status:** Active spec. Supersedes v3, v2.1 (iDIG Summaries) and the original
ChatGPT-drafted spec (https://chatgpt.com/share/6ab42c60-717c-83e8-9efb-1380824f8c32).
**Revised:** 2026-09-28. **Sprint plan:** [`_sprints/SPRINT_1_Exploring_MVP.md`](_sprints/SPRINT_1_Exploring_MVP.md)
**Evidence:** [`_experiments/`](_experiments/): exp01 (topic trails), exp02 (first question
trails), exp03 (gemini-3.8-flash, one call vs two), exp04 (claim/established/contested shape,
validated live against the real API — see `_experiments/exp04_claims/`).

### What changed in v3.5
- **Trails show an `angle` phrase, not the raw move name (D33, revises D30).** Built and
  validated live in `dev_server/pipeline.py`: real digs now show a short, trail-specific
  phrase ("How a database mismatch actually happens") instead of the category word
  ("MECHANISM"). `move`/`dimension` are unchanged internally — still what `pick()` uses for
  diversity — `angle` is a new, additional field the same call generates, display-only.
- **Real "iDIG Deeper" pipeline built** (`pipeline.py`'s `run_deeper()`): a second grounded
  two-call pass over the 4 shown trails, finding real, cited resources per trail (not the
  hand-written single-headline mock). Supplementary by design — an empty/unverified result
  never blocks the main dig from rendering.
- **Trails carry a closed-vocabulary `pattern` tag: 25 structural/causal patterns, not
  narrative archetypes (D35).** See §7.3a. Built specifically so D34's connector idea has an
  explainable shared tag to match on, not just embedding similarity of free text.
- **Trails-as-connectors, a documented future direction, not built (D34).** See §7.5.

### What changed in v3.4
- **Wonder, a proposed 4th RSD dimension, added as exploratory this-sprint-only (§7.7, D32).**
  Non-resolving, distinct from `unknowns` (epistemic gap vs. permanent open-endedness),
  grounded in Plato's *thaumazein*. **Built entirely inside `exploring_domain/` — nothing in
  `idig_logic_core` is touched.** Verified by reading the actual source: `core/rsd.py`'s
  `RSDVector` and `core/hcs.py`'s interference-harmony/stability-factor math are hardcoded to
  exactly three dimensions, and that code is live under `jobs_manager_domain`,
  `knowledge_center_domain`, and `recruiting_domain` — three working domains with nothing to do
  with Exploring. Movies doesn't import `idig_logic_core` at all yet, so it was never at risk
  either way. Promoting Wonder to core is a deliberate later decision, expected alongside the
  planned Movies-onto-core migration, not a side effect of this sprint.

### What changed in v3.3
- **A new guard: acute personal crisis content (§7.6).** Stress-testing the trail taxonomy
  against a real headline about a named public figure's suicide attempt surfaced a case the
  existing Guards didn't cover: `semantic`/`social` trails about the *practice* (crisis
  intervention, suicide-reporting standards) stay legitimate, but `experiential` trails, any
  future Wonder-dimension trails, and — absolutely, with no exception — the resource/commerce
  enrichment layer (working name **iDIG Deeper**, prototyped in the extension's mock UI, not
  yet built server-side) must be suppressed for content about an identifiable person's private
  crisis. This is specified as a deterministic code-level classifier the worker runs, not a
  prompt instruction a model could be talked out of.
- **AI-disclosure labeling and a real Report action, on every dig, not just `unverified` ones
  (§5.6, §5.7).** Grounding and the `unverified` status (D27) reduce hallucination, they don't
  eliminate it, and a reader has no way to tell a well-grounded claim from one that slipped
  through. Every dig now shows a persistent, visible AI-disclosure line and a **[Report
  this]** action with a real endpoint behind it, not just words next to a disclaimer.
- **D6 reversed:** the icon is now a persistent floating launcher on every page (draggable,
  drops the toolbar-only `activeTab` trigger), not an on-click injection. That requires a
  manifest `content_scripts` entry (matching `http`/`https` pages) and `host_permissions:
  ["<all_urls>"]` instead of just the iDIG API origins — `chrome.tabs.captureVisibleTab`
  specifically requires the literal `<all_urls>` pattern or `activeTab`; broad but scoped
  patterns like `http://*/*` don't satisfy it. A real permission broadening, done
  deliberately so the launcher can start a selection without first going through the toolbar
  icon (§4.2, §4.3, §11).
- **The review step is a docked floating panel**, not a separate popup window: the launcher
  content script opens an iframe onto `review.html`, anchored to the right edge of the page
  with margin on all sides, in place of `chrome.windows.create` (§4.4, §4.5).
- **A History tab, extension-only, local-only** (§4.5): an explicit **[Save]** persists
  `{id, image, url, domain, savedAt}` to `chrome.storage.local`, capped at 24. Cancel and every
  other close path are unchanged — they still discard and save nothing.

### What changed in v3.1
- **§0 North star (new):** what success means, and the principles every other section serves.
- **Trails are questions:** an evergreen question + a grounded hook + a move (D17, §7.3).
- **Headline digs paint context around the claim.** They never give a verdict (D24). Question
  digs lead with evidence, not a short answer (§7.2).
- **Interpretations are always attributed.** The narrator states evidence only (D25).
- **Diversity over popularity:** counts never raise a trail's rank (D26).
- **Search is required:** a dig without search results is marked unverified and never
  cached as trusted (D27).
- **Measure integrity, not engagement** (D28). The observer sets their own lens (D29).
  Trails show why they're there (D30).
- **Model:** gemini-3.x Flash, one call with search + response schema + low thinking (D1, D23).
  gemini-2.5-flash can't combine search with a schema.
- **Data changes:** digs are `headline` or `question`; trails store `move/question/hook`;
  there's a new `unverified` status; grounding counts and flags are stored (§8.1).
- **Loop filter** tightened to 0.85.
- **Demo mode (D31):** only allowlisted IPs can trigger new generation. Everyone else can read
  digs that already exist. **Spending limits (§13.3):** a per-call token cap, at most 2
  attempts per dig, a daily token budget, and a Google-side backstop.

---

## 0. North star

**Success is when an observer feels good about what they learned, at the core of who they
are. Not in service of anyone else, only who they are and who they aspire to be.**

That success happens inside the observer, so the system never tries to measure it or infer
it. The system measures only **its own integrity** (§13). Every design choice serves this:

- **Insight is the part the observer couldn't have predicted.** A path that only confirms
  what someone already thinks teaches nothing. The math favors trails that take the observer
  somewhere new and in a different direction from where they started, which means
  **diversity over popularity**.
- **Invitation, never manipulation.** Once the system optimizes for the observer's reaction
  (clicks, time spent, return visits), it learns to produce the *feeling* of curiosity
  instead of the real thing, and the observer stops exploring and starts defending. Deep
  inquiry can spread on its own merits. It can't be engineered.
- **The payoff always exceeds the hook.** Clickbait opens a gap and doesn't fill it. A trail
  opens a gap and fills it with more than the reader expected.
- **Context, not verdicts.** Exploring paints context around what a headline claims: what's
  established, who disputes what, and what's left out. The reader reaches their own
  conclusion and owns it. Telling someone what to think takes that ownership away.
- **Serve the aspiring self, not the impulsive one.** Engagement systems serve who you are at
  11pm while scrolling. Exploring serves who you're trying to become. Any personal lens is
  set by the observer and stays on their device (D29).
- **Trust is the product** (`idig_logic_core/DISCOVERY_ARTIFACT_PROTOCOL.md`). No
  pay-to-play, no opaque ranking, no hidden objective.

## 1. What this is

A browser extension plus an iDIG lens at `i-dig.io/exploring`, where the URL reads
**"I dig exploring."** The observer sees a headline on any page, clicks iDIG, snips the
headline, confirms the text, and lands on a **headline dig**: the context around what the
headline claims, plus **four trails**. Each trail is a deep, evergreen **question**. Following
one opens a **question dig** that answers it with evidence and offers four more questions.
The headline is the trailhead. Each step moves from the news toward the ideas underneath it.

> I see something interesting → I dig it → I keep digging.

The extension handles the browser interaction. iDIG (core/domains) does the research, and
`idig_logic_core` picks the trails. The extension never scrapes. The only content it sends is
the text the observer deliberately selected and confirmed, plus the URL it came from.

**There's no login.** Research is shared and anonymous on the server. Each observer's
history lives only on their own device (§9).

Later, Exploring becomes the way into the other iDIG domains (doors, §12).

### Vocabulary

| Term | Meaning |
|---|---|
| **Snip** | One observer capturing one headline. Holds their source URL. Never merged with anyone else's. |
| **Dig** | One piece of grounded research, shared by everyone who reaches it. It's either a **headline dig** (context around a news claim; fresh ~36 h) or a **question dig** (an evidence-based answer to an evergreen question; fresh ~7 days). |
| **Claim** | What a headline states or implies, restated in neutral words. |
| **Trail** | A way deeper: a **question** (the enduring puzzle beneath the story) + a **hook** (a grounded fact that makes it urgent now) + a **move** + a **dimension** + a search **seed**. |
| **Move** | The kind of question: tension, mechanism, precedent, frame, stakes, hidden, scale, unknowns (§7.3). |
| **Dimension** | The three RSD dimensions from `idig_logic_core`: **semantic** (mechanism, precedent, scale), **experiential** (stakes, life under it), **social** (tension, frame, hidden actors). *Plus a 4th under proposal, local to this domain only: **Wonder** — non-resolving, not instrumental (§7.7, D32).* |
| **Path** | The **ordered** sequence of digs an observer follows. Order matters: reading precedent then stakes leaves a different understanding than stakes then precedent. |
| **Archive** | The observer's own history of paths, saved automatically in IndexedDB on their device. |

## 2. Decisions

### Carried over (some revised)

| # | Decision | Why |
|---|---|---|
| D1 | **The server researches. It never summarizes the source article.** *(v3.1: the model is **gemini-3.x Flash** (gemini-3.8-flash as of 2026-09-23), with Google Search grounding and a response schema **in one call**, `thinking_level="low"`. That call writes the dig **and** the trail candidates.)* | A headline alone is too thin to summarize honestly, and fetching `source_url` would bring back the scraping/paywall problem. exp02 showed gemini-2.5-flash rejects search + a JSON schema together. exp03 showed one 3.8-flash call gives the best trails at ~2,000 tokens per dig, and a second "question writer" call cost 2–3× more for weaker hooks. |
| D2 | **The backend lives in `iDIGcore_w_domains`,** not in this folder. | Logic stays separate from features. |
| D3 | **Reuse the existing core Supabase project.** New Postgres schema: `exploring`. | No new projects. Schema-per-domain matches `knowledge_center`. |
| D4 | **The logic goes in `idig_lc_domains/exploring_domain/`,** a Python watcher like `recruiting_domain/run.py`. Matching, research, guards and trail selection all happen in the worker. | Keeps the logic next to `idig_logic_core`, which does the trail math. |
| D5 | **The web surface is its own Next.js app, `iDIGcore_w_domains/exploring_app/`, mounted at `i-dig.io/exploring` like `/movies`** (§4.8). | A Next app has one `basePath`, and `knowledge_center_app` already has its own. |
| D6 | *(v3.2: reversed — see below)* ~~Permissions: `activeTab` + `scripting` + `storage`, host permissions only for iDIG API origins. Never `<all_urls>`, and no persistent content scripts.~~ **Now:** `storage` only, plus `host_permissions: ["<all_urls>"]` and a persistent `content_scripts` entry matching `http`/`https` pages (§4.2). | The floating launcher (§4.3) must be present on every page and start a selection from its own click, not just from the toolbar icon. That can't be done with a per-click `activeTab` grant, and `chrome.tabs.captureVisibleTab` specifically requires the literal `<all_urls>` pattern (or `activeTab`) — scoped patterns like `http://*/*` don't satisfy it. |
| D7 | **Selection is adjusted by redrawing,** not by resize handles. | Simpler, and enough for headlines. |
| D8 | **OCR uses Tesseract.js, bundled locally, running in an extension page.** | MV3 forbids remote code. Page CSP can break WASM in content scripts. |
| D9 | **The full screenshot never leaves the background worker.** The crop is never sent to the server. | Minimum data. |
| D10 | **Snip, dig and trail IDs are UUIDs.** | Nobody can walk through IDs to find other people's snips. |
| D11 | **The worker never fetches `source_url`.** Resolving a grounding redirect reads only its `Location` header and never visits the target (§7.6). | Paywall and publisher rules. (exp01: CNN returned 451 to a fetch anyway.) |
| D12 | **Browsers:** Chrome first, Edge and Brave checked, Safari later. DuckDuckGo dropped. | |
| D13 | **Named iDIG Exploring.** Everything uses `exploring`. | The URL finishes "I dig ___." |
| D14 | **Snips and digs are separate records. Many snips share one dig.** | Research is the expensive part, so share it (§6). |
| D15 | **Matching ladder:** exact hash → near (embedding) → gray-zone yes/no check → new. `match_type` is recorded. | Catches rewordings without merging different events. |
| D16 | **Three cost rules:** (1) viewing never generates; (2) generated text is the same for every observer and doesn't depend on the path; (3) generation needs a deliberate action and is rate-limited. | Cost grows with new research, not with traffic. |
| D17 | **Trails are questions.** *(v3.1)* The research call returns **8** candidates `{move, dimension, pattern, angle, question, hook, seed}` *(`pattern` and `angle` added v3.5, D33/D35 — reader-facing/connector fields; see D33, D35)*, at least 2 per dimension and at least 6 different moves, written to the question-craft rules (§7.3). Core shows **4**: the best per dimension, the 4th by MMR, **all 4 moves distinct**, and nothing that loops back to the path (§7.5). All 8 are stored. | exp03: question trails were far deeper than topic trails (exp01) at the same token cost. An evergreen question is reusable across headlines, and the hook makes it urgent now. |
| D18 | **Question digs are neutral and evergreen.** The hook, written by the parent call, carries the connection to the story. The question dig answers the question on its own terms and is cached by question, so every path that reaches the same question shares it. | Reuse across paths and headlines. The deepest digs become the most shared. |
| D19 | **Fixed-size context:** the root headline, the path's question titles, and the question with its seed. Never earlier digs' full text. | Step six costs about what step one did (exp01: 1,891 vs 1,996 tokens). |
| D20 | **No login. The archive is saved automatically on the device** (IndexedDB, export/import), modeled on Movies' `useSavedFilms.ts`. The extension stays stateless. | Privacy is part of the product. No friction to start. |
| D21 | **Rate limits use no identity:** a hashed IP with a daily count, plus a global hourly cap. Only new generations count. | Normal explorers never hit it. |
| D22 | **Each snip gets a delete token.** Only its hash is stored, and the token lives in the observer's archive. | Ownership without accounts. |
| D23 | **Bounded output.** *(v3.1)* Response schema, length guidance per field, `thinking_level="low"`, sources from grounding metadata only (cited chunks, top 5), token counts stored. **No word limit on questions:** compression pushed the model toward verdicts and subjectivity. | exp03: "low" used 0 thinking tokens on research. A single clean dig is ~2,000 tokens. |

### New in v3.1

| # | Decision | Why |
|---|---|---|
| D24 | **Headline digs paint context around the claim and never give a verdict.** The structure is: the claim (neutral) → what happened → why now → **established** (what independent sources agree on) → **contested** (attributed positions) → **left out** (context the headline omits that changes how the claim reads) → still unknown. There's no true/false/misleading label. | Verdicts are where perspective creeps in, and they take ownership away from the reader. Separating what's agreed from what's disputed lets the evidence speak. It's close to fact-checking, but without a referee. |
| D25 | **Interpretations are always attributed. The narrator states evidence only.** Every judgment is tied to who holds it (`held_by`). Loaded words in the narrator's voice ("theatrical," "grandstanding," "posturing," "slammed," …) are flagged by a zero-token word check in the worker, retried once, and stored with a flag if they persist (§7.6). | exp03's answers had real substance but still leaned ("virtually never… theatrical threats… domestic posturing"). A "be neutral" instruction isn't enough, so neutrality comes from structure plus a check. |
| D26 | **Diversity over popularity.** `follow_count` and `snip_count` are shown for transparency ("12 explorers dug this") but **never raise a trail's rank**. Selection favors trails that are complementary to each other (§7.5). Later, one slot is reserved for a **road less traveled**: a strong candidate few observers have taken (§12). | Popularity feeds on itself and keeps people inside what they already think. Insight comes from directions the observer wouldn't have picked. |
| D27 | **Search is required.** A grounded call that returns **0 search queries or 0 cited sources** is retried once. If it fails again, the dig gets status `unverified`. It's shown with a notice, never matched or reused by the cache, and re-researched on the next request. | exp03: gemini-3.x decides whether to search, and skipped it in 2 of 8 calls while still producing specific 2026 claims we couldn't verify. |
| D28 | **The system measures its integrity, never engagement.** It tracks grounding rate, unverified rate, loaded-word flags, path diversity, and whether the payoff exceeds the hook (reviewed by a person). It **never** tracks or optimizes time on site, return visits, scroll depth or streaks (§13). | Success belongs to the observer (§0). Optimizing for reactions is exactly what destroys trust. |
| D29 | **Any personal lens is set by the observer, on their device.** For example: "show me the history behind things," "show me how other countries see it," "push me toward what I don't usually read." It re-ranks the stored candidates in the browser. Nothing is inferred silently. History-based suggestions are only shown to the observer, and used only if they turn them on. | It serves the observer's aspirations, not their predicted impulses. The server never learns it. |
| D30 | **Trails show why they're there.** *(v3.5: revised — see D33.)* ~~Each shows its move ("precedent," "tension," …).~~ **"More trails"** reveals the other stored candidates at no token cost. | Transparency is the line between invitation and manipulation. |
| D31 | **Demo mode: only allowlisted IPs can generate.** While `EXPLORING_DEMO_MODE=on` (the default), the web app's POST routes allow new generation only from IPs in `EXPLORING_ALLOWED_IPS` (a comma-separated list; CIDR allowed, e.g. an IPv6 `/64`), plus localhost. Other visitors can open existing digs and follow **already-dug** trails, which costs nothing. Anything that would generate gets `403`. The gate **fails closed**: if the real IP can't be determined, it's blocked. | A public demo can't run up a bill faster than a Gemini budget alert can be seen. Shared links still work, so the demo can be shown to people. It's turned off only after the public limits (§8.4, §13.3) have been proven in practice. |
| D32 | **The Wonder dimension (§7.7) is built entirely inside `exploring_domain/` this sprint — nothing in `idig_logic_core` is touched.** No new field on `core/rsd.py`'s `RSDVector`, no edit to `core/hcs.py`'s `DIMS` tuple or its interference-harmony/stability-factor math. Exploring's own dimension/move handling stays local code, not an import from core. | Verified by reading the actual source, not assuming from the design docs: `RSDVector` hardcodes exactly three fields and `validate_rsd_extraction` hardcodes that exact tuple; `hcs.py`'s "Interference Harmony" and "Stability Factor" are hand-written for exactly three pairwise comparisons (`s_emb, e_emb, soc_emb`, `/3.0` divisors), not a loop over however many dimensions exist. That shared code is live under `jobs_manager_domain`, `knowledge_center_domain`, and `recruiting_domain` today. Movies doesn't import `idig_logic_core` at all yet (confirmed: zero hits repo-wide), so it isn't at risk from an Exploring-only change — but three other working domains are, and Wonder is still unproven past two hand-built examples. Promoting Wonder to core is a deliberate, later decision — expected after this sprint's testing, timed with Paul's planned migration of Movies onto core/domains — not a side effect of building it for Exploring now. |

### New in v3.5

| # | Decision | Why |
|---|---|---|
| D33 | **Trails carry a new `angle` field — a short, trail-specific phrase (4-8 words) — shown as the visible label instead of the raw `move` name. Revises D30.** `move`/`dimension` are unchanged and still drive `pick()`'s diversity selection (§7.5); `angle` rides alongside as a sixth field in the same trail object, generated by the same call, display-only. | Showing the taxonomy word itself ("MECHANISM," "TENSION") undersold the actual question underneath it — a fixed category name can't capture what makes *this specific* trail worth following. Built and validated live: `pipeline.py`'s `QUESTION_CRAFT` now asks for the angle explicitly, with weak/strong calibration examples, and it produces genuinely specific phrases ("How a database mismatch actually happens," "Who actually makes the final call") rather than restating the move or the question. |
| D34 | **Trails as connectors between digs — a documented future direction, not built.** When a new trail shares its `pattern` tag (D35) with a trail already stored under a *different* headline's dig, surface that as a link ("this question also came up digging into: ___"), narrowed by embedding similarity within that shared tag rather than embedding similarity alone. Needs a persistent trail store (Supabase, `exploring.trails` with `pattern` and an embedding column) and a query at dig-creation time. | This was the original premise for iDIG Exploring — "trails, doors into other domains" — not a new idea. `pick()` already embeds every candidate trail to score relevance; the raw material exists for one dig's lifetime and is currently discarded. The blocker is persistence, not the math: the current dev server (`dev_server/`) is in-memory only and has no `exploring.digs`/`exploring.trails` schema live yet (§8 describes the intended schema; it isn't provisioned). Do this after Sprint 1's real backend (Supabase, the worker, the demo gate) exists — building cross-dig matching on top of an in-memory prototype would mean rebuilding it twice. |
| D35 | **Trails carry a closed-vocabulary `pattern` tag: one of 25 structural/causal patterns (§7.3a), not a narrative archetype.** Built now, ahead of D34, specifically so a future cross-dig connection is an explainable shared tag ("both are **Function Creep**") rather than a coincidental embedding-similarity match on free text. | Tried narrative archetypes first ("Maverick vs. The System," modeled on Movies' hand-picked trails) and rejected them: Movies' trails were hand-authored per film, but Exploring has to classify any headline automatically, and a real test case (a college-football-playoff dig) produced an angle so specific to that story's own numbers ("How 12-team math rewrites at-large bids") that it could never plausibly match a different story — which is exactly the failure D34 needs to avoid. A structural pattern names the mechanism, not the players, so it transfers: a voter-database story and a corporate-ESG story can both be **Function Creep** despite sharing nothing narratively. |

## 3. User flow

```
[icon click] → overlay: "Select the headline"
   drag rectangle (drag again to redraw) → [Cancel] [iDIG]      Esc = cancel
[iDIG] → background captures visible tab → crops → opens Review window
Review window: OCR runs → "Is this what you want to dig into?"
   editable headline · source domain · [Send to iDIG]
[Send] → POST /exploring/api/snips → { id, delete_token } → new tab: /exploring/{id}#t={token}
/exploring/{id}: saves itself to the archive, removes #t from the URL
   source link at top → headline → "Digging…" (or instant, if cached)
   → the claim · what happened · why now · established · contested (attributed) · left out
     · still unknown · sources
   → 4 question trails (each: move label · question · hook) · [More trails]
[trail click] → POST /exploring/api/trails/{id}/follow
   cached → /exploring/d/{dig_id}
   not cached → "Digging…" → /exploring/d/{dig_id}
/exploring/d/{dig_id}: the question → what the evidence shows → evidence → how it's
   interpreted (attributed) → still open → sources → 4 new questions · breadcrumb of the path
   (each dig opened is added to the archive automatically, in order)
```

## 4. Extension

Revised in v3.2: a persistent floating launcher replaces the toolbar-only trigger, and the
review step is a docked floating panel instead of a separate popup window.

### 4.1 Layout (this folder)

```
idig_exploring/
├── SPEC.md                       ← this file
├── _sprints/
├── _experiments/                 exp01–03: scripts, raw results, reports
├── extension/
│   ├── public/manifest.json      static MV3 manifest
│   ├── package.json · tsconfig.json · vite.config.ts · vite.content.config.ts
│   ├── .env.development          VITE_IDIG_API_URL=http://localhost:3003
│   ├── .env.production           VITE_IDIG_API_URL=https://i-dig.io
│   ├── public/ocr/               tesseract worker + core wasm + eng.traineddata
│   └── src/
│       ├── config.ts             the ONLY place the API URL is read
│       ├── types.ts              Payload, Capture, message types
│       ├── browser/
│       │   ├── abstraction.ts    interface: captureVisibleTab, tab messaging, storage
│       │   └── chrome.ts         Chrome implementation
│       ├── background/background.ts
│       ├── content/launcher.ts   persistent: floating icon + selection surface + docked panel
│       ├── review/               review.html · review.ts · review.css (loaded in the panel's iframe)
│       ├── ocr/ocr.ts
│       └── api/idig.ts
└── README.md                     install + dev instructions
```

Only `src/browser/chrome.ts` may call `chrome.*`. Everything else goes through
`abstraction.ts`.

### 4.2 Manifest essentials

```json
{
  "manifest_version": 3,
  "name": "iDIG Exploring",
  "permissions": ["storage"],
  "host_permissions": ["<all_urls>"],
  "content_scripts": [{ "matches": ["http://*/*", "https://*/*"], "js": ["launcher.js"], "run_at": "document_idle" }],
  "background": { "service_worker": "background.js", "type": "module" },
  "action": { "default_title": "iDIG — select something you dig" }
}
```

`launcher.js` (built from `content/launcher.ts`) is declared in `content_scripts`, so it
runs on every top-level `http`/`https` page without a click first — that's what makes the
floating icon persistent (§4.3). Because `host_permissions` now covers all origins, the
background can still `captureVisibleTab` and message any tab even though the click that
started a selection happened in a content script, not on the toolbar icon (which no longer
grants a fresh `activeTab` scope here). Extension-page fetches to the iDIG API origins skip
CORS as before, so the server needs no CORS config.

### 4.3 Floating launcher + selection surface (`content/launcher.ts`)

- **Launcher icon:** a rounded-square button pinned to the right edge of the page, present on
  every page via the persistent content script. Dragging it vertically repositions it
  (position saved as a 0–1 fraction of viewport height in `chrome.storage.local`, so it's
  remembered across pages and restarts).
- *(v3.2)* A plain click (no drag) **toggles the docked panel** (§4.5) open or closed — it
  does not start a selection directly. With nothing snipped yet, the panel opens to its
  History tab, so History is reachable without snipping first. The panel's own **[+ New
  snip]** button starts a selection, closing the panel first so it isn't in the way of the
  headline. The toolbar action button keeps the old one-click-to-selection behavior instead,
  for a faster path that skips the panel; if a panel happens to be open when it's clicked,
  that panel is closed first.
- **Selection surface:** unchanged from v3's overlay — a fixed full-viewport host with a
  **closed Shadow DOM**, so page CSS can't reach it and it can't leak into the page. It
  removes itself completely on cancel or confirm, leaving no residue.
- Instruction banner: **"Select the headline"**.
- Dragging draws a rectangle with a visible border. Everything outside it is dimmed (four
  dim panels; don't dim the rect itself).
- Dragging again replaces the rectangle. [Cancel] and [iDIG] appear next to the rectangle.
  Esc cancels.
- Minimum size is **24×12 CSS px**. Anything smaller shows "Please select the headline."
  Nothing ever auto-detects the headline.
- On confirm, the surface is **hidden first**, then it sends `{rect (CSS px,
  viewport-relative), devicePixelRatio, url}` to the background, so the surface isn't in the
  capture. `url` is `location.href` read when the selection started, in case an SPA
  navigates mid-drag.
- If the page scrolls while selecting, cancel the selection. Only the viewport is captured.

### 4.4 Capture and crop (`background.ts`)

1. `captureVisibleTab` gives a PNG data URL, then `createImageBitmap`.
2. Scale the rect by `devicePixelRatio`, which already includes page zoom. Clamp to the
   bitmap bounds. Crop with `OffscreenCanvas`.
3. Put the crop (PNG data URL) and `{url, domain}` in `chrome.storage.session` under a
   capture id. Drop the full bitmap.
4. Message the tab's launcher content script (`idig:show-panel`, `{capture: <id>}`), which
   opens the docked panel (§4.5). The background never opens a window itself.

`domain` is `new URL(selection.url).hostname` with any leading `www.` removed. Nothing else
is read from the page: no title, no meta, no DOM.

**Unsupported pages** are `chrome://`, `edge://`, `about:`, the Chrome Web Store, `file://`
(unless allowed) and the PDF viewer — the manifest's content script never runs there, so
there's no launcher to message. For these the extension must still say so: set the action
badge to "!". It must never fail silently, even though (unlike v3) there's no window it can
open on such a page to show the error text in.

### 4.5 Review panel (`review/`, docked by `content/launcher.ts`)

- *(v3.2)* The launcher icon **stays visible (and draggable) while the panel is open**,
  instead of hiding — the two are visually docked: the panel's right edge butts up flush
  against the icon's left edge with no gap between them (`PANEL_RIGHT_OFFSET` in
  `launcher.ts` is derived from the icon's own width and margin, so this stays true if the
  icon's size changes), and the panel's vertical position tracks the icon's center (height
  capped at 560px, clamped to the viewport). Dragging the icon while the panel is open moves
  the panel with it in real time. The icon itself sits close against the right edge (4px),
  near the browser's scrollbar. The toolbar-triggered flow and `beginSelection` still hide
  the icon outright, since a
  visible icon over the page would be distracting mid-drag-select.
- A resize handle on the panel's left edge lets the observer drag it wider (320–720px,
  default 400), clamped to fit the viewport. The width is saved to `chrome.storage.local`
  (`idig:panelWidth`) and reapplied — while the panel is still off-screen, so there's no
  visible jump — the next time it opens.
- The launcher opens a floating panel anchored to the right edge of the page (margin on all
  sides, rounded corners, slide-in animation) containing an `<iframe>` onto the extension's
  own `review/review.html?capture=<id>`. The page inside is unchanged from v3 — same
  `chrome.storage.session` read, same UI — it just renders in a docked iframe instead of a
  separate popup window.
- It shows the cropped image, which also confirms the selection was right.
- It runs OCR with a status line ("Reading headline…").
- Heading: **"Is this what you want to dig into?"**
- Editable headline field: a textarea with whitespace and line breaks collapsed, trimmed,
  and at most 300 chars.
- It shows the source domain, with the full URL as a clickable link (opens in a new tab) and
  tooltip.
- Buttons: **[Send to iDIG]** and **[Cancel]**, where Cancel discards the session entry and
  asks the launcher (via `postMessage`, since an iframe can't call `window.close()`) to slide
  the panel closed. Removing the iframe this way still fires its `pagehide` handler, so a
  scrim click or a page navigation discards the capture the same way.
- If OCR fails or returns fewer than 3 characters, show **"We couldn't read the
  headline."** and focus an empty field for typing it in by hand.

**History tab (added in v3.2, extension-only):** losing the popup window's own OS window also
lost its incidental "reopen a snip you minimized" behavior (it had a taskbar entry; a docked
panel doesn't). The panel now has two tabs, **Snip** and **History**. History is a plain list
in `chrome.storage.local` (`HistoryEntry[]`, capped at 24, newest first), written **only** by
an explicit **[Save]** button next to Cancel — Cancel and every other close path still discard
the pending capture immediately and write nothing, so the "stores nothing after cancel" claim
in §11 holds for anything not deliberately saved. Each entry is just `{id, image, url, domain,
savedAt}`: the crop, the source, and when it was saved — nothing richer, since there's no dig
content to show yet (Phase D/E). This is a separate, smaller thing from the web app's archive
in §9 (which will hold full paths through digs, in IndexedDB, once Phase D exists) — the two
may end up merging once the web app exists, but for now this is just "don't lose the crop."
The tab bar also carries a **[+ New snip]** button (visible whenever tabs are, i.e. whenever
the panel is open), and opening the panel with nothing pending (§4.3) hides the Snip tab and
defaults straight to History rather than showing a false "expired" error.

**Opting out (D6 needs this):** broadening to a persistent, all-pages launcher (D6) means an
observer who doesn't want it on-page needs an easy way to say so. The tab bar's **[Remove
button]** sets `idig:launcherRemoved` in `chrome.storage.local`, checked by `launcher.ts`
before it ever reveals the icon on a page; `show()` (called after every transient hide, e.g.
after a selection) respects it — a no-op while removed, so nothing accidentally undoes the
choice. **This is a real toggle, not one-way** — the button relabels to **[Show button]**
once removed. *(Corrected after testing: removing and re-adding the unpacked extension does
**not** reliably clear `chrome.storage.local` in Chrome — confirmed empirically, the flag
survived a real remove-and-reinstall. Only manually clearing storage from DevTools did, which
an observer can't do. So reinstall can't be the recovery path; the in-panel toggle, reachable
via the toolbar icon, is the only thing that actually works.)* `beginSelection()` also clears
`idig:launcherRemoved` itself, the moment a selection actually starts (toolbar icon, or a
panel's own **[+ New snip]**) — deliberately re-engaging with iDIG at all is already a clear
"I want this back" signal, so restoring the button doesn't wait on someone separately finding
the in-panel toggle afterward.

**First-run onboarding:** a brand-new observer has no reason to know the button opens
anything. The first time `launcher.ts` ever runs (`idig:onboarded` unset in
`chrome.storage.local`), it shows the button, waits ~900ms for its entrance animation to
land, then opens the panel itself (History tab, since nothing's been snipped) — so the
button-to-panel connection is obvious without anyone having to guess to click it. Marked
`true` after the first run regardless of outcome, so it only ever fires once per install.
Skipped if the button was already removed by then (unlikely at first run, but checked).

**Export / Import:** `chrome.storage.local` — like everything else an extension stores — is
wiped when the extension is removed, even if reinstalled from the same folder right after.
That's a browser-enforced privacy guarantee, not something an extension can opt out of. The
only way History data outlives a removal is leaving `chrome.storage.local` entirely: History
has **[Export]** (downloads the current list as a timestamped `.json`) and **[Import]** (reads
one back in, merging by `id` — an entry from the file wins over one already stored with the
same id — newest `savedAt` first, still capped at 24). Export always saves to the same
`Downloads/iDIG Exploring/` subfolder (needs the `downloads` permission — a plain `<a
download>` link can't target a folder, only `chrome.downloads.download({filename})` can).
Import can't be pointed at that folder the same way: no browser API lets a page or extension
set a file picker's starting directory, since that would let arbitrary sites probe a user's
filesystem layout. In practice Chrome's picker tends to reopen on the last folder the person
used, so this is mostly self-solving after the first import — but it's the browser doing
that, not something this extension controls.

### 4.6 OCR (`ocr/ocr.ts`)

- Tesseract.js v5 with `workerPath`, `corePath` and `langPath` all pointing at
  `chrome.runtime.getURL("ocr/…")`. Nothing loads from a CDN.
- Preprocess before OCR: upscale small crops so text height is at least about 40px, then
  convert to grayscale. Use page segmentation mode 6 (a single block of text).
- The interface is `recognize(image): Promise<{text, confidence}>`, so the engine can be
  swapped later.

### 4.7 API client and dev fallback (`api/idig.ts`)

- `POST {API}/exploring/api/snips` with the payload in §5.1 and an 8s timeout. `{API}` is
  always just the origin (`https://i-dig.io` or `http://localhost:3003`).
- On `201 {id, delete_token}`, open `{API}/exploring/{id}#t={delete_token}` in a new tab and
  close the review window. The token goes in the URL **fragment**, which browsers never send
  to the server. The page saves it to the archive and removes it (§9.3). The extension
  keeps nothing.
- On a network error, timeout or 5xx: fallback mode with the headline, URL, "● iDIG
  unavailable", **[Copy payload]** and **[Retry]**. On a 4xx (including 429), show the
  server's message.

### 4.8 URL model: mounted like `/movies`

How Movies works today, which Exploring copies:

1. **The apex project** (`idig_website_new-build`, which serves i-dig.io) proxies the path
   prefix to a separate Vercel deployment in its `vercel.json` rewrites, **before** the SPA
   catch-all:
   ```json
   { "source": "/movies",        "destination": "https://idig-movies-production-demo.vercel.app/movies" },
   { "source": "/movies/:path*", "destination": "https://idig-movies-production-demo.vercel.app/movies/:path*" },
   ```
   The lowercase and `/Movies` capitalized forms are both listed.
2. **The feature app knows its prefix.** Movies (Vite) sets `base: '/movies/'` and sends
   every runtime URL through `withBase()`.
3. **The apex SPA doesn't route the path.** `App.tsx` and `NavBar.tsx` treat `/movies` as an
   external link.

For Exploring, add these four rewrites to `idig_website_new-build/vercel.json`, above
`"/(.*)"`:

```json
{ "source": "/Exploring",        "destination": "https://<exploring-app>.vercel.app/exploring" },
{ "source": "/Exploring/:path*", "destination": "https://<exploring-app>.vercel.app/exploring/:path*" },
{ "source": "/exploring",        "destination": "https://<exploring-app>.vercel.app/exploring" },
{ "source": "/exploring/:path*", "destination": "https://<exploring-app>.vercel.app/exploring/:path*" }
```

In `exploring_app`, set `basePath: "/exploring"` using the same `NEXT_PUBLIC_BASE_PATH`
mechanism as `knowledge_center_app/next.config.ts`. Next applies the basePath to pages,
`_next` assets and route handlers, so there's **no** `withBase()` equivalent.

Locally, `exploring_app` runs on **port 3003** with `NEXT_PUBLIC_BASE_PATH=/exploring`
(`localhost:3003/exploring/{id}`). Other ports in use: Movies UI 3002, Movies API 3001,
`knowledge_center_app` 3000.

Security headers follow Movies' `vercel.json`: `nosniff`, `frame-ancestors 'none'`, a CSP
with `connect-src 'self'`, and a Referrer-Policy.

**Verify through the proxy:** the rate limit (§8.4) needs the observer's real IP. Check that
proxied requests carry it in `x-forwarded-for` / `x-real-ip`. If they don't, only the global
cap applies until that's fixed.

### 4.9 States

`IDLE → SELECTING → CAPTURED → OCR_PROCESSING → REVIEW → SUBMITTING → COMPLETE`, plus
`ERROR`. Every state can return to `IDLE` by Cancel, Esc or closing the window. No state
machine library.

## 5. Contract

All paths are under the `/exploring` basePath. **Every GET is read-only and never triggers
generation** (D16).

### 5.1 `POST /exploring/api/snips` (from the extension)

```json
{
  "headline": "Major TV Networks Halt Video Coverage of Trump Over CNN Ban",
  "source_url": "https://example.com/article",
  "source_domain": "example.com",
  "captured_at": "2026-09-21T17:30:00Z",
  "source": "idig-browser-extension"
}
```

Validation: `headline` 3–300 chars after trimming; `source_url` http(s), ≤ 2048 chars;
`source_domain` matches the URL's hostname (ignoring `www.`); `source` from an allowlist.

Response: `201 {"id": "<snip uuid>", "status": "received", "delete_token": "<token>"}`, or
`400`/`403`/`429 {"error": "…"}`. **The demo gate runs first (D31):** a non-allowlisted IP
gets `403 {"error": "iDIG Exploring is in private demo. New digs are limited."}` and nothing is
saved. The route only saves the snip with its `rate_key` (§8.4). It answers 429 when the global
hourly cap or the daily token budget (§13.3) is full. The worker does the matching and the
per-IP check.

### 5.2 `GET /exploring/api/snips/{id}`

`{status, match_type, dig: <dig object>}`. Polled every 3s while the snip is `received` or
its dig is `queued`/`researching`.

### 5.3 `GET /exploring/api/digs/{id}`

The dig object:
`{id, kind, status, result, sources, coverage, snip_count, follow_count, researched_at, trails: [4 shown], more_trails: [the other stored candidates]}`.
`kind` is `headline` or `question`. `status` can be `unverified` (D27), and the page then
shows: *"We couldn't confirm this against search results. Treat it with care."*

### 5.4 `POST /exploring/api/trails/{id}/follow` (from a trail click)

- A current, fresh, `ready` child dig exists → `200 {"dig_id": "…"}` and `follow_count` goes
  up. That costs nothing.
- Otherwise, **if the demo gate allows this IP (D31)**, it marks the trail `requested` (a
  conditional update) and returns `202 {"status": "requested"}`. The page polls
  `GET /exploring/api/trails/{id}`. If the gate doesn't allow it, it returns `403` with the
  demo message, and the page shows it next to the trail.

A trail object: `{id, move, dimension, question, hook, rank, child_dig_id, follow_count}`.
`seed` and `embedding` never leave the server.

### 5.5 `DELETE /exploring/api/snips/{id}` (Sprint 2)

Header `X-Delete-Token: <token>`. It compares hashes, deletes the snip and decrements
`snip_count`. The shared dig stays.

### 5.6 `POST /exploring/api/digs/{id}/report`

A real action behind the AI-disclosure label (§5.7), not just words next to it. Body:
`{"reason"?: "inaccurate" | "concerning" | "broken_link" | "other"}`. Response: `204`.
Increments `report_count` on the dig (§8.1). **Not behind the demo gate (D31)** — that gate
limits *new generation*, and flagging a problem with something already generated should never
require allowlist access. Rate-limited per IP the same way other routes are, so reporting
can't itself become a way to spam-hide a dig. No auto-hide in Sprint 1 — there's no moderation
team yet, so this only needs to durably record the signal, not act on it.

### 5.7 Pages

| Path | What |
|---|---|
| `/exploring` | Landing page: what iDIG Exploring is, how to get the extension, and the principles in §0 in plain words |
| `/exploring/{snip_id}` | **The observer's source link at the top** (required), headline, the headline dig (§7.1), sources, 4 trails with move labels, [More trails], "N explorers dug this" |
| `/exploring/d/{dig_id}` | A question dig (§7.2), sources, 4 trails, [More trails], a breadcrumb of the path from the local archive. Shareable. |
| `/exploring/archive` | The observer's archive (§9) |

**Rendering rules:** `contested` and `interpretations` always show *who* holds each position.
The narrator's text and attributed positions look visibly different. Open Graph previews are
built from stored data only.

**AI-disclosure label (added v3.3):** every dig — not only `unverified` ones — shows a
persistent, visible line, not buried in a footer: *"Written by AI from real search results,
not a human editor. Check the sources below — and tell us if something looks wrong."* An
`unverified` dig (§5.3) gets a stronger version of the same idea, not a different one: *"We
couldn't confirm this against search results. Treat it with care."* Both sit next to a
**[Report this]** action (§5.6) — a disclaimer nobody can act on isn't a safeguard, it's
decoration.

## 6. Matching and caching

The worker resolves every snip and trail request with this ladder, checking only against
**current, fresh, `ready`** digs of the **same kind** (`headline` for snips, `question` for
trail requests). `unverified` digs are never matched (D27).

```
normalize(text) → hash
 1. EXACT   hash matches                                        → attach     match_type = exact
 2. NEAR    embed; nearest cosine ≥ EXPLORING_NEAR_MATCH        → attach     match_type = near
 3. GRAY    EXPLORING_GRAY_FLOOR ≤ cosine < NEAR_MATCH          → yes/no check
            yes                                                  → attach     match_type = confirmed
 4. NEW     otherwise                                            → research   match_type = new
```

- **Normalization:** Unicode NFKC, lowercase, strip quotes and punctuation, collapse
  whitespace, remove trailing outlet tags (" - CNN", " | BBC News"). Done once, in Python.
  For question digs, the normalized text is the **question**.
- **Embeddings:** `gemini-embedding-001` at 768 dimensions (`output_dimensionality`), in
  pgvector, searched with `exploring.nearest_dig` over an HNSW cosine index.
- **Gray-zone check:** one ungrounded call to a lite model, ~50 tokens: "same news event?"
  for headlines, "same question?" for questions.
- **Freshness:** `EXPLORING_FRESH_HOURS` = 36 for headline digs,
  `EXPLORING_FRESH_HOURS_QUESTION` = 168 for question digs. A new request that matches only a
  stale dig triggers new research (a new dig with `previous_dig_id`; the old one becomes
  `is_current = false`). **Viewing** never does.
- **Two at once:** the partial unique index on `(kind, query_hash) where is_current`. The
  loser of the insert attaches to the winner's dig.
- **Thresholds** (tune from recorded data): `EXPLORING_NEAR_MATCH = 0.97`,
  `EXPLORING_GRAY_FLOOR = 0.90`.

## 7. The research call, the guards and the trails

**Reference implementation:** `_experiments/exp03_two_step/run_experiment.py`, variant C.
`researcher.py` and `trails.py` should start from it.

### 7.1 Headline dig: context around the claim

One call to `EXPLORING_MODEL` (default `gemini-3.8-flash`): Google Search tool +
`response_mime_type="application/json"` + response schema + `thinking_level="low"`,
temperature 0.4. The input is the headline, source domain and capture date.

```json
{
  "claim": "what the headline states or implies, restated in neutral words, 1 sentence",
  "what_happened": "1-2 sentences",
  "why_now": "what led to this moment, ~60 words",
  "established": ["up to 4 facts that multiple independent sources agree on"],
  "contested": [{"held_by": "who", "position": "what they say, ~30 words"}],
  "left_out": "context the headline doesn't mention that changes how the claim reads, ~60 words",
  "still_unknown": ["up to 3: what isn't settled, and what evidence would settle it"],
  "coverage": "broad | thin | disputed",
  "trails": [{"move": "…", "dimension": "…", "pattern": "… (v3.5, D35, closed vocabulary, §7.3a)", "angle": "… (v3.5, D33)", "question": "…", "hook": "…", "seed": "…"}]
}
```

`contested` has up to 4 entries, and **every** judgment in the dig lives there, attributed.
**No field may state a verdict on the claim** (true/false/misleading) in the narrator's
voice. The worker merges `sources` from grounding metadata (§7.6).

### 7.2 Question dig: evidence first

The same call and settings. The input is the fixed-size context (D19):

```
Answer this question as a stand-alone explainer: "<question>"
Research seed: <seed>
Context, ONLY to identify what is meant (don't write about this story):
Root headline: "<headline>" (<date>); path so far: <q1> → <q2> → <this question>
```

```json
{
  "evidence_story": "what the evidence shows, told plainly, ~150 words; no one-line verdict up front",
  "evidence": ["up to 4 concrete facts, cases, dates or numbers"],
  "interpretations": [{"held_by": "which scholars, officials or schools of thought", "position": "~30 words"}],
  "still_open": "what isn't settled, ~50 words",
  "coverage": "broad | thin | disputed",
  "trails": [ … same shape; hooks tie each new question to THIS answer, not the headline … ]
}
```

**There's no `short_answer` field.** In exp03, the short answer was where subjectivity
concentrated ("virtually never… theatrical threats… posturing"), and the longer explanation
was where the substance was. Lead with the evidence.

Example of an attributed interpretation, from the brinkmanship dig: *Realist scholars argue
public threats raise **audience costs**: once a leader draws a red line in public, backing
down looks weak at home, so compromise gets harder. Others point to the "madman theory" and
argue that looking unpredictable can push an adversary toward concessions.* Both are shown,
each tied to who holds it.

### 7.3 Question craft (goes in the prompt)

Each trail:
- **pattern** *(added v3.5, D35):* the closest-fitting structural pattern from the fixed
  25-item list in §7.3a — a mechanism, not a narrative label, so the model picks it
  independent of who the story's players are. See §7.3a for the full list and rationale.
- **angle** *(added v3.5, D33):* a short phrase, 4-8 words, shown as the trail's visible label
  **instead of** the raw move name. Never the category word itself ("mechanism," "tension") —
  it has to earn attention on its own, before the reader sees the question. A pull-quote
  fragment, not a restatement of the question or the hook. Weak: "Mechanism." Strong: "How a
  database mismatch actually happens."
- **question:** aims at the **enduring puzzle beneath the news**. It would still be worth
  asking a year from now and could be reached from many headlines. **As long as it needs to
  be, in everyday words.** No fixed word limit.
- **hook:** ~15 words. **A specific fact from the cited search results** that makes the
  question urgent now. It must add something the question doesn't say, and never restate it.
- **seed:** a neutral search query for researching the question on its own.

What makes a question worth following. It opens a gap the reader didn't know was there:
- It has a twist: "why would…", "how can… when…", "even though", "yet", "despite".
- It names something concrete: a mechanism, an institution, a place, a pattern.
- It's answerable with evidence (history, data, how a system works). No "should", no
  opinion, no loaded premise.
- A person who isn't very curious reads it and thinks "huh… I don't actually know that."

Rejected outright: textbook abstractions ("How do nations balance sovereignty with
cooperation?"); impact templates ("What are the effects/implications of X?"); anything the dig
already answers; yes/no questions; "you/your"; **restating the question just answered**.

Calibrate with examples from an **unrelated** story, so the model can't copy them into this one
(the drought examples in the exp03 script).

**Moves:** tension (the contradiction inside the story) · mechanism (how the underlying thing
works) · precedent (when it happened before, and how it ended) · frame (how sides or countries
tell it differently) · stakes (what changes on the ground) · hidden (who isn't in the headline
but matters) · scale (how big, against something familiar) · unknowns (what isn't settled, and
what would settle it).

Write **8** trails: at least 2 per dimension, at least 6 different moves.

**Examples from exp03** (the target quality):
- *tension:* "Why do leaders deploy total-destruction rhetoric while quietly negotiating in
  adjoining rooms?" Hook: *"Hours after threatening Iran's annihilation at the podium, US envoys
  met Iranian officials backstage."*
- *mechanism:* "How does the UN Charter treat one member state threatening another with
  annihilation?" It led to Article 2(4), the ICJ's 1996 nuclear weapons opinion, and the
  Chapter VII veto problem.

### 7.3a Patterns: a closed vocabulary for cross-dig connectors (added v3.5, D35)

**Rejected first, and why:** the initial idea was narrative archetypes ("Maverick vs. The
System," modeled on Movies' hand-picked trails). Movies' trails were hand-authored per film —
Paul chose the archetype that fit a film he already knew. Exploring has no equivalent human in
the loop; a model has to classify *any* headline automatically. A real test (a college-football
playoff-format dig) produced an angle phrase — "How 12-team math rewrites at-large bids" — so
specific to that story's own numbers that it could never plausibly match a different story. A
label that only ever matches itself is worthless as a connector (D34).

**The fix: name the mechanism, not the drama.** These 25 are structural/causal patterns drawn
from economics, systems theory, statistics and sociology — established concepts, not invented
flavor — chosen so two stories with nothing narratively in common can still share one:

Function Creep (a system's scope quietly expands past its original purpose) · Teaching to the
Test (optimizing for the measure instead of the goal it represents) · Moral Hazard (being
shielded from consequences changes the behavior it was meant to guard against) · Survivorship
Bias (only the outcomes that made it through get counted) · Selection Bias (the sample isn't
representative of what it claims to describe) · Network Effect (value compounds simply because
more people/nodes join) · Tragedy of the Commons (a shared resource degrades because no one
owns the cost of using it) · Externality (the cost or benefit lands on someone who wasn't part
of the decision) · Principal-Agent Problem (the person acting doesn't bear the consequences the
person affected does) · Regulatory Capture (the overseer starts serving the overseen) · Path
Dependency (an early, possibly arbitrary choice locks in everything downstream) · Threshold
Effect (nothing changes until a line is crossed, then everything does) · Feedback Loop (an
effect loops back and amplifies or dampens its own cause) · Diminishing Returns (the same input
produces less benefit over time) · Winner-Take-All Dynamics (small early advantages compound
into total dominance) · Information Asymmetry (one side knows something the other doesn't, and
that gap drives the outcome) · Signal vs. Noise (what looks meaningful is statistical
variation, or vice versa) · Compounding (small, steady effects accumulate into something large)
· Bottleneck (the whole system's speed is set by its single slowest part) · Redundancy vs.
Fragility (a system's backup capacity, or lack of it, determines what survives) · Lock-In
(switching costs trap people/systems in a choice long after it stops being the best one) ·
Free-Rider Problem (some benefit from a shared effort without contributing to it) · Diffusion
of Responsibility (when everyone is accountable, no one is) · Margin of Error (the gap between
a measurement and the truth becomes the whole story) · Emergent Complexity (simple rules,
followed at scale, produce behavior nobody designed).

("Goodhart's Law" was the working name for **Teaching to the Test** — renamed because the
economics term isn't widely recognized, and the idiom carries the identical meaning without
requiring the reader to know an economist's name.)

**Validated live**, `dev_server/pipeline.py`, across two unrelated real headlines: a Philippine
impeachment-trial dig tagged its vote-threshold trail **Threshold Effect** and its forced-
financial-disclosure trail **Information Asymmetry** — neither forced, both immediately
legible without reading the question first. Canonical source of the list is `PATTERNS` in
`pipeline.py`; the copy above must be kept in sync with it.

### 7.4 Prompt rules (both kinds)

- ALWAYS run Google Search before writing. Only search results count, not memory.
- People's titles and roles come from the search results as of the capture date. (exp01/02
  called the sitting president "former" when working from memory.)
- Research across several outlets, and across countries when the story is international.
  Don't open or quote the observer's source page.
- The narrator states evidence. **Every judgment is attributed** (`held_by`). No loaded
  adjectives in the narrator's voice.
- Don't invent facts. Say so when coverage is thin or disputed.
- The same text for every reader. No years in questions unless needed to tell things apart.
  **No citation markers** like `[1.2.2]` in any text field.

### 7.5 Choosing the four trails (`idig_logic_core`, no AI call)

1. Embed the anchor text and all 8 candidates (`question + hook`) in **one batch call**.
   Anchor: `headline + what_happened + why_now` for headline digs, and
   `question + evidence_story` for question digs.
2. **Loop filter:** drop any candidate whose cosine to a question already on the path
   (including the one just answered) is **≥ 0.85**. (0.90 let a near-restatement through in exp03.)
3. `relevance(c) = cosine(candidate, anchor)`.
4. Pick the most relevant candidate in **each dimension**, with **no repeated move**, which
   gives 3 trails.
5. The 4th is chosen by MMR over the remaining candidates with an unused move:
   `λ · relevance − (1 − λ) · max cosine(c, picked)`, with λ = 0.7.
6. Store all 8, with `score` and with `rank` 1–4 for the shown ones and null for the rest.
   **Counts never factor in** (D26).

**To tune later:** measure how much of the dig's meaning the chosen four cover together, not
only relevance one by one. exp01's relevance scores bunched together at 0.80–0.87.

**Future direction, not built (D34): trails as connectors between digs.** Step 1 already
embeds every candidate trail — that embedding is only ever used within this one dig's
selection and then discarded. The natural extension is to persist it (`exploring.trails`
gets an embedding column) and, at dig-creation time, query for trails already stored under
*other* headlines' digs within some cosine threshold of the new candidate. A genuine match
becomes a visible connector — "this question also came up digging into: ___" — turning a
trail into a door into a different story, not just a follow-up question on this one. This is
the original premise behind "trails, doors into other domains," not a new idea; it's blocked
on the real backend (Supabase, the worker) existing, not on the math. Building it against the
current in-memory `dev_server/` prototype would mean redoing it once that backend lands.

### 7.6 Guards (in the worker, before anything is stored as `ready`)

| Guard | Rule | On failure |
|---|---|---|
| JSON | Parse the response and validate it against the schema | Retry once (exp03: ~1 in 3 grounded calls failed), then `error` |
| Grounding (D27) | ≥ 1 search query **and** ≥ 1 cited source | Retry once, then `unverified` |
| Citation markers | Strip `\[\d+(\.\d+)*\]` from every text field | Fix in place |
| Loaded words (D25) | A word list in `lexicon.py` (theatrical, grandstanding, posturing, slammed, blasted, so-called, …) checked **outside quotes and outside `held_by`/`position`** | Retry once with the hit named, then store with a `loaded_terms` flag |
| Shape | ≥ 6 trails, ≥ 2 per dimension, and `contested`/`interpretations` present | Pick from what's there, and log it |
| Acute personal crisis (added v3.3) | Classify before research: does this headline/question center on an identifiable, named person's private mental-health crisis or self-harm (not an institution, a system, or a public policy)? | See below — not a retry-then-error guard, a content-shape guard |

**Sources:** keep only chunks cited in `grounding_supports`, rank them by citation count, keep
the top 5. Resolve each `vertexaisearch…/grounding-api-redirect/…` URL by reading its
`Location` header **without following it**, since those redirect links aren't permanent.
Store `{domain, url, cited}`.

**Acute personal crisis guard, in full (added v3.3):** found by stress-testing the trail
taxonomy against a real headline about a named public figure's suicide attempt. The four
RSD dimensions (§1 Vocabulary; a proposed fourth, Wonder, isn't built yet) aren't uniformly
safe here:
- `semantic` and `social` trails stay legitimate **if aimed at the practice, not the person** —
  how crisis interventions and wellness checks actually work, what real suicide-reporting
  standards (WHO; the AFSP's *Reporting on Suicide* recommendations) say about publishing
  details like this and why, who decided to publish it. These don't require knowing or
  speculating about anyone's private state.
- `experiential` trails are suppressed outright. "What's it like to be in crisis," aimed at a
  specific, currently-identified real person, isn't empathy — it's speculation about someone's
  private suffering as content for strangers, however carefully worded.
- Any future Wonder-dimension trail is suppressed outright, for the same reason one register
  deeper: aiming *thaumazein* at a real person's suffering — making it material for strangers'
  philosophical arrest — uses someone's worst moment without their consent.
- **The resource/commerce enrichment layer (working name iDIG Deeper) does not run at all.**
  No exception. This is a firm product rule, not a judgment call left to the model: recommending
  a book, a documentary, or any purchase against content about a real person's suicide attempt
  is unambiguously monetizing it. Right-of-publicity law (e.g. California Civil Code §3344)
  makes this a legal exposure too, independent of the ethical one — commercial use of a real
  person's identity without consent is close to the textbook fact pattern those claims are built
  on.
- This is a **deterministic classifier the worker runs**, not a system-prompt instruction. A
  differently-worded headline can talk a model out of an instruction; it can't talk a
  code-level gate out of running.
- In place of trails and enrichment for content that trips this guard, the page shows a plain,
  unmonetized pointer to the 988 Suicide & Crisis Lifeline — not a trail, not a product.

### 7.7 Wonder: a proposed 4th dimension, local to this domain (added v3.4, D32)

**Status: exploratory, this sprint only.** Not yet proven at pipeline scale — validated so far
by hand-reasoning through two headlines (a Supreme Court/SAVE-database ruling, and a
"Madden trailer sparks debate over Nicolas Cage's portrayal" story), not by an automated
`researcher.py` prompt. Treat everything below as a working hypothesis to test this sprint,
not a committed design the way §7.1–§7.6 are.

**What it is.** The three existing RSD dimensions (§1 Vocabulary) are all instrumental — they
help the observer navigate a situation: how it works (`semantic`), what it costs to live under
it (`experiential`), who's saying what (`social`). Wonder is not instrumental. It doesn't
resolve. It's distinct from `unknowns` specifically: `unknowns` is an *epistemic* gap — more
evidence would close it. Wonder is a *permanent* open-endedness — no amount of evidence closes
it, because the question was never really about facts.

**Why "Wonder," specifically.** Grounded in Plato, not vibes: *thaumazein* — wonder — is the
term Plato (*Theaetetus* 155d) and Aristotle (*Metaphysics* I) use for the origin of philosophy
itself, the state of being arrested by a question you hadn't considered. Wonder isn't one
emotional flavor (awe, or melancholy, or vertigo) — it's the structural moment of arrest, which
can cash out as any of those depending on the story. Candidate **moves** under this dimension
(untested): `mystery`, `melancholy`, `awe`, `vertigo`. These would sit under Wonder the way
`tension`/`frame`/`hidden` sit under `social` — flavors of one dimension, not a dimension each.

**The craft difference.** Every other move's hook performs urgency ("here's what makes this
pressing now") — that fits, because the other 7 moves point toward evidence that can resolve
something. A Wonder hook shouldn't perform urgency, since urgency implies movement toward
resolution and Wonder doesn't resolve. It should make the question harder to look away from,
not more pressing.

**The reasoning technique that produced a good Wonder trail on the first try** (worth writing
into the actual prompt when this gets built): (1) take the surface claim literally; (2) ask what
the emotional charge is actually about underneath the literal claim; (3) look for a hidden
structural fact that recontextualizes the surface claim — often temporal (someone is dead, time
has passed) or "the original was already X" (the thing being compared against was itself
constructed or mediated); (4) check for analogical resonance with a totally different register
(physics, philosophy, an unrelated earlier story) — same abstract shape, different domain; (5)
ground the feeling in a real, named, existing concept (a real psychological, philosophical, or
historical term), so it stays evidence-respecting rather than inventing sentiment, keeping faith
with D24/D25 even for a non-resolving dimension; (6) write the question with the standard craft
rules (§7.3), with the softened, non-urgent hook described above.

**Open design question, not yet settled:** how a question dig answering a Wonder trail should
end. Not `still_unknown: what evidence would settle it` — that's the epistemic-gap ending, wrong
register for this. Something closer to "what this leaves you sitting with," honestly presented
as non-resolving rather than forcing a take.

**Where it lives (D32): entirely inside `exploring_domain/`.** `idig_logic_core`'s `RSDVector`
(`core/rsd.py`) and HCS scoring (`core/hcs.py`) are hardcoded to exactly three dimensions —
verified by reading the source, not assumed — and are live under three other domains
(`jobs_manager_domain`, `knowledge_center_domain`, `recruiting_domain`) that have nothing to do
with Exploring. Nothing in this section touches those files. If Wonder proves out this sprint,
promoting it to core — generalizing `hcs.py`'s pairwise interference-harmony math from three
dimensions to however many exist — is a deliberate follow-up decision, expected to happen
alongside Paul's planned migration of Movies onto core/domains, not before.

**Interaction with §7.6:** the acute-personal-crisis guard already accounts for Wonder — any
Wonder-dimension trail is suppressed outright for content about an identifiable person's private
crisis, for the same reason `experiential` trails are.

## 8. Data: Supabase (core project, schema `exploring`)

### 8.1 Schema

```sql
create extension if not exists vector;
create schema if not exists exploring;

create table exploring.digs (
  id              uuid primary key default gen_random_uuid(),
  kind            text not null check (kind in ('headline','question')),
  query_text      text not null,        -- normalized headline, or the question
  query_hash      text not null,        -- sha256 of query_text
  embedding       vector(768),
  parent_dig_id   uuid references exploring.digs(id),  -- where a question dig was first reached from
  previous_dig_id uuid references exploring.digs(id),  -- older version this one refreshes
  is_current      boolean not null default true,
  status          text not null default 'queued'
                  check (status in ('queued','researching','ready','unverified','error')),
  result          jsonb,                -- §7.1 / §7.2 shape minus trails
  sources         jsonb,                -- [{domain, url, cited}] top 5 (§7.6)
  coverage        text check (coverage in ('broad','thin','disputed')),
  flags           text[] not null default '{}',   -- e.g. loaded_terms, json_retry, grounding_retry
  search_queries  int,
  sources_cited   int,
  error           text,
  model           text,
  tokens_in       int,
  tokens_out      int,
  tokens_thinking int,
  snip_count      int not null default 0,
  follow_count    int not null default 0,
  report_count    int not null default 0,   -- §5.6, no auto-hide yet, just a durable signal
  researched_at   timestamptz,
  fresh_until     timestamptz,
  created_at      timestamptz not null default now(),
  updated_at      timestamptz not null default now()
);
create unique index digs_current_query on exploring.digs (kind, query_hash) where is_current;
create index on exploring.digs using hnsw (embedding vector_cosine_ops);
create index on exploring.digs (status, created_at);

create table exploring.snips (
  id                uuid primary key default gen_random_uuid(),
  headline          text not null,
  source_url        text not null,
  source_domain     text not null,
  captured_at       timestamptz not null,
  source            text not null default 'idig-browser-extension',
  dig_id            uuid references exploring.digs(id),
  match_type        text check (match_type in ('exact','near','confirmed','new')),
  status            text not null default 'received'
                    check (status in ('received','resolved','error')),
  error             text,
  delete_token_hash text not null,
  rate_key          text,               -- hashed IP; cleared once resolved (§8.4)
  created_at        timestamptz not null default now()
);
create index on exploring.snips (status, created_at);
create index on exploring.snips (dig_id);

create table exploring.trails (
  id             uuid primary key default gen_random_uuid(),
  dig_id         uuid not null references exploring.digs(id) on delete cascade,
  move           text not null check (move in ('tension','mechanism','precedent','frame',
                                               'stakes','hidden','scale','unknowns')),
  dimension      text not null check (dimension in ('semantic','experiential','social')),
  question       text not null,
  hook           text not null,
  seed           text not null,
  embedding      vector(768),
  score          real,
  rank           smallint,             -- 1–4 shown; null = shown under "More trails"
  child_dig_id   uuid references exploring.digs(id),
  child_status   text not null default 'none'
                 check (child_status in ('none','requested','ready','unverified','error')),
  follow_count   int not null default 0,   -- shown, never used for ranking (D26)
  rate_key       text,
  created_at     timestamptz not null default now()
);
create index on exploring.trails (dig_id, rank);
create index on exploring.trails (child_status) where child_status = 'requested';

create table exploring.rate_counts (
  rate_key    text not null,
  day         date not null,
  generations int  not null default 0,
  primary key (rate_key, day)
);

alter table exploring.digs        enable row level security;
alter table exploring.snips       enable row level security;
alter table exploring.trails      enable row level security;
alter table exploring.rate_counts enable row level security;
-- No public policies: the Next route handlers and the worker both use the service role.
```

Plus `exploring.nearest_dig(query vector, kind text, min_fresh timestamptz)`, which returns
the closest **current, fresh, `ready`** dig of that kind with its cosine similarity.

**Setup:** add `exploring` to Supabase **Settings → API → Exposed schemas**, and enable the
`vector` extension in the core project.

### 8.2 Counters

`snip_count` goes up when a snip resolves to a dig. `follow_count` on the trail and its child
dig goes up on every follow, including cached ones. They're shown ("12 explorers dug this")
and **never used to rank** (D26). They carry no identity.

### 8.3 What's never stored

The observer's identity, a raw IP, the screenshot or crop, page content, any link between
two snips from the same person, or any measure of time spent.

### 8.4 Rate limits (D21)

- `rate_key = sha256(ip + EXPLORING_RATE_SECRET + yyyy-mm-dd)`. It rotates daily.
- The route saves `rate_key` on the snip, or on the trail when a click queues one. The worker
  clears it once the request resolves.
- **The per-IP limit is checked by the worker, and only when it's about to generate.** If
  `generations ≥ EXPLORING_DAILY_PER_IP` (default 30), the request ends in `error` with
  "Daily dig limit reached. Cached digs still open." Cache hits never count.
- **Global cap:** `EXPLORING_HOURLY_CAP` (default 60) new research calls per hour. The route
  answers 429 once it's full.
- Cloudflare Turnstile only if bots appear.
- **Demo gate (D31):** checked in the route **before** anything else, using the same IP the
  `rate_key` comes from (`x-real-ip`, then the first `x-forwarded-for` entry, as set by
  Vercel). The allowlist check uses the raw IP in memory only, and the IP is never stored.
  Localhost (`127.0.0.1`, `::1`) is always allowed in development.

## 9. The archive (no login, on the device)

### 9.1 Storage

IndexedDB `idig-exploring` on the i-dig.io origin, modeled on
`idig_movies_production_demo/src/shared/hooks/useSavedFilms.ts`, in
`exploring_app/lib/archive.ts` (`'use client'`). Every lens is served from the same origin, so
database names stay prefixed by lens.

Stores:
- `history`, keyed by `key`:
  ```ts
  { key: "snip:<id>" | "dig:<id>",
    type: "snip" | "question",
    snipId?: string, digId: string,
    title: string,                 // headline, or the question
    move?: string, dimension?: string,   // trail follows; available to a lens the observer turns on
    sourceDomain?: string,         // snips only
    parentDigId?: string,          // builds the breadcrumb; with openedAt, preserves path ORDER
    openedAt: string,
    deleteToken?: string }         // snips only (D22)
  ```
- `settings`: `{ paused: boolean, lens: { ... } | null }`, where `lens` holds whatever the
  observer chose (D29).

### 9.2 Saved automatically

Opening a snip page or following a trail writes a `history` entry unless `paused` is on. No
save button. Entries are pointers, and the content stays on the server. Paths are ordered
histories (`parentDigId` + `openedAt`), because the order of questions shapes understanding.

### 9.3 Delete token handoff

The snip page reads `#t=<token>`, stores it in that snip's history entry, and immediately
calls `history.replaceState` to remove it. Shared links never carry it.

### 9.4 Archive page and controls

`/exploring/archive`:
- History, newest first, with breadcrumbs for paths.
- **Export:** `idig-exploring-archive.json` with
  `{version: 1, exported, source: "idig-exploring", history: [...], settings: {...}}`.
- **Import:** merges by `key` and **keeps every field**. (Movies' version drops `projectId`
  at `useSavedFilms.ts:117-123`. Don't copy that bug.)
- Remove an entry, clear all (this device only), pause saving.
- *(Sprint 2)* Delete my snip from iDIG (§5.5).
- *(Sprint 2)* **My lens (D29):** the observer chooses what they want more of, for example
  "the history behind things," "how other countries see it," "what I don't usually read."
  Each choice maps to move/dimension weights that re-rank a dig's 8 stored candidates in the
  browser. Their own move/dimension counts are shown to them as information only, and used only
  if they turn that on. Nothing leaves the device.

### 9.5 Known limits (stated on the archive page)

The archive exists only in this browser on this device. It's gone after clearing site data or
in a private window, and Safari erases it after 7 days without a visit. The fix is export and
import.

## 10. Exploring domain: the worker

`iDIGcore_w_domains/idig_lc_domains/exploring_domain/`:

| File | Role |
|---|---|
| `schema.py` | Field names and JSON schemas for both dig kinds and for trails (the contract) |
| `prompts.py` | Headline prompt, question prompt, question craft (§7.3), rules (§7.4), gray-zone prompts |
| `normalize.py` | Normalization + hashing (§6) |
| `matcher.py` | The matching ladder (§6) |
| `researcher.py` | The grounded call (§7.1–7.2), fixed-size context, token counts. Start from the exp03 script. |
| `guards.py` | JSON, grounding, citation-marker, loaded-word and shape checks, plus source cleanup (§7.6) |
| `lexicon.py` | The loaded-word list (tunable) |
| `trails.py` | Loop filter + selection (§7.5), using `idig_logic_core` |
| `limits.py` | Per-IP daily check + global hourly cap (§8.4) |
| `supabase_writer.py` | Conditional claims, writes, counters, clearing `rate_key` |
| `run.py` | Polls every 3s for `received` snips and `requested` trails |

**Changes needed in `idig_logic_core`:**
- `BaseConditioner`: optional `tools`, `response_schema`, `thinking_level` (Gemini 3.x uses
  levels, not a budget) and `max_output_tokens`. Today it only sets `system_instruction`,
  `temperature` and a JSON mime type.
- `vectors.py`: `embed_texts(client, texts)` for batch embedding, and
  `output_dimensionality=768`. Note that its default model, `gemini-embedding-2`, falls back to
  `gemini-embedding-001`, which is what the experiments used.
- Add an MMR / diversity helper next to `cosine_similarity`.

**Environment (revised 2026-09-27):** Exploring uses its **own dedicated key**,
`EXPLORING_GEMINI_API_KEY`, set in the same shared `iDIGcore_w_domains/.env` file — not the
plain `GEMINI_API_KEY` that `recruiting_domain`/`knowledge_center_domain`/`jobs_manager_domain`
already share, and not Movies' separate `GOOGLE_API_KEY` (a different repo entirely, which
doesn't import `idig_logic_core` — confirmed by checking, D32's finding applies to Movies'
independence generally, not just the HCS math). Reasoning: quota/billing isolation, so an
experimental Exploring pipeline can't eat into Hiring's or Movies' production budget or rate
limit, and clean cost attribution per product — relevant given Paul's plan to license/sell
these separately rather than operate them as one thing. Set `EXPLORING_MODEL` so the model
can be switched without code changes.

Production hosting of the worker is **deferred** (runs locally in Sprint 1).

## 11. Privacy (testable checks)

- *(v3.2: reversed, see D6.)* The launcher content script runs on every `http`/`https` page
  and `host_permissions` covers all origins — broader than v3's `activeTab`-only model. What
  it still does **not** do: no `tabs` or `history` permission; it never reads page title,
  meta, DOM text or cookies; it renders only the floating icon and, on activation, the
  selection surface and review panel — nothing runs silently in the background.
- The payload sent to the server is exactly the five fields in §5.1. No image, HTML, title,
  meta, cookies, DOM text or device ID.
- `chrome.storage.session` is cleared on send or cancel. *(v3.2: except a deliberate Save —
  see §4.5's History tab. Cancel and every other close path are unchanged: nothing is stored.)*
- The extension makes no network calls except to the configured iDIG API.
- No raw IP stored. `rate_key` rotates daily and is cleared once a request resolves.
- The delete token never reaches the server in a URL, and only its hash is stored.
- The archive and lens never leave the device except in a file the observer exports.
- No cookies, analytics scripts or time-on-site measurement on `/exploring`.

## 12. Scope

**Sprint 2 (designed here, built next):**
- Sharing a whole path as one link (a stored list of dig IDs, zero tokens).
- **A share card:** one question + the first lines of its evidence. That's the shareable unit
  of insight, not the headline.
- Delete my snip from iDIG (§5.5).
- My lens (§9.4, D29).

**Later:**
- **Road less traveled (D26):** once follow counts exist, reserve one of the 4 slots for a
  strong, complementary candidate that few observers have taken.
- **Signals the math can read from content alone**, none of which need personal data:
  - *Agreement:* embed how each source states a claim and measure the spread. Tight means
    established, wide means contested, with no verdict needed.
  - *Left out:* entities in the sources minus entities in the headline.
  - *Frame differences:* different wording for the same event across outlets and countries.
  - *Hub questions:* question digs reached from many different headlines. These are the
    evergreen ideas the news keeps passing through, and a map of how ideas connect, not of people.
- **Doors** into other iDIG domains (a contract per domain) and one iDIG archive file across
  lenses.
- Other ways in: a typed topic, and right-click "Dig this selection" (no OCR).
- Side panel review UI, Safari, production worker hosting, refreshing stale popular digs ahead
  of demand, Turnstile.

**Always out:** scraping; summarizing source articles; accounts and profiles; feeds; verdicts
(true/false labels); pay-to-play placement; optimizing time on site, return visits, streaks,
autoplay or infinite scroll.

## 13. Cost and integrity

### 13.1 Cost (measured, exp01–03)

| Action | AI cost |
|---|---|
| View any page, open a shared link, render a preview | none |
| Snip, exact or near match | one embedding (near only) |
| Snip in the gray zone | embedding + ~50-token lite call |
| Snip, new story | one grounded call (**~2,000 tokens**, 0 thinking at "low") + one batch embedding |
| Trail click, already dug | none |
| Trail click, first time | one grounded call (**~2,000 tokens**) + one batch embedding |

Retries add roughly 30% on average (exp03: about 1 in 3 grounded calls needed a JSON retry).
3.x models report `tool_use_prompt_token_count` as 0 and searched 0–4 times per dig.
**Before launch:** check current Gemini 3.x token and grounding prices, and whether grounding is
billed per request or per search query.

### 13.2 Integrity (what the system measures, D28)

- Grounding rate, and the share of digs that end up `unverified`
- Loaded-word flags per 100 digs
- JSON retry rate
- Cache hit rates by `match_type`
- **Path diversity:** for each headline, how many distinct moves and dimensions observers'
  first steps cover, and the spread of question digs reached. This is anonymous and aggregate,
  from counts only.
- **Payoff > hook:** a person periodically reviews a sample of trails and their digs. Did the
  answer deliver more than the hook promised?

**Never measured:** time on site, return visits, scroll depth, streaks, or anything that
profiles an individual.

### 13.3 Spending limits

These layers work together, from the cheapest to the hardest to get around:

| Layer | Limit | Where | On hit |
|---|---|---|---|
| **Demo gate** (D31) | Only allowlisted IPs can generate | Web app routes | `403`; existing digs stay readable |
| **Per call** | `max_output_tokens` = `EXPLORING_MAX_OUTPUT_TOKENS` (default 3000; exp03's largest single output was ~1,300). **Check in E1 whether Gemini 3.x counts thinking tokens against it.** | `researcher.py` | Treated as a JSON failure (§7.6) |
| **Per dig** | **At most 2 attempts in total, across all guards.** A JSON retry, a grounding retry and a loaded-word retry share that one extra attempt; they don't stack. | `guards.py` | `error` or `unverified`, with a flag |
| **Per IP per day** | `EXPLORING_DAILY_PER_IP` new generations (default 30) | Worker (§8.4) | "Daily dig limit reached" |
| **Per hour** | `EXPLORING_HOURLY_CAP` new research calls (default 60) | Route + worker | `429`; worker pauses |
| **Per day, in tokens** | `EXPLORING_DAILY_TOKEN_BUDGET` (default 500,000). Summed from `tokens_in + tokens_out + tokens_thinking` on today's digs, plus the gray-zone calls. | Route + worker | `429` for new snips; the worker stops generating; cached digs still open |
| **Google side** | A budget alert **and** a hard API quota on the Google Cloud project that owns `GEMINI_API_KEY`. When the worker is hosted on a fixed IP, also restrict the key to that IP. | Google Cloud console | Google refuses the calls, even if the code misbehaves |

With the defaults, the hourly cap alone allows ~60 digs × ~2,600 tokens ≈ **156k tokens an
hour**. The daily token budget brings that down to ≈ **190 new digs a day** at most.
Raise the limits deliberately, not by default.

## 14. Acceptance (Sprint 1 done when a developer can…)

1. Load `extension/dist` unpacked in Chrome.
2. On any news article, click iDIG, select just the headline, and confirm.
3. See the crop and the OCR text, and edit it.
4. Send it to `localhost:3003/exploring/api/snips` and get a snip UUID + delete token.
5. Land on `/exploring/{id}` with no `#t=` in the address bar. See the source link, headline,
   and "Digging…" resolve into: **the claim · what happened · why now · established ·
   contested (each with who holds it) · left out · still unknown · ≤ 5 real source URLs** (no
   `vertexaisearch` redirects), then **4 question trails, each with a move label and hook, with
   4 different moves and every dimension present**, plus [More trails].
6. Snip the **same headline** from a second browser profile. It resolves `exact` with **no new
   research call**.
7. Snip the same story from a **different outlet's headline**. It resolves `near`/`confirmed`,
   or `new` if the thresholds say so, and the outcome is recorded.
8. Click a trail. A question dig opens at `/exploring/d/{dig_id}`: **evidence story ·
   evidence · interpretations (attributed) · still open**, with 4 new trails, none restating
   the question just answered. Click the same trail from the second profile: instant, no
   research call.
9. `/exploring/archive` lists the snip and the question, in path order, without saving by hand.
   Export → clear → import restores everything, including delete tokens.
10. Reload dig pages 10× and fetch them with `curl`: no new rows, no research calls.
11. Set `EXPLORING_DAILY_PER_IP=1`: the second *new* story is refused with the limit message,
    and a cached one still opens.
12. Every `ready` dig has `search_queries ≥ 1` and `sources_cited ≥ 1`. A forced no-search
    result (mock the response) ends as `unverified` with the notice, and is not reused by a
    later matching snip.
13. Stop the web app, snip again, and get the fallback screen with Copy payload and Retry.
14. The Network tab shows the extension sent only the five-field POST.
15. **Demo gate:** with `EXPLORING_ALLOWED_IPS` set to an address that isn't yours (and
    localhost exemption off for the test), a snip POST and a follow of an undug trail both get
    `403` with no new rows, while existing digs and already-dug trails still open. Set
    `EXPLORING_DAILY_TOKEN_BUDGET` below today's total: the next new snip gets `429`, and cached
    digs still open.
