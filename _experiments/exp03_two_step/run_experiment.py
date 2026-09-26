"""
Experiment 03: gemini-3.8-flash (search + response schema in one call), sharper question craft.

Variant C (one call):  grounded research writes the dig AND the trail candidates.
Variant D (two calls): grounded research writes the dig only; a separate ungrounded
                       "question writer" call (more thinking, one job) writes the trails.
Both: core picks 4 (best per dimension, 4th by MMR, moves distinct), then trail #1 gets a
question dig (same variant pattern), and its trails are loop-filtered against the path.

Run:  python run_experiment.py   (GEMINI_API_KEY from env)
"""
import json
import os
import sys
import time
import urllib.error
import urllib.request
from collections import Counter
from pathlib import Path

from google import genai
from google.genai import types

HERE = Path(__file__).resolve().parent
CORE = HERE.parents[2] / "iDIGcore_w_domains"
sys.path.insert(0, str(CORE))
from idig_logic_core.core.vectors import cosine_similarity  # noqa: E402

HEADLINE = "United Nations General Assembly: Iran, Trump, Ukraine"
SOURCE_DOMAIN = "cnn.com"
DATE = "2026-09-23"

MODEL = "gemini-3.8-flash"
EMBED_MODEL = "gemini-embedding-001"
EMBED_DIMS = 768
MMR_LAMBDA = 0.7
LOOP_THRESHOLD = 0.90
DIMENSIONS = ("semantic", "experiential", "social")
MOVES = ["tension", "mechanism", "precedent", "frame", "stakes", "hidden", "scale", "unknowns"]

# ---------- schemas ----------
TRAIL_ITEM = {"type": "object", "properties": {
    "move": {"type": "string", "enum": MOVES},
    "dimension": {"type": "string", "enum": list(DIMENSIONS)},
    "question": {"type": "string"}, "hook": {"type": "string"}, "seed": {"type": "string"}},
    "required": ["move", "dimension", "question", "hook", "seed"]}
TRAILS = {"type": "array", "items": TRAIL_ITEM}

HEADLINE_FIELDS = {
    "what_happened": {"type": "string"}, "why_now": {"type": "string"}, "at_stake": {"type": "string"},
    "contested": {"type": "string"}, "to_watch": {"type": "array", "items": {"type": "string"}},
    "coverage": {"type": "string", "enum": ["broad", "thin", "disputed"]}}
QUESTION_FIELDS = {
    "short_answer": {"type": "string"}, "deeper_story": {"type": "string"},
    "evidence": {"type": "array", "items": {"type": "string"}}, "still_open": {"type": "string"},
    "coverage": {"type": "string", "enum": ["broad", "thin", "disputed"]}}


def schema(fields: dict, with_trails: bool) -> dict:
    props = dict(fields)
    if with_trails:
        props["trails"] = TRAILS
    return {"type": "object", "properties": props, "required": list(props)}


# ---------- prompts ----------
RULES = f"""You are the research engine for iDIG Exploring. ALWAYS run Google Search before writing,
even if you think you know the answer. Your memory is out of date; only search results count.
- Research across several outlets. Do not open or quote the observer's source page.
- People's titles and roles MUST come from the search results as of {DATE}, never from memory.
- Say plainly when coverage is thin or disputed. Don't invent facts beyond the search results.
- Neutral tone, no editorializing. The same text for every reader."""

HEADLINE_LENGTHS = """Lengths: what_happened 1-2 sentences; why_now, at_stake, contested each max ~60 words;
to_watch max 3 concrete items."""
QUESTION_LENGTHS = """Lengths: short_answer 2-3 sentences that actually answer; deeper_story max ~120 words;
evidence max 4 concrete facts/cases/numbers; still_open max ~50 words."""

QUESTION_CRAFT = """TRAILS ARE QUESTIONS that turn a passive reader into a curious one.

Each trail has:
- "question": aims at the enduring puzzle BENEATH the news. It would still be worth asking a
  year from now and could be reached from many headlines. Max ~16 words.
- "hook": max ~15 words. A SPECIFIC fact from this story that makes the question urgent right
  now. It must add something the question doesn't say. Never restate the question.
- "seed": a neutral search query for researching the question on its own.

A great question opens a gap the reader didn't know existed:
- It contains a twist: "why would...", "how can... when...", "even though", "yet", "despite".
- It names something concrete: a mechanism, an institution, a place, a pattern.
- It's answerable with evidence (history, data, how a system works). No opinion, no "should".
- A bored person reading it thinks "huh... I don't actually know that."

Reject these patterns outright:
- Textbook abstractions: "How do nations balance sovereignty with cooperation?"
- Impact templates: "What are the impacts/effects/implications of X on Y?"
- Anything the dig already answers, anything yes/no, anything with "you"/"your".

Calibration, from an UNRELATED story about a drought:
  weak:   "What are the effects of the drought on farmers?"
  strong: "Why do food prices rise in countries where it hasn't rained any less?"
          hook: "Wheat futures jumped 9% this week, mostly on forecasts, not harvests."
  weak:   "How are governments responding to the drought?"
  strong: "Why can a city with less rainfall end up with more water than its neighbor?"
          hook: "The two most-restricted counties this summer sit beside a reservoir."

Moves (one per trail): tension (the contradiction inside the story), mechanism (how the
underlying thing works), precedent (when it happened before and how it ended), frame (how
sides tell it differently), stakes (what changes on the ground), hidden (who isn't in the
headline but matters), scale (how big, against something familiar), unknowns (what isn't
settled and what evidence would settle it).
Dimensions: semantic (mechanism, precedent, scale), experiential (stakes, life under it),
social (tension, frame, hidden actors, incentives).

Write 8 trails: at least 2 per dimension, at least 6 different moves."""

