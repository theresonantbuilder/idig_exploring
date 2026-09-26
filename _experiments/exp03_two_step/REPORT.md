# Experiments 02 + 03: question-shaped trails

**Date:** 2026-09-23 · **Headline:** the stand-in from exp01 ("United Nations General Assembly:
Iran, Trump, Ukraine", cnn.com) · **Raw output:** `results.json` here and in `../exp02_questions/`

**Goal:** trails that are questions. Each has an evergreen, reusable **question** (the puzzle
beneath the news) plus a timely **hook** (a specific fact from this story), written to make a
not-very-curious reader curious. The dig uses a context-first structure: what happened / why
now / at stake / contested / to watch. Question digs use: short answer / deeper story /
evidence / still open.

## Exp 02: gemini-2.5-flash (the spec's model), thinking 0 vs 1024

- **Thinking 0:** the questions were better than exp01's topic lists but still bland and
  academic ("How do nations balance national sovereignty with the need for international
  cooperation?"). The "former President" error came back, and the child dig's JSON failed to parse.
- **Thinking 1024:** titles were correct, but it ignored the JSON instruction, wrote prose,
  and ran out of tokens.
- **Root cause:** gemini-2.5-flash **rejects search + a JSON response schema in the same
  call** (400: "Tool use with a response mime type: 'application/json' is unsupported").

## Probe: which models this key can use

The key has gemini-3-flash-preview, 3.5, 3.6, 3.7 and **3.8-flash**, and 3.x-pro. All the 3.x
Flash models tested **accept search + a response schema together** and got Trump's title
right. They think a lot by default (650–1,600 thinking tokens), so `thinking_level` has to be set.

## Exp 03: gemini-3.8-flash, one call (C) vs two calls (D)

- **C:** one grounded call writes the dig + 8 trail candidates, with thinking "low".
- **D:** a grounded research call (thinking "low") writes the dig, then an ungrounded
  "question writer" call (thinking "medium") writes the trails from that research.

### Question quality: a big jump

**C, the 4 shown (core-picked):**
1. *precedent*: When has public General Assembly brinkmanship ever produced a verified
   multilateral peace accord afterwards?
2. *stakes*: How do local energy workforces survive when refineries and grids become primary
   diplomatic bargaining chips?
3. *tension*: **Why do leaders deploy total destruction rhetoric while simultaneously
   conducting quiet bilateral negotiations in adjoining rooms?** Hook: *Hours after threatening
   Iran's annihilation at the podium, US envoys met Iranian officials backstage.*
4. *mechanism*: How do host country visa obligations actually constrain United Nations
   diplomacy during active military conflicts? Hook: *Pezeshkian's attendance remained
   uncertain until Washington issued a last-minute travel visa.*

Also a candidate but not shown: *hidden*: Which backchannel intermediaries carry actual
weight when warring parties refuse direct communication? Hook: *…Pakistani and Qatari envoys
shuffling proposals between hotel delegations.*

**C, trail #1 dig** ("When has GA brinkmanship ever produced a peace accord?"): *virtually
never.* Durable accords (Camp David 1978, Oslo 1993, Dayton 1995, JCPOA 2015) were negotiated
away from the cameras. The 1962 Cuban Missile Crisis was settled through the private
Kennedy–Dobrynin channel, not Stevenson's UN showdown. Public threats create "audience
costs" that make compromise harder at home. Still open: whether "madman" rhetoric ever
speeds up concessions.

**D, trail #1 dig** ("How does the UN Charter address a member threatening annihilation?"):
Article 2(4) bans the *threat* of force, not only its use. The ICJ's 1996 nuclear weapons
opinion held that a threat is unlawful whenever the underlying force would be. Article 51
self-defense needs an armed attack. Chapter VII enforcement is usually blocked by a veto.
Its child trails include: *Why do nuclear powers argue deterrence posturing is lawful while
Charter rules ban threats?*

These read like the product: evergreen questions that someone could arrive at from many
headlines, and answers that give real context.

### Cost

| | C, headline | C, trail #1 | D, headline | D, trail #1 |
|---|---|---|---|---|
| Calls | 1 (+1 JSON retry) | 1 | 2 (+1 retry) | 2 |
| Thinking tokens | 0 | 0 | 2,928 (writer) | 1,938 (writer) |
| Output tokens | 2,276* | 1,164 | 1,473 | 1,083 |
| **Total tokens** | 3,848* | **2,001** | **5,734** | **4,351** |
| Time | 7.4 s | 8.6 s | 17.7 s | 18.3 s |

\* includes one retry, so a single clean attempt is about 2,000 tokens.

**C costs about the same per dig as exp01's generic version (~2,000 tokens) and produces far
better trails. D costs 2–3× more,** almost all of it in the writer's thinking, and its hooks
are weaker because the writer only sees the research text, not the search results.

### Problems found

1. **Grounding isn't guaranteed on 3.x.** The model decides for itself whether to search.
   D's headline research and C's trail #1 dig reported **0 search queries and 0 cited
   sources**, even with "ALWAYS search first" in the prompt. D's dig still contains
   specific 2026 claims ("delegates walked out"), and we can't verify where they came from.
   **Rule needed:** a grounded call with 0 queries or 0 cited sources is a failure. Retry once,
   then mark the dig as unverified or reject it. Never cache it as a trusted dig.
2. **Unparseable JSON about 1 in 3 grounded calls,** even with a schema. Citation markers such
   as `[1.2.2]` leak into the text. Strip them, forbid them in the prompt, and keep the one
   retry.
3. **Some questions are heavy with jargon** ("empirical metrics distinguish between
   post-strike military degradation and long-term political submission"). Add a
   plain-language limit: ≤ 14 words, everyday words.
4. **Some hooks may not be grounded** ("regional diesel plants burned across battle lines").
   A hook must be a fact from the cited sources.
5. **Relevance puts the best question third.** The tension question is the one most likely to
   spark curiosity, and it was ranked #3 because the order follows relevance to the story.
   Option: the call rates each candidate's "spark" 1–5 (about 8 tokens each), and core orders
   the 4 shown by spark, while still picking by dimension and move.
6. `tool_use_prompt_token_count` is always 0 on 3.x, so check how search is billed on 3.x
   (per query?) against current pricing.

## Recommendation for the spec

- **Model:** gemini-3.x Flash (3.8-flash today) with `thinking_level="low"`, search, and a
  response schema in **one call** (variant C). This changes D1 and D23. **Drop the separate
  question-writer call.**
- **Trails:** `{move, dimension, question, hook, seed}` with the question-craft rules above.
  Core picks the 4: best per dimension, the 4th by MMR, all moves distinct, loops dropped.
- **Dig shapes:** headline = what happened / why now / at stake / contested / to watch;
  question = short answer / deeper story / evidence / still open.
- **Guards:** require ≥ 1 query and ≥ 1 cited source; strip citation markers; one retry.
- **Still to test:** ordering by spark rating, the plain-language limit, and the same run on
  3 more headlines (a thin one, a non-political one, one that isn't breaking news).
