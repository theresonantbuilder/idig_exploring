"""
Experiment 01: one headline -> dig -> 4 trails -> child dig for trail #1.

Follows SPEC.md v3 §7: one grounded research call that also writes trail
candidates, core picks 4 trails with embedding math (no AI call), then a
neutral child dig with the fixed-size context (D19).

Run from anywhere:  python run_experiment.py
Writes results.json next to this file.
"""
import json
import re
import sys
import time
from pathlib import Path

import numpy as np
from google import genai
from google.genai import types

HERE = Path(__file__).resolve().parent
CORE = HERE.parents[2] / "iDIGcore_w_domains"
sys.path.insert(0, str(CORE))
from idig_logic_core.core.vectors import cosine_similarity  # noqa: E402

HEADLINE = "United Nations General Assembly: Iran, Trump, Ukraine"
SOURCE_DOMAIN = "cnn.com"
CAPTURED = "2026-09-23"

RESEARCH_MODEL = "gemini-2.5-flash"
EMBED_MODEL = "gemini-embedding-001"
EMBED_DIMS = 768
THINKING_BUDGET = 0
MAX_OUTPUT_TOKENS = 1500
MMR_LAMBDA = 0.7
DIMENSIONS = ("semantic", "experiential", "social")

SYSTEM = """You are the research engine for iDIG Exploring. You explain news and topics
neutrally, using Google Search. Rules:
- Research across several outlets. Do not open or quote the observer's source page.
- Say so plainly when coverage is thin or disputed, and set "coverage".
- Do not invent facts beyond what search results support.
- Neutral tone, no editorializing. Write the same text for every reader.
- Return ONLY a JSON object, no markdown fences, in exactly this shape:
{
  "overview": "2-3 sentences, plain language",
  "key_points": ["at most 4 short points"],
  "context": "why this matters / background, at most ~80 words",
  "coverage": "broad | thin | disputed",
  "trail_candidates": [
    {"dimension": "semantic | experiential | social",
     "title": "at most ~6 words",
     "relates": "at most ~20 words: how this connects to the headline",
     "seed": "a neutral search query for researching this trail on its own"}
  ]
}
Give 6-9 trail_candidates with AT LEAST 2 per dimension:
- semantic = what happened, the facts, the substance
- experiential = who it affects and how, human impact
- social = who is involved, reactions, the debate"""

HEADLINE_PROMPT = """Headline an observer snipped: "{headline}"
Source outlet: {domain} (captured {date})
Research the news event this headline describes, as of {date}."""

TRAIL_PROMPT = """Root headline: {root_headline}
Parent overview: {parent_overview}
Trail so far: {trail_path}
Research this topic: {seed}

Write about THIS TOPIC ITSELF as a stand-alone explainer, not about the parent
story. The context above is only there to identify which topic is meant.
Trail candidates should lead deeper into this topic."""


def load_key() -> str:
    import os
    if os.environ.get("GEMINI_API_KEY"):
        return os.environ["GEMINI_API_KEY"]
    for line in (CORE / ".env").read_text(encoding="utf-8").splitlines():
        m = re.match(r"\s*GEMINI_API_KEY\s*=\s*(.+)\s*$", line)
        if m:
            return m.group(1).strip().strip('"').strip("'")
    raise SystemExit("GEMINI_API_KEY not found in iDIGcore_w_domains/.env")


def parse_json(text: str) -> dict:
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text)
    start, end = text.find("{"), text.rfind("}")
    return json.loads(text[start:end + 1])


def research(client, prompt: str) -> dict:
    config = types.GenerateContentConfig(
        system_instruction=SYSTEM,
        temperature=0.2,
        max_output_tokens=MAX_OUTPUT_TOKENS,
        tools=[types.Tool(google_search=types.GoogleSearch())],
        thinking_config=types.ThinkingConfig(thinking_budget=THINKING_BUDGET),
    )
    t0 = time.time()
    resp = client.models.generate_content(model=RESEARCH_MODEL, contents=prompt, config=config)
    elapsed = round(time.time() - t0, 1)

    cand = resp.candidates[0]
    gm = cand.grounding_metadata
    sources, seen = [], set()
    for ch in (gm.grounding_chunks or []) if gm else []:
        if ch.web and ch.web.uri not in seen:
            seen.add(ch.web.uri)
            sources.append({"title": ch.web.title, "url": ch.web.uri})

    u = resp.usage_metadata
    usage = {
        "prompt_tokens": u.prompt_token_count,
        "output_tokens": u.candidates_token_count,
        "thinking_tokens": u.thoughts_token_count,
        "tool_use_prompt_tokens": u.tool_use_prompt_token_count,
        "total_tokens": u.total_token_count,
    }
    raw = resp.text or ""
    try:
        result = parse_json(raw)
        parse_error = None
    except Exception as e:  # keep the raw text so the failure can be studied
        result, parse_error = None, f"{type(e).__name__}: {e}"

    return {
        "result": result,
        "parse_error": parse_error,
        "raw_text": raw if parse_error else None,
        "sources": sources,
        "search_queries": list(gm.web_search_queries or []) if gm else [],
        "finish_reason": str(cand.finish_reason),
        "usage": usage,
        "seconds": elapsed,
        "model": RESEARCH_MODEL,
    }


