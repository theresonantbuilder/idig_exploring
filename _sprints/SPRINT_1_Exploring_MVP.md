# Sprint 1 — iDIG Exploring MVP

## Goal
Reach the acceptance criteria in [`../SPEC.md` §14](../SPEC.md#14-acceptance-sprint-1-done-when-a-developer-can):
snip a headline in Chrome and land on a headline dig that paints context around the claim,
with 4 question trails. Follow one to a question dig that answers with evidence and
attributed interpretations. Repeat snips and repeat trail clicks come from the shared cache
with no new AI call. The observer's path is saved automatically on the device. Everything runs
locally. Paths already match production (`i-dig.io/exploring/{id}`), and Phase G is the step
that puts them live.

Read [`SPEC.md` §0 North star](../SPEC.md#0-north-star) before building anything. Every
phase serves it.

## Where the work happens
| Part | Location |
|---|---|
| Extension | `idig_exploring/extension/` (this folder) |
| Web app (pages, API routes, on-device archive) | `iDIGcore_w_domains/exploring_app/` (new, Next.js, `basePath=/exploring`, port 3003) |
| Apex routing (Phase G) | `idig_website_new-build/vercel.json`, the same rewrite pattern as `/movies` |
| Worker (matching, research, guards, trails, limits) | `iDIGcore_w_domains/idig_lc_domains/exploring_domain/` |
| Core changes (conditioner, batch embeddings, MMR) | `iDIGcore_w_domains/idig_logic_core/` |
| Data | Existing core Supabase project, new `exploring` schema (+ pgvector) |
| Reference implementation | `_experiments/exp03_two_step/run_experiment.py` (variant C) |

## Before starting
- [ ] **P1** Put a real `GEMINI_API_KEY` in `iDIGcore_w_domains/.env`. It currently holds the
      template placeholder. The experiments borrowed the key from
      `iDIG_demo_resonance-engine-with-attractor/.env`. Add `EXPLORING_MODEL=gemini-3.8-flash`.
- [ ] **P2** Look up current Gemini 3.x Flash token and grounding prices, including whether
      grounding is billed per request or per search query. Note them in SPEC §13.1.
- [ ] **P3** On the Google Cloud project that owns the key: set a **budget alert** and a
      **hard API quota** (SPEC §13.3), so Google refuses calls even if the code misbehaves.

## Ordering rule
**Phase A is a gate.** Don't start B until the snip-and-crop step works reliably on the test
pages below. **Phases D and E don't depend on the extension** and can run alongside A–C.
**E0 (core changes) comes before the rest of E, and E1 (experiment 04) comes before
researcher.py is finalized.**

**Test pages** (vary layout, zoom and DPR): apnews.com article, nytimes.com article (paywall
shell), bbc.com, a Substack post, a page with a sticky header. Test at browser zoom 100% and 150%.

---

## Phase A — Extension skeleton + snip prototype (gate)
- [x] **A1** Scaffold `extension/`: Vite + TypeScript, MV3 build that outputs `dist/` with
      background, overlay, and review entry points. Add `config.ts` reading
      `VITE_IDIG_API_URL`, plus `.env.development` and `.env.production`.
- [x] **A2** `browser/abstraction.ts` interface + `browser/chrome.ts`. Check with grep that
      `chrome.` appears nowhere else in `src/`.
- [x] **A3** *(revised 2026-09-25, SPEC D6/§4.2)* Manifest per SPEC §4.2 (name "iDIG
      Exploring"): `storage`, `host_permissions` for all `http`/`https` origins, and a
      persistent `content_scripts` entry running `launcher.js`. Placeholder icons.
- [ ] **A4** *(rebuilt 2026-09-25, verify in A8)* A persistent floating launcher icon
      (`content/launcher.ts`) on every page, draggable vertically, position kept in
      `chrome.storage.local`. Click (icon or toolbar) starts a selection. No content script
      on a page (e.g. `chrome://`) → badge only (SPEC §4.4).
- [ ] **A5** *(built, verify in A8)* Selection surface: Shadow DOM, banner, drag rectangle,
      dim outside, drag again to redraw, [Cancel]/[iDIG], Esc, min-size check, cancel on
      scroll, clean removal.
- [ ] **A6** *(built, verify in A8)* Hide surface → send rect + DPR + url → background runs
      `captureVisibleTab`, scales the rect, crops with `OffscreenCanvas` → stores in
      `storage.session`.
- [ ] **A7** *(rebuilt 2026-09-25, verify in A8)* Docked review panel (iframe onto
      `review.html`, opened by the launcher) shows **only the cropped image**.
- [ ] **A8 (gate check)** On every test page and at both zoom levels, the crop matches the
      drawn rectangle with no overlay chrome in it. Record results under "Gate results."

## Phase B — OCR + review
- [ ] **B1** Bundle Tesseract.js v5 worker, core wasm and `eng.traineddata` into
      `public/ocr/`, loaded through `runtime.getURL`. Confirm no requests go to a CDN.
- [ ] **B2** `ocr.ts`: preprocess (upscale to text height ≥ 40px, grayscale), page
      segmentation mode 6, return `{text, confidence}`.
- [ ] **B3** Review UI: status line, editable headline (normalized, ≤ 300 chars), source
      domain with the full URL, [Send to iDIG]/[Cancel].
- [ ] **B4** OCR failure or text shorter than 3 chars → "We couldn't read the headline." with
      manual entry.
- [ ] **B5** Accuracy check: OCR 10 real headlines. Aim for at most 2 of 10 needing more than
      a one-character fix, and tune the preprocessing if it misses.

## Phase C — Submit + dev fallback
- [ ] **C1** `api/idig.ts`: POST the five-field payload to `/exploring/api/snips` with an 8s
      timeout.
- [ ] **C2** On `201 {id, delete_token}` → open `{API}/exploring/{id}#t={delete_token}`, close
      the review window, clear the session entry. The extension stores nothing.
- [ ] **C3** Fallback screen: "● iDIG unavailable", [Copy payload], [Retry]. Show the message
      from a 4xx, including 429.
- [ ] **C4** `extension/README.md`: install, `npm run dev` / `build`, load unpacked,
      switching the API URL.

## Phase D — Data + web app (core repo)
- [ ] **D1** Write `exploring_domain/_sprints/schema.sql` from SPEC §8.1, including
      `exploring.nearest_dig` (current, fresh, `ready` only). Enable `vector`, run it in the
      core Supabase project, and **add `exploring` to Exposed schemas.**
- [ ] **D2** Scaffold `exploring_app/` like `knowledge_center_app` (Next 16, Tailwind 4,
      `server-only`). Copy its `NEXT_PUBLIC_BASE_PATH` block, set
      `NEXT_PUBLIC_BASE_PATH=/exploring`, dev script `next dev -p 3003`,
      `lib/supabaseAdmin.ts` pinned to the `exploring` schema.
- [ ] **D3a** `lib/demoGate.ts` (SPEC D31, §8.4): `EXPLORING_DEMO_MODE` (default on),
      `EXPLORING_ALLOWED_IPS` (comma list, CIDR supported), localhost always allowed, IP from
      `x-real-ip` then the first `x-forwarded-for` entry, **fail closed** if there's no IP.
      Never logs or stores the IP.
- [ ] **D3** `POST app/api/snips/route.ts` (SPEC §5.1): **demo gate first → 403**, validation,
      global hourly cap and daily token budget → 429,
      `rate_key` from the request IP, a random delete token with only its hash stored,
      insert, return 201 `{id, status, delete_token}`.
- [ ] **D4** Read-only GET routes: `api/snips/[id]`, `api/digs/[id]` (with `trails` and
      `more_trails`), `api/trails/[id]` (SPEC §5.2–5.4). Trails return
      `{id, move, dimension, question, hook, rank, child_dig_id, follow_count}`, never `seed`
      or `embedding`.
- [ ] **D5** `POST api/trails/[id]/follow` (SPEC §5.4): a fresh `ready` child → 200 +
      `follow_count`++. Otherwise **the demo gate** (not allowed → 403 with the demo message),
      then a conditional update to `requested` with `rate_key` → 202.
- [ ] **D6** `lib/archive.ts` (`'use client'`), modeled on Movies' `useSavedFilms.ts`:
      IndexedDB `idig-exploring`, `history` + `settings` stores, record / list / remove /
      clear / pause, export + import that **keeps every field** (SPEC §9). Record `move`,
      `dimension` and `parentDigId` on trail follows so path order is preserved.
- [ ] **D7** `app/[id]/page.tsx` → `/exploring/{snip_id}`: read `#t=` → save to archive →
      `history.replaceState`. Source link at top, headline, "Digging…" with 3s polling (a
      basePath-aware URL, since `fetch` doesn't add basePath). Then render the headline dig
      in SPEC §7.1 order: the claim · what happened · why now · established · **contested
      with who holds each position, visibly distinct from the narrator** · left out · still
      unknown · sources. Then 4 trails (move label · question · hook) + [More trails] + "N
      explorers dug this." Handle not-found, error, daily-limit and **unverified** (notice
      text in SPEC §5.3) states.
- [ ] **D8** `app/d/[id]/page.tsx` → `/exploring/d/{dig_id}`: the question dig in SPEC §7.2
      order: evidence story · evidence · **interpretations, attributed** · still open ·
      sources. Then 4 trails + [More trails] and a breadcrumb from the local archive.
- [ ] **D9** `app/archive/page.tsx`: history with path breadcrumbs, export, import, remove,
      clear all, pause, and the known-limits note (SPEC §9.5).
- [ ] **D10** `app/page.tsx` at `/exploring`: landing page, including the §0 principles in
      plain words. Open Graph tags on snip and dig pages, built from stored data only.
- [ ] **D11** Security headers matching Movies' `vercel.json` (SPEC §4.8). **No cookies, no
      analytics, no time-on-site measurement** (D28).
- [ ] **D12** Test with curl against `localhost:3003`: a valid snip, bad inputs, a burst over
      the hourly cap, and GETs creating no rows.

## Phase E — Exploring domain worker (core repo)
- [ ] **E0 (core first)** In `idig_logic_core`: `BaseConditioner` gets optional `tools`,
      `response_schema`, `thinking_level` and `max_output_tokens`. `vectors.py` gets
      `embed_texts` (batch) and `output_dimensionality=768`. Add an MMR helper. Check that
      recruiting still runs unchanged.
- [ ] **E1 (experiment 04, before finalizing prompts)** Copy `_experiments/exp03_two_step/`
      to `_experiments/exp04_claims/` and switch it to the v3.1 shapes (SPEC §7.1–7.2),
      question craft without a word limit (§7.3), the rules (§7.4), the loop filter at 0.85,
      and the guards (§7.6). Run it on **4 real headlines**: one political with a clear claim,
      one non-political (science, health or culture), one thin live-blog headline, and one
      that isn't breaking news. For each, check:
      - Is the claim neutral? Is every contested position attributed, and is the narrator
        free of verdicts and loaded words?
      - Do the questions and hooks meet §7.3, and does the payoff exceed the hook?
      - Grounding rate, JSON retry rate and tokens per dig.

      Write `REPORT.md` and adjust the prompts before E3.
- [ ] **E2** Scaffold `exploring_domain/` (`schema.py`, `prompts.py`, `normalize.py`,
      `matcher.py`, `researcher.py`, `guards.py`, `lexicon.py`, `trails.py`, `limits.py`,
      `supabase_writer.py`, `run.py`) and add it to `idig_lc_domains/README.md`.
- [ ] **E3** `researcher.py` + `prompts.py`: one call to `EXPLORING_MODEL` with search +
      response schema + `thinking_level="low"` for both dig kinds (SPEC §7.1–7.4), the
      fixed-size context for question digs, and token counts stored. Start from the E1 script.
      Set `max_output_tokens` from `EXPLORING_MAX_OUTPUT_TOKENS` (SPEC §13.3). In E1, check
      whether Gemini 3.x counts thinking tokens against it.
- [ ] **E4** `guards.py` + `lexicon.py` (SPEC §7.6): JSON retry, grounding requirement →
      `unverified`, **at most 2 attempts per dig across all guards**, citation-marker
      stripping, loaded-word check outside attributed fields,
      shape check, and source cleanup (cited only, top 5, redirect resolved from the
      `Location` header without following it). **Also (added v3.3): the acute-personal-crisis
      classifier (SPEC §7.6) — a deterministic check run before research, not a prompt
      instruction, suppressing `experiential`/Wonder trails and the whole iDIG Deeper layer
      for content about an identifiable person's private crisis.**
- [ ] **E5** `normalize.py` + `matcher.py`: exact → near → gray → new (SPEC §6), matching
      only `ready` digs of the same kind, freshness by kind, the insert race handled, and
      `match_type` recorded.
- [ ] **E6** `trails.py`: batch embed, loop filter at 0.85 against the path, best per
      dimension with distinct moves, the 4th by MMR, all 8 stored with `score` and `rank`.
      **Counts never used.** If prototyping the proposed Wonder dimension this sprint (SPEC
      §7.7, D32), its move/dimension handling is **local code in this file**, not an import
      from or edit to `idig_logic_core` — do not touch `core/rsd.py`'s `RSDVector` or
      `core/hcs.py`'s `DIMS`/interference-harmony math. That code is live under
      `jobs_manager_domain`, `knowledge_center_domain`, and `recruiting_domain`.
- [ ] **E7** `limits.py` + `supabase_writer.py` + `run.py`: per-IP daily check only before
      generating, global hourly cap, **daily token budget** (`EXPLORING_DAILY_TOKEN_BUDGET`,
      summed from today's `tokens_*` plus gray-zone calls; stop generating when reached),
      conditional claims, counters, clearing `rate_key`, polling every 3s.
- [ ] **E8** Matching check: the same headline 3×, 3 outlets on the same story, and 2
      look-alike events that are different ("raises" vs "holds"). Record cosine scores and
      outcomes, and adjust the thresholds if needed.

## Phase F — End to end
- [ ] **F1** Run SPEC §14 steps 1–15 in Chrome, using two browser profiles for the cache steps.
- [ ] **F2** Repeat steps 2–5 in Edge and Brave. Note any differences.
- [ ] **F3** Privacy checks from SPEC §11: manifest, Network tab, storage cleared, no raw IP
      in any table, no `#t=` in history or shared links.
- [ ] **F4** First integrity report (SPEC §13.2): grounding and unverified rates,
      loaded-word flags, JSON retry rate, hit rates by `match_type`, tokens per dig, and a
      review by you of 10 trails for payoff > hook.

## Phase G — Mount at i-dig.io/exploring (same as /movies)
This can wait until F passes, but it's still part of this sprint so the URL model is proven,
not just planned.
- [ ] **G1** Create a Vercel project for `exploring_app` with its root directory set to
      `iDIGcore_w_domains/exploring_app`. Env vars: `NEXT_PUBLIC_BASE_PATH=/exploring`,
      `SUPABASE_URL`, `SUPABASE_SERVICE_KEY`, `EXPLORING_HOURLY_CAP`,
      `EXPLORING_RATE_SECRET`, `EXPLORING_DAILY_TOKEN_BUDGET`, **`EXPLORING_DEMO_MODE=on`**
      and **`EXPLORING_ALLOWED_IPS=<your IP>`**. Check that `<project>.vercel.app/exploring`
      loads. **The demo gate must be deployed before G2 makes the app public.**
- [ ] **G2** In `idig_website_new-build/vercel.json`, add the four `/exploring` +
      `/Exploring` rewrites from SPEC §4.8, **above** the `"/(.*)"` catch-all.
- [ ] **G3** Add an `/exploring` note next to the existing `/movies` proxy comments in
      `App.tsx` and `NavBar.tsx`. Add a nav link only if you want one.
- [ ] **G4** Check through the proxy: landing, snip and dig pages with their `_next` assets, a
      POST to `/exploring/api/snips` passing through with its body, **and that the real client
      IP reaches the app**. The archive's IndexedDB appears under the i-dig.io origin.
      **Test the gate from a phone on mobile data** (a different IP): snipping and undug
      trails get the demo message, and your shared links still open.
- [ ] **G5** Build the extension with `.env.production` and run SPEC §14 against i-dig.io.
      Digs only complete while the worker runs locally.

---

## Gate results (A8)
_(fill in: page · zoom · crop matches? · overlay visible in crop? · notes)_

| Page | 100% | 150% | Notes |
|---|---|---|---|
| apnews.com article | | | |
| nytimes.com article | | | |
| bbc.com article | | | |
| Substack post | | | |
| Sticky-header page | | | |
| `chrome://extensions` (should show "can't run") | | n/a | |

## Notes / decisions during sprint
- **2026-09-24, Phase A build choices:**
  - The overlay is built as its own IIFE (`vite.overlay.config.ts`), because
    `executeScript` injects files as classic scripts.
  - The source URL is stashed in `storage.session` at icon click (`pending:<tabId>`), so a
    service-worker restart between the click and the selection doesn't lose it.
  - Enter also confirms a selection.
  - Stale snips are swept after 15 min, and closing the review window discards its snip.
  - The background logs a warning if screenshot width ≠ viewport × DPR, to catch
    crop-offset cases during A8.

## Sprint 2 (designed in SPEC §12)
- Share a whole path as one link, plus the **share card** (one question + its evidence)
- "Delete my snip from iDIG" button + `DELETE /exploring/api/snips/{id}`
- **My lens:** the observer sets their aspirations on their device, and the stored candidates
  are re-ranked in the browser (D29)

## Backlog
- Road less traveled slot, once follow counts exist (D26)
- Content signals: agreement across sources, left-out entities, frame differences, hub
  questions (SPEC §12)
- **Doors** into other iDIG domains, and one iDIG archive file across lenses
- Other ways in: typed topic, right-click "Dig this selection"
- Side panel review UI; Safari; Chrome Web Store listing
- **Worker hosting** for production (Railway, like the Movies API server?)
- Refresh popular stale digs ahead of demand; Turnstile if abuse appears
- TuneAble: anonymous count signals once real data exists
- **iDIG Deeper** (resource/commerce enrichment layer): prototyped in the extension's mock UI
  (`extension/src/review/mockDeeper.ts`), not yet specified for the real pipeline. Must ship
  together with the acute-personal-crisis guard (SPEC §7.6) — that guard is what makes it safe
  to build at all.
- **Related, separate project:** migrate Movies onto core/domains and retire its Supabase
  project. Also fix the `projectId` import bug in `useSavedFilms.ts`.
