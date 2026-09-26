"""
Experiment 02: question-shaped trails ("moves"), context-first dig structure.

Changes from exp01 (see ../exp01_unga/REPORT.md):
- Dig structure: what_happened / why_now / at_stake / contested / to_watch
- Trails are evergreen QUESTIONS + a timely HOOK, tagged with a move and a dimension
- Core picks 4: best per dimension, 4th by MMR, all 4 moves distinct
- Child candidates too close to trails already on the path are dropped (no loops)
- Titles/roles must come from search results as of the date (exp01 "former President" bug)
- Sources: only cited chunks, redirect resolved via Location header, top 5
- Two variants: thinking budget 0 vs 1024

Run:  python run_experiment.py   (GEMINI_API_KEY from env, else iDIGcore_w_domains/.env)
"""
import json
import os
import re
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
CAPTURED = "2026-09-23"

RESEARCH_MODEL = "gemini-2.5-flash"
EMBED_MODEL = "gemini-embedding-001"
EMBED_DIMS = 768
MAX_OUTPUT_TOKENS = 2000
MMR_LAMBDA = 0.7
LOOP_THRESHOLD = 0.90
DIMENSIONS = ("semantic", "experiential", "social")
VARIANTS = {"A_thinking_0": 0, "B_thinking_1024": 1024}

QUESTION_CRAFT = """TRAILS ARE QUESTIONS. Each trail has two parts:
- "question": aimed at the enduring puzzle BENEATH the news, so it would still be worth
  asking a year from now and could be reached from many different headlines.
- "hook": one short line (max ~15 words) tying that question to THIS story. The hook is
  where today's specifics go.

What makes a question worth following (it must open a gap the reader didn't know was there):
- Concrete: it names a specific thing, mechanism, place, or pattern. Never "What are the
  implications of...", "What is the impact of...", "How does this affect...".
- Surprising: it points at a contradiction, an anomaly, or a "wait, why?" that a
  reasonable person wouldn't have thought to ask.
- Answerable with evidence: history, data, how systems work. Never "should", never opinion,
  never a loaded premise that takes a side.
- Not already answered by the dig above it.
- Not personal: no "you"/"your", no advice. Not yes/no. Max ~16 words, no jargon.

Examples from an UNRELATED story (a headline about a drought), for calibration only:
  weak:   "What are the effects of the drought on farmers?"
  strong: "Why do food prices rise in countries where it hasn't rained any less?"
  weak:   "How are governments responding to the drought?"
  strong: "Why do some regions run out of water while their neighbors, with less rain, don't?"

Each trail uses one MOVE:
- tension     the contradiction or paradox inside the story
- mechanism   how the underlying thing actually works
- precedent   when this happened before, and how it ended
- frame       how different sides or countries tell it differently
- stakes      what it changes on the ground, concretely
- hidden      who or what isn't in the headline but matters
- scale       how big this really is, compared with something familiar
- unknowns    what isn't settled, and what evidence would settle it

And one DIMENSION: semantic (mechanism, precedent, scale), experiential (stakes, what life
is like under it), social (tension, frame, hidden actors, incentives).

Give 8 trail candidates: at least 2 per dimension, at least 5 different moves. Each also gets
"seed": a neutral search query for researching the question on its own."""

RULES = """You are the research engine for iDIG Exploring. Use Google Search. Rules:
- Research across several outlets. Do not open or quote the observer's source page.
- People's titles and roles MUST come from the search results as of {date}, never from
  memory. If unsure of a title, use the name alone.
- Say plainly when coverage is thin or disputed, and set "coverage".
- Do not invent facts beyond what search results support. Neutral tone, no editorializing.
- Write the same text for every reader. No years in questions unless needed to tell things apart.
- Return ONLY a JSON object, no markdown fences."""

HEADLINE_SHAPE = """Shape:
{{
  "what_happened": "1-2 sentences",
  "why_now": "what led to this moment, max ~60 words",
  "at_stake": "what actually hangs on it, max ~60 words",
  "contested": "where accounts or interpretations differ, max ~60 words",
  "to_watch": ["max 3 concrete things that would change the picture"],
  "coverage": "broad | thin | disputed",
  "trails": [{{"move": "...", "dimension": "...", "question": "...", "hook": "...", "seed": "..."}}]
}}"""