def embed(client, texts: list[str]) -> list[list[float]]:
    resp = client.models.embed_content(
        model=EMBED_MODEL,
        contents=texts,
        config=types.EmbedContentConfig(output_dimensionality=EMBED_DIMS, task_type="SEMANTIC_SIMILARITY"),
    )
    return [list(e.values) for e in resp.embeddings]


def pick_trails(client, overview: str, candidates: list[dict]) -> list[dict]:
    """SPEC §7.4: best per dimension, then one more by MMR. No generation call."""
    vecs = embed(client, [overview] + [f"{c['title']}. {c['relates']}" for c in candidates])
    ov, cvecs = vecs[0], vecs[1:]
    for c, v in zip(candidates, cvecs):
        c["relevance"] = round(cosine_similarity(v, ov), 4)
        c["_vec"] = v

    picked = []
    for dim in DIMENSIONS:
        pool = [c for c in candidates if c.get("dimension") == dim and c not in picked]
        if pool:
            best = max(pool, key=lambda c: c["relevance"])
            best["picked_by"] = f"best {dim}"
            picked.append(best)

    while len(picked) < 4:
        rest = [c for c in candidates if c not in picked]
        if not rest:
            break
        def mmr(c):
            redundancy = max(cosine_similarity(c["_vec"], p["_vec"]) for p in picked) if picked else 0.0
            return MMR_LAMBDA * c["relevance"] - (1 - MMR_LAMBDA) * redundancy
        nxt = max(rest, key=mmr)
        nxt["mmr_score"] = round(mmr(nxt), 4)
        nxt["picked_by"] = "MMR (best remaining, least redundant)"
        picked.append(nxt)

    for rank, c in enumerate(picked, 1):
        c["rank"] = rank
    for c in candidates:
        c.pop("_vec", None)
    return picked


def main():
    client = genai.Client(api_key=load_key())
    out = {"headline": HEADLINE, "source_domain": SOURCE_DOMAIN, "captured": CAPTURED,
           "settings": {"research_model": RESEARCH_MODEL, "thinking_budget": THINKING_BUDGET,
                        "max_output_tokens": MAX_OUTPUT_TOKENS, "embed_model": EMBED_MODEL,
                        "embed_dims": EMBED_DIMS, "mmr_lambda": MMR_LAMBDA}}

    print("1/3 headline dig (grounded research call)...")
    dig = research(client, HEADLINE_PROMPT.format(headline=HEADLINE, domain=SOURCE_DOMAIN, date=CAPTURED))
    out["headline_dig"] = dig
    if not dig["result"]:
        print("   parse failed:", dig["parse_error"])
        (HERE / "results.json").write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
        return

    print("2/3 core picks 4 trails (embeddings + math, no generation)...")
    cands = dig["result"].get("trail_candidates", [])
    trails = pick_trails(client, dig["result"]["overview"], cands)
    out["trails_shown"] = [{k: c.get(k) for k in ("rank", "dimension", "title", "relates", "seed",
                                                  "relevance", "picked_by", "mmr_score")} for c in trails]

    first = trails[0]
    print(f"3/3 child dig for trail #1: {first['title']!r}...")
    child = research(client, TRAIL_PROMPT.format(
        root_headline=HEADLINE,
        parent_overview=dig["result"]["overview"],
        trail_path=first["title"],
        seed=first["seed"],
    ))
    out["trail1_dig"] = child
    if child["result"]:
        ccands = child["result"].get("trail_candidates", [])
        ctrails = pick_trails(client, child["result"]["overview"], ccands)
        out["trail1_trails_shown"] = [{k: c.get(k) for k in ("rank", "dimension", "title", "relates",
                                                             "relevance", "picked_by")} for c in ctrails]

    (HERE / "results.json").write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    print("done -> results.json")


if __name__ == "__main__":
    main()