HEADLINE_PROMPT = f"""Headline an observer snipped: "{HEADLINE}"
Source outlet: {SOURCE_DOMAIN} (captured {DATE})
Research the news event this headline describes, as of {DATE}."""

QUESTION_PROMPT = """Answer this question as a stand-alone explainer: "{question}"
Research seed: {seed}
Context, ONLY to identify what is meant (don't write about this story):
Root headline: "{headline}" ({date}); trail so far: {path}"""

WRITER_PROMPT = """Here is grounded research an observer just read:
{research}

Write the trails that lead deeper from it. {extra}
Use only facts that appear in the research for hooks."""


# ---------- calls ----------
def key() -> str:
    return os.environ["GEMINI_API_KEY"]


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **k):
        return None


def resolve_redirect(url: str) -> str:
    try:
        urllib.request.build_opener(_NoRedirect).open(urllib.request.Request(url, method="HEAD"), timeout=5)
    except urllib.error.HTTPError as e:
        if e.code in (301, 302, 303, 307, 308) and e.headers.get("Location"):
            return e.headers["Location"]
    except Exception:
        pass
    return url


def usage(resp) -> dict:
    u = resp.usage_metadata
    return {"prompt": u.prompt_token_count or 0, "tool_use_prompt": u.tool_use_prompt_token_count or 0,
            "output": u.candidates_token_count or 0, "thinking": u.thoughts_token_count or 0,
            "total": u.total_token_count or 0}


def call(client, system: str, prompt: str, resp_schema: dict, grounded: bool, thinking: str) -> dict:
    """One retry on unparseable JSON; the retry's tokens are added to the usage."""
    first = _call(client, system, prompt, resp_schema, grounded, thinking)
    if first["result"] is not None:
        first["retried"] = False
        return first
    second = _call(client, system, prompt, resp_schema, grounded, thinking)
    second["usage"] = {k: second["usage"][k] + first["usage"][k] for k in second["usage"]}
    second["retried"], second["first_parse_error"] = True, first.get("parse_error")
    return second


def _call(client, system: str, prompt: str, resp_schema: dict, grounded: bool, thinking: str) -> dict:
    cfg = types.GenerateContentConfig(
        system_instruction=system, temperature=0.7 if not grounded else 0.4,
        response_mime_type="application/json", response_schema=resp_schema,
        tools=[types.Tool(google_search=types.GoogleSearch())] if grounded else None,
        thinking_config=types.ThinkingConfig(thinking_level=thinking),
    )
    t0 = time.time()
    resp = client.models.generate_content(model=MODEL, contents=prompt, config=cfg)
    out = {"usage": usage(resp), "seconds": round(time.time() - t0, 1),
           "finish_reason": str(resp.candidates[0].finish_reason), "thinking_level": thinking,
           "grounded": grounded}
    try:
        out["result"] = json.loads(resp.text)
    except Exception as e:
        out["result"], out["parse_error"], out["raw_text"] = None, f"{type(e).__name__}: {e}", resp.text
    if grounded:
        gm = resp.candidates[0].grounding_metadata
        chunks = list(gm.grounding_chunks or []) if gm else []
        cites = Counter(i for s in ((gm.grounding_supports or []) if gm else []) for i in (s.grounding_chunk_indices or []))
        out["search_queries"] = list(gm.web_search_queries or []) if gm else []
        out["sources_total"], out["sources_cited"] = len(chunks), len(cites)
        out["sources_top5"] = [{"domain": chunks[i].web.title, "url": resolve_redirect(chunks[i].web.uri), "cited": n}
                               for i, n in cites.most_common(5) if i < len(chunks) and chunks[i].web]
    return out