QUESTION_SHAPE = """Shape:
{{
  "short_answer": "2-3 sentences that actually answer the question",
  "deeper_story": "the explanation, max ~120 words",
  "evidence": ["max 4 concrete facts, cases, or numbers"],
  "still_open": "what isn't settled, max ~50 words",
  "coverage": "broad | thin | disputed",
  "trails": [{{"move": "...", "dimension": "...", "question": "...", "hook": "...", "seed": "..."}}]
}}
For these trails, the "hook" ties each new question to the question just answered."""

HEADLINE_PROMPT = """Headline an observer snipped: "{headline}"
Source outlet: {domain} (captured {date})
Research the news event this headline describes, as of {date}."""

QUESTION_PROMPT = """Answer this question as a stand-alone explainer: "{question}"
Research seed: {seed}

Context, ONLY to identify what is meant (do not write about this story):
Root headline: {root_headline} ({date})
Trail so far: {trail_path}"""


def load_key() -> str:
    if os.environ.get("GEMINI_API_KEY"):
        return os.environ["GEMINI_API_KEY"]
    for line in (CORE / ".env").read_text(encoding="utf-8").splitlines():
        m = re.match(r"\s*GEMINI_API_KEY\s*=\s*(.+)\s*$", line)
        if m:
            return m.group(1).strip().strip('"').strip("'")
    raise SystemExit("GEMINI_API_KEY not found")


def parse_json(text: str) -> dict:
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip())
    return json.loads(text[text.find("{"): text.rfind("}") + 1])


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **k):
        return None


def resolve_redirect(url: str) -> str:
    """Read the Location header of Google's grounding redirect without visiting the target."""
    opener = urllib.request.build_opener(_NoRedirect)
    try:
        opener.open(urllib.request.Request(url, method="HEAD"), timeout=5)
    except urllib.error.HTTPError as e:
        if e.code in (301, 302, 303, 307, 308) and e.headers.get("Location"):
            return e.headers["Location"]
    except Exception:
        pass
    return url


def research(client, system: str, prompt: str, thinking_budget: int) -> dict:
    config = types.GenerateContentConfig(
        system_instruction=system,
        temperature=0.4,
        max_output_tokens=MAX_OUTPUT_TOKENS + thinking_budget,
        tools=[types.Tool(google_search=types.GoogleSearch())],
        thinking_config=types.ThinkingConfig(thinking_budget=thinking_budget),
    )
    t0 = time.time()
    resp = client.models.generate_content(model=RESEARCH_MODEL, contents=prompt, config=config)
    elapsed = round(time.time() - t0, 1)

    cand = resp.candidates[0]
    gm = cand.grounding_metadata
    chunks = list(gm.grounding_chunks or []) if gm else []
    cites = Counter()
    for sup in (gm.grounding_supports or []) if gm else []:
        for i in sup.grounding_chunk_indices or []:
            cites[i] += 1
    sources = []
    for i, n in cites.most_common(5):
        if i < len(chunks) and chunks[i].web:
            sources.append({"domain": chunks[i].web.title, "url": resolve_redirect(chunks[i].web.uri),
                            "cited_times": n})

    u = resp.usage_metadata
    raw = resp.text or ""
    try:
        result, err = parse_json(raw), None
    except Exception as e:
        result, err = None, f"{type(e).__name__}: {e}"
    return {
        "result": result, "parse_error": err, "raw_text": raw if err else None,
        "sources_top5": sources, "sources_total": len(chunks), "sources_cited": len(cites),
        "search_queries": list(gm.web_search_queries or []) if gm else [],
        "finish_reason": str(cand.finish_reason),
        "usage": {"prompt": u.prompt_token_count, "tool_use_prompt": u.tool_use_prompt_token_count,
                  "output": u.candidates_token_count, "thinking": u.thoughts_token_count or 0,
                  "total": u.total_token_count},
        "seconds": elapsed,
    }


def embed(client, texts):
    resp = client.models.embed_content(
        model=EMBED_MODEL, contents=texts,
        config=types.EmbedContentConfig(output_dimensionality=EMBED_DIMS, task_type="SEMANTIC_SIMILARITY"))
    return [list(e.values) for e in resp.embeddings]


