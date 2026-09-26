# Experiment 01 — UNGA headline → dig → 4 trails → trail #1 dig

**Date:** 2026-09-23 · **Script:** `run_experiment.py` · **Raw output:** `results.json`
**Follows:** SPEC v3 §7 (one grounded call writes the dig + trail candidates, core picks 4, neutral child dig)

**Headline used:** "United Nations General Assembly: Iran, Trump, Ukraine" (cnn.com, 2026-09-23).
This is a stand-in taken from the URL, because CNN returned HTTP 451 to the fetch. That
matches D11 (the server never reads the source page), and in real use the observer snips the
headline. It's a deliberately thin, live-blog-style headline.

**Settings:** gemini-2.5-flash + google_search, thinking budget 0, temperature 0.2,
max 1500 output tokens. The JSON came from the prompt, not a response schema.
Embeddings: gemini-embedding-001 at 768 dimensions, one batch call per dig. MMR λ 0.7.
**Key:** borrowed from `iDIG_demo_resonance-engine-with-attractor/.env` through an
environment variable. The core repo's `.env` only has the `your_…` placeholder.

## Results

### Headline dig
> The 81st United Nations General Assembly (UNGA), which began on September 22, 2026, has been
> significantly shaped by ongoing international conflicts and geopolitical tensions. Key
> discussions have revolved around the war between the United States and Iran, the continuing
> conflict in Ukraine, and statements made by ~~former~~ U.S. President Donald Trump…

Coverage: broad. 7 search queries, 25 grounding sources.

### The 4 trails core picked (9 candidates, 3/3/3 by dimension)
| # | Dimension | Trail | Relevance | Picked by |
|---|---|---|---|---|
| 1 | semantic | Details of the US-Iran War | 0.847 | best semantic |
| 2 | experiential | Global Energy Market Impact of Conflicts | 0.852 | best experiential |
| 3 | social | UN's Role in Global Conflicts | 0.866 | best social |
| 4 | social | International Reactions to Trump's UN Speech | 0.858 | MMR (0.346) |

Not shown: Iran's Nuclear Program Status (0.800), Russia-Ukraine War Developments (0.824),
Civilian Impact of Iran War (0.823), Refugee Crisis from Ukraine War (0.801), Impact of AI on
Global Security Debates (0.840).

### Trail #1 dig: "Details of the US-Iran War" (seed: "US Iran war 2026 timeline")
> The war between the United States and Iran began on February 28, 2026, with coordinated U.S.
> and Israeli strikes against military and strategic sites in Iran, including nuclear
> installations and leadership targets. Iran quickly retaliated… Despite a Pakistan-brokered
> ceasefire in April and a memorandum of understanding in June, hostilities have continued
> intermittently, particularly concerning the Strait of Hormuz.

Its own 4 trails: Causes of US-Iran War 2026 (sem) · Civilian casualties US-Iran War 2026 (exp)
· Diplomatic efforts US-Iran War 2026 (soc) · Role of Israel in 2026 Iran conflict (soc, MMR).
3 search queries, 10 grounding sources.

## Numbers

| | Headline dig | Trail #1 dig |
|---|---|---|
| Prompt tokens | 364 | 468 |
| Tool-use (search results) tokens | 457 | 513 |
| Output tokens | 1,070 | 1,015 |
| Thinking tokens | 0 | 0 |
| **Total** | **1,891** | **1,996** |
| Search queries | 7 | 3 |
| Sources returned | 25 | 10 |
| Time | 8.2 s | 6.2 s |

Trail selection: 2 batch embedding calls of 10 texts each, and no generation. The fixed-size
context worked: the child dig cost about the same as the parent (D19).

## Findings

**Working as designed**
1. **One call does both jobs.** The dig and 9 well-formed, dimension-tagged candidates came
   back in one grounded call, and the JSON parsed on the first try both times.
2. **Core picked sensibly.** It chose one per dimension, and the MMR 4th slot went to a
   social trail about reactions, not a near-copy of trail 3.
3. **The child dig is neutral (D18).** It's a stand-alone explainer of the US-Iran war with
   no UNGA framing, so it can be reused by any path that reaches this topic.
4. **Thinking was off and nothing broke.** Cost is dominated by output tokens (~1,050 per dig).

**Problems to fix**
5. **A factual error: "former U.S. President Donald Trump."** He's the sitting president in
   2026. That's the model's prior leaking through, and a key point contradicts it. Fix:
   tell the prompt that titles and roles must come from the search results as of the date,
   not from memory. Test thinking budget 0 against a small budget (E6).
6. **`relates` lines don't relate.** They describe the trail ("Explores the origins…")
   instead of saying why it matters *for this headline*. That's the whole point of D18.
   Fix: "`relates` must name the connection to the headline in one clause, e.g. 'Trump
   defended the strikes at the UN, and this is how the war began.'"
7. **Child trails loop back to the parent.** "Civilian casualties" and "International
   reactions" reappear one level down. Fix in core: drop candidates whose cosine to any trail
   already shown on the path is ≥ ~0.9. That's pure math, no tokens.
8. **Trail candidates are ~40% of output tokens** (about 50 tokens each × 9). Options: ask
   for 6 (2 per dimension), or shorten `relates` to ~12 words. Test the effect on quality.
9. **Sources aren't usable as they are.**
   - The URLs are `vertexaisearch.cloud.google.com/grounding-api-redirect/…` links, which
     aren't permanent. The worker has to resolve each redirect to its final URL when it
     saves the dig.
   - The "title" is only the domain.
   - Quality is mixed: 4× youtube.com, detective-store.com, militaryspend.org.
   - 25 is too many to show.

   Fix: resolve the redirects, keep only the sources the answer actually cites (from grounding
   supports), rank them, show about 5, and consider a list of outlets to prefer or block.
10. **Clutter in titles.** "…2026" is appended to trail titles. Tell the prompt no years unless
    they're needed to tell things apart.
11. **Relevance scores bunch together** (0.80–0.87). Per-dimension picks still work, but
    relevance alone barely separates candidates. Revisit once there's follow-count data.

**To verify (policy and pricing)**
12. **Google's terms for Grounding with Google Search.** Check whether they require showing
    the Search Suggestions (`search_entry_point`) alongside grounded answers, and whether they
    limit storing grounded results and showing them to other users later. **This directly
    affects the shared cache (D14, D16).** Check before building Phase D/E.
13. **How grounding is billed:** per request or per search query. The headline dig ran 7
    queries, and a thin headline makes the model fan out.