def embed(client, texts):
    r = client.models.embed_content(model=EMBED_MODEL, contents=texts, config=types.EmbedContentConfig(
        output_dimensionality=EMBED_DIMS, task_type="SEMANTIC_SIMILARITY"))
    return [list(e.values) for e in r.embeddings]


def pick(client, anchor: str, cands: list, path: list) -> tuple[list, list]:
    vecs = embed(client, [anchor] + [f"{c['question']} {c['hook']}" for c in cands] + [p["question"] for p in path])
    a, cv, pv = vecs[0], vecs[1:1 + len(cands)], vecs[1 + len(cands):]
    pool, dropped = [], []
    for c, v in zip(cands, cv):
        c["relevance"], c["_v"] = round(cosine_similarity(v, a), 4), v
        loop = max((cosine_similarity(v, p) for p in pv), default=0.0)
        (dropped.append({"question": c["question"], "loop": round(loop, 3)}) if loop >= LOOP_THRESHOLD else pool.append(c))
    picked = []
    used = lambda: {p["move"] for p in picked}  # noqa: E731
    for d in DIMENSIONS:
        opts = [c for c in pool if c["dimension"] == d and c not in picked and c["move"] not in used()]
        if opts:
            b = max(opts, key=lambda c: c["relevance"]); b["picked_by"] = f"best {d}"; picked.append(b)
    while len(picked) < 4:
        rest = [c for c in pool if c not in picked and c["move"] not in used()] or [c for c in pool if c not in picked]
        if not rest:
            break
        mmr = lambda c: MMR_LAMBDA * c["relevance"] - (1 - MMR_LAMBDA) * max(cosine_similarity(c["_v"], p["_v"]) for p in picked)  # noqa: E731
        n = max(rest, key=mmr); n["picked_by"] = f"MMR {mmr(n):.3f}"; picked.append(n)
    for r, c in enumerate(picked, 1):
        c["rank"] = r
    for c in cands:
        c.pop("_v", None)
    return picked, dropped


def dig(client, variant: str, fields: dict, lengths: str, prompt: str, extra_writer: str) -> tuple[dict, list]:
    """Returns (record, trail candidates)."""
    if variant == "C":
        r = call(client, RULES + "\n" + lengths + "\n\n" + QUESTION_CRAFT, prompt, schema(fields, True), True, "low")
        return {"calls": [r]}, (r["result"] or {}).get("trails", [])
    research = call(client, RULES + "\n" + lengths, prompt, schema(fields, False), True, "low")
    writer = call(client, QUESTION_CRAFT, WRITER_PROMPT.format(
        research=json.dumps(research["result"], ensure_ascii=False), extra=extra_writer),
        {"type": "object", "properties": {"trails": TRAILS}, "required": ["trails"]}, False, "medium")
    return {"calls": [research, writer]}, (writer["result"] or {}).get("trails", [])


def run(client, variant: str) -> dict:
    print(f"[{variant}] headline dig...")
    rec, cands = dig(client, variant, HEADLINE_FIELDS, HEADLINE_LENGTHS, HEADLINE_PROMPT, "")
    res = rec["calls"][0]["result"]
    shown, _ = pick(client, f"{HEADLINE}. {res['what_happened']} {res['why_now']}", cands, [])
    out = {"headline_dig": rec, "candidates": cands,
           "shown": [{k: c[k] for k in ("rank", "move", "dimension", "question", "hook", "picked_by")} for c in shown]}
    first = shown[0]
    print(f"[{variant}] question dig: {first['question']!r}")
    rec2, cands2 = dig(client, variant, QUESTION_FIELDS, QUESTION_LENGTHS, QUESTION_PROMPT.format(
        question=first["question"], seed=first["seed"], headline=HEADLINE, date=DATE, path=first["question"]),
        f'The question just answered was: "{first["question"]}". Hooks tie new questions to that answer.')
    r2 = rec2["calls"][0]["result"]
    shown2, dropped = pick(client, f"{first['question']} {r2['short_answer']}", cands2, shown)
    out.update({"trail1_dig": rec2, "trail1_candidates": cands2, "trail1_dropped_loops": dropped,
                "trail1_shown": [{k: c[k] for k in ("rank", "move", "dimension", "question", "hook", "picked_by")} for c in shown2]})
    tot = lambda recs: {k: sum(c["usage"][k] for r in recs for c in r["calls"]) for k in ("prompt", "tool_use_prompt", "output", "thinking", "total")}  # noqa: E731
    out["token_totals"] = {"headline": tot([rec]), "trail1": tot([rec2])}
    return out


def main():
    client = genai.Client(api_key=key())
    results = {"headline": HEADLINE, "date": DATE, "model": MODEL, "variants": {}}
    for v in ("C", "D"):
        results["variants"][v] = run(client, v)
    (HERE / "results.json").write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
    print("done -> results.json")


if __name__ == "__main__":
    main()