def pick_trails(client, anchor_text: str, cands: list[dict], path_trails: list[dict]) -> tuple[list, list]:
    """Best per dimension, 4th by MMR; moves distinct; drop loops back to the path."""
    texts = [anchor_text] + [f"{c['question']} {c['hook']}" for c in cands] + [t["question"] for t in path_trails]
    vecs = embed(client, texts)
    anchor, cvecs, pvecs = vecs[0], vecs[1:1 + len(cands)], vecs[1 + len(cands):]

    dropped = []
    pool = []
    for c, v in zip(cands, cvecs):
        c["relevance"] = round(cosine_similarity(v, anchor), 4)
        c["_v"] = v
        loop = max((cosine_similarity(v, p) for p in pvecs), default=0.0)
        if loop >= LOOP_THRESHOLD:
            dropped.append({"question": c["question"], "loop_similarity": round(loop, 4)})
        else:
            pool.append(c)

    picked = []
    def moves():
        return {p["move"] for p in picked}
    for dim in DIMENSIONS:
        opts = [c for c in pool if c.get("dimension") == dim and c not in picked and c.get("move") not in moves()]
        if opts:
            best = max(opts, key=lambda c: c["relevance"])
            best["picked_by"] = f"best {dim}"
            picked.append(best)
    while len(picked) < 4:
        rest = [c for c in pool if c not in picked and c.get("move") not in moves()] or \
               [c for c in pool if c not in picked]
        if not rest:
            break
        def mmr(c):
            return MMR_LAMBDA * c["relevance"] - (1 - MMR_LAMBDA) * max(cosine_similarity(c["_v"], p["_v"]) for p in picked)
        nxt = max(rest, key=mmr)
        nxt["picked_by"] = f"MMR ({mmr(nxt):.3f})"
        picked.append(nxt)
    for r, c in enumerate(picked, 1):
        c["rank"] = r
    for c in cands:
        c.pop("_v", None)
    return picked, dropped


def run_variant(client, name: str, budget: int) -> dict:
    print(f"[{name}] headline dig...")
    sys_h = RULES.format(date=CAPTURED) + "\n\n" + HEADLINE_SHAPE + "\n\n" + QUESTION_CRAFT
    dig = research(client, sys_h, HEADLINE_PROMPT.format(headline=HEADLINE, domain=SOURCE_DOMAIN, date=CAPTURED), budget)
    out = {"thinking_budget": budget, "headline_dig": dig}
    if not dig["result"]:
        return out
    r = dig["result"]
    anchor = f"{HEADLINE}. {r['what_happened']} {r['why_now']}"
    shown, _ = pick_trails(client, anchor, r.get("trails", []), [])
    out["trails_shown"] = [{k: c.get(k) for k in ("rank", "move", "dimension", "question", "hook", "seed",
                                                  "relevance", "picked_by")} for c in shown]

    first = shown[0]
    print(f"[{name}] question dig for trail #1: {first['question']!r}")
    sys_q = RULES.format(date=CAPTURED) + "\n\n" + QUESTION_SHAPE + "\n\n" + QUESTION_CRAFT
    child = research(client, sys_q, QUESTION_PROMPT.format(
        question=first["question"], seed=first["seed"], root_headline=HEADLINE, date=CAPTURED,
        trail_path=first["question"]), budget)
    out["trail1_dig"] = child
    if child["result"]:
        cr = child["result"]
        cshown, dropped = pick_trails(client, f"{first['question']} {cr['short_answer']}",
                                      cr.get("trails", []), shown)
        out["trail1_trails_shown"] = [{k: c.get(k) for k in ("rank", "move", "dimension", "question", "hook",
                                                             "relevance", "picked_by")} for c in cshown]
        out["trail1_dropped_as_loops"] = dropped
    return out


def main():
    client = genai.Client(api_key=load_key())
    results = {"headline": HEADLINE, "source_domain": SOURCE_DOMAIN, "captured": CAPTURED,
               "model": RESEARCH_MODEL, "variants": {}}
    for name, budget in VARIANTS.items():
        results["variants"][name] = run_variant(client, name, budget)
    (HERE / "results.json").write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
    print("done -> results.json")


if __name__ == "__main__":
    main()
