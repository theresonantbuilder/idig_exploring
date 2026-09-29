"""
Experiment 04: the settled shape (SPEC v3.1-3.4) — claim/established/contested (§7.1),
evidence-first question digs (§7.2), open-length questions (§7.3), and the D27 grounding
guard + D25 loaded-word check + citation-marker stripping (§7.6), across 4 real headlines
picked to stress different cases (sprint E1):
  1. political, a clear claim to paint context around, not a verdict on
  2. non-political (science) — low-stakes, tests craft quality without political heat
  3. a thin live-blog headline — sparse, ongoing, no single clean claim
  4. not breaking news — a feature/update story, no ticking clock

Revised 2026-09-27: two-call shape, not one. Testing against this exact model/key showed
that Gemini's `grounding_metadata` (real citations) is not returned once the call also
requests JSON via `response_schema`/`response_mime_type` — even on prompts that are
structurally impossible to answer without a live search, the model still searches but the
API drops the attribution. So each dig is now: (1) a free-text RESEARCH call with the search
tool and no schema, which is the only call that needs to think or search, and whose real
`grounding_metadata` is what SPEC's `sources_top5`/citations come from; (2) a cheap SHAPE
call with the schema and no tools, which just reformats call 1's already-researched text
into the JSON structure and does no research of its own. This isn't more expensive than the
old one-call design — that design's own D27 retry loop was already paying for 2 attempts on
every dig, chasing grounding metadata that JSON mode can structurally never return.

Deliberately out of scope here: the acute-personal-crisis classifier (SPEC §7.6, added
v3.3). None of the 4 headlines below need it, and it deserves its own dedicated test with
a real, careful call about whether to include crisis-adjacent content at all — not
something to fold in here as an afterthought.

Run:  python run_experiment.py
(EXPLORING_GEMINI_API_KEY and EXPLORING_MODEL come from iDIGcore_w_domains/.env — the one
shared core env file, same one recruiting_domain/run.py loads. Exploring gets its own key,
a distinct variable in that same file, so its usage/quota/billing is isolated from Movies
and from Hiring/Knowledge Center/Jobs Manager, which share a different key.)
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

from dotenv import load_dotenv
from google import genai
from google.genai import types

HERE = Path(__file__).resolve().parent
CORE = HERE.parents[2] / "iDIGcore_w_domains"
sys.path.insert(0, str(CORE))
load_dotenv(CORE / ".env")
from idig_logic_core.core.vectors import cosine_similarity  # noqa: E402

# ---------- the 4 headlines (refresh these if this runs long after they were picked) ----------
HEADLINES = [
    {
        "label": "political_clear_claim",
        "headline": "Government can use Social Security data to identify noncitizen voters, Supreme Court rules",
        "source_domain": "washingtonpost.com",
        "date": "2026-09-25",
    },
    {
        "label": "non_political",
        "headline": "Scientists discover two tiny new snail species in Montenegro",
        "source_domain": "sciencedaily.com",
        "date": "2026-09-26",
    },
    {
        "label": "thin_live_blog",
        "headline": "LIVE UPDATES: Sara Duterte Impeachment Trial",
        "source_domain": "gmanetwork.com",
        "date": "2026-09-23",
    },
    {
        "label": "not_breaking_news",
        "headline": "NASA's Roman Space Telescope may now have enough fuel for at least 22 years of science",
        "source_domain": "nasa.gov",
        "date": "2026-09-20",
    },
]

MODEL = os.environ.get("EXPLORING_MODEL", "gemini-3.8-flash")
EMBED_MODEL = "gemini-embedding-001"
EMBED_DIMS = 768
MMR_LAMBDA = 0.7
LOOP_THRESHOLD = 0.85  # exp03 found 0.90 let a near-restatement through (§7.5)
DIMENSIONS = ("semantic", "experiential", "social")
MOVES = ["tension", "mechanism", "precedent", "frame", "stakes", "hidden", "scale", "unknowns"]

# D25: checked only in narrator-voice fields, never inside an attributed `position`.
LOADED_WORDS = [
    "theatrical", "grandstanding", "posturing", "slammed", "blasted", "so-called",
    "shocking", "stunning", "blistering", "scathing", "explosive",
]

# ---------- schemas (§7.1 / §7.2) — used only by the SHAPE call now ----------
CONTESTED_ITEM = {
    "type": "object",
    "properties": {"held_by": {"type": "string"}, "position": {"type": "string"}},
    "required": ["held_by", "position"],
}
TRAIL_ITEM = {
    "type": "object",
    "properties": {
        "move": {"type": "string", "enum": MOVES},
        "dimension": {"type": "string", "enum": list(DIMENSIONS)},
        "question": {"type": "string"}, "hook": {"type": "string"}, "seed": {"type": "string"},
    },
    "required": ["move", "dimension", "question", "hook", "seed"],
}
TRAILS = {"type": "array", "items": TRAIL_ITEM}

HEADLINE_FIELDS = {
    "claim": {"type": "string"},
    "what_happened": {"type": "string"},
    "why_now": {"type": "string"},
    "established": {"type": "array", "items": {"type": "string"}, "maxItems": 4},
    "contested": {"type": "array", "items": CONTESTED_ITEM, "maxItems": 4},
    "left_out": {"type": "string"},
    "still_unknown": {"type": "array", "items": {"type": "string"}, "maxItems": 3},
    "coverage": {"type": "string", "enum": ["broad", "thin", "disputed"]},
}
# No short_answer (dropped per v3.1 — it's where subjectivity concentrated). Lead with evidence.
QUESTION_FIELDS = {
    "evidence_story": {"type": "string"},
    "evidence": {"type": "array", "items": {"type": "string"}, "maxItems": 4},
    "interpretations": {"type": "array", "items": CONTESTED_ITEM, "maxItems": 4},
    "still_open": {"type": "string"},
    "coverage": {"type": "string", "enum": ["broad", "thin", "disputed"]},
}


def schema(fields: dict) -> dict:
    props = dict(fields)
    props["trails"] = TRAILS
    return {"type": "object", "properties": props, "required": list(props)}


# ---------- prompts (§7.3 / §7.4) ----------
def rules(date: str) -> str:
    return f"""You are the research engine for iDIG Exploring. ALWAYS run Google Search before
writing, even if you think you know the answer. Your memory is out of date; only search
results count.
- Research across several outlets, and across countries when the story is international.
  Do not open or quote the observer's source page.
- People's titles and roles MUST come from the search results as of {date}, never from memory.
- The narrator states evidence. Every judgment is attributed to who holds it (`held_by`) —
  never stated in the narrator's own voice. No loaded adjectives in the narrator's voice.
- Don't invent facts. Say plainly when coverage is thin or disputed.
- The same text for every reader. No citation markers like [1.2.2] in any text field.
- Write your findings as clear, well-labeled prose (not JSON) — a second pass will convert
  this into the final structured format, so cover every field below fully in your own words."""


HEADLINE_LENGTHS = """Cover, in prose: claim (1 sentence, restating the headline neutrally);
what_happened (1-2 sentences); why_now (~60 words); established (up to 4 facts multiple
sources agree on); contested (up to 4 attributed positions, ~30 words each — every judgment
in the dig lives here, attributed, never in your own voice); left_out (~60 words: context the
headline omits that changes how the claim reads); still_unknown (up to 3 items: what isn't
settled, and what evidence would settle it); coverage (broad / thin / disputed). State no
verdict on the claim anywhere."""

QUESTION_LENGTHS = """Cover, in prose: evidence_story (~150 words, telling what the evidence
shows plainly — no one-line verdict up front); evidence (up to 4 concrete facts, cases, dates
or numbers); interpretations (up to 4 attributed positions — which scholars, officials or
schools of thought — ~30 words each); still_open (~50 words); coverage (broad / thin /
disputed)."""

QUESTION_CRAFT = """TRAILS ARE QUESTIONS that turn a passive reader into a curious one.

Each trail has:
- "question": aims at the enduring puzzle BENEATH the news. It would still be worth asking a
  year from now and could be reached from many headlines. As long as it needs to be, in
  everyday words — no fixed word limit. Compressing a question into a soundbite tends to force
  a verdict into it, which is exactly what this must not do.
- "hook": ~15 words. A SPECIFIC fact from this story that makes the question urgent right now.
  It must add something the question doesn't say. Never restate the question.
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

Write 8 trails: at least 2 per dimension, at least 6 different moves. List each trail's
move, dimension, question, hook, and seed clearly."""

HEADLINE_PROMPT = """Headline an observer snipped: "{headline}"
Source outlet: {source_domain} (captured {date})
Research the news event this headline describes, as of {date}."""

QUESTION_PROMPT = """Answer this question as a stand-alone explainer: "{question}"
Research seed: {seed}
Context, ONLY to identify what is meant (don't write about this story):
Root headline: "{headline}" ({date}); trail so far: {path}"""

SHAPE_SYSTEM = """Convert the research notes below into the exact JSON schema requested.
This is a faithful format conversion only: do not add, remove, invent, or reinterpret any
fact, attribution, or trail — carry over wording closely. Do not run any research yourself;
everything you need is already in the notes. If a field isn't covered, use an empty string,
empty array, or the closest neutral coverage value already implied by the notes."""


# ---------- guards (§7.6) ----------
CITATION_MARKER = re.compile(r"\[\d+(?:\.\d+)*\]")


def strip_citations(obj):
    """Recursively strips citation markers like [1.2.2] from every string field."""
    if isinstance(obj, str):
        return CITATION_MARKER.sub("", obj)
    if isinstance(obj, list):
        return [strip_citations(v) for v in obj]
    if isinstance(obj, dict):
        return {k: strip_citations(v) for k, v in obj.items()}
    return obj


def find_loaded_words(result: dict, narrator_fields: list[str]) -> list[str]:
    """D25: checked only in narrator-voice fields, never inside an attributed `position`."""
    hits = []
    for field in narrator_fields:
        text = str(result.get(field, "")).lower()
        hits += [w for w in LOADED_WORDS if w in text]
    return hits


def check_shape(trails: list[dict]) -> dict:
    dims = Counter(t.get("dimension") for t in trails)
    moves = {t.get("move") for t in trails}
    return {
        "trail_count": len(trails),
        "per_dimension": dict(dims),
        "distinct_moves": len(moves),
        "meets_shape": len(trails) >= 6 and all(dims.get(d, 0) >= 2 for d in DIMENSIONS) and len(moves) >= 6,
    }


# ---------- calls ----------
def key() -> str:
    # A dedicated key for Exploring, isolated from Movies and from Hiring/Knowledge
    # Center/Jobs Manager — same shared core .env file, a different variable name.
    return os.environ["EXPLORING_GEMINI_API_KEY"]


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


def _research(client, system: str, prompt: str, thinking: str) -> dict:
    """Free-text, tools on, no schema. The only call that thinks/searches — its
    grounding_metadata is the real source of truth for citations (§7.1 sources_top5)."""
    cfg = types.GenerateContentConfig(
        system_instruction=system, temperature=0.4,
        tools=[types.Tool(google_search=types.GoogleSearch())],
        thinking_config=types.ThinkingConfig(thinking_level=thinking),
    )
    t0 = time.time()
    resp = client.models.generate_content(model=MODEL, contents=prompt, config=cfg)
    has_candidate = bool(resp.candidates)
    gm = resp.candidates[0].grounding_metadata if has_candidate else None
    chunks = list(gm.grounding_chunks or []) if gm else []
    cites = Counter(i for s in ((gm.grounding_supports or []) if gm else []) for i in (s.grounding_chunk_indices or []))
    return {
        "usage": usage(resp), "seconds": round(time.time() - t0, 1),
        "finish_reason": str(resp.candidates[0].finish_reason) if has_candidate else "NO_CANDIDATES",
        "text": resp.text if has_candidate else "",
        "search_queries": list(gm.web_search_queries or []) if gm else [],
        "sources_cited": len(cites),
        "sources_top5": [{"domain": chunks[i].web.title, "url": resolve_redirect(chunks[i].web.uri), "cited": n}
                         for i, n in cites.most_common(5) if i < len(chunks) and chunks[i].web],
    }


def _shape(client, research_text: str, resp_schema: dict) -> dict:
    """Schema on, tools OFF. Cheap: no search deliberation, just reformatting text it
    already has. Never contributes its own citations — those come from _research."""
    cfg = types.GenerateContentConfig(
        system_instruction=SHAPE_SYSTEM, temperature=0.1,
        response_mime_type="application/json", response_schema=resp_schema,
        thinking_config=types.ThinkingConfig(thinking_level="low"),
    )
    t0 = time.time()
    resp = client.models.generate_content(model=MODEL, contents=research_text, config=cfg)
    out = {"usage": usage(resp), "seconds": round(time.time() - t0, 1),
           "finish_reason": str(resp.candidates[0].finish_reason)}
    try:
        out["result"] = strip_citations(json.loads(resp.text))
    except Exception as e:
        out["result"], out["parse_error"], out["raw_text"] = None, f"{type(e).__name__}: {e}", resp.text
    return out


def call(client, system: str, prompt: str, resp_schema: dict, thinking: str) -> dict:
    """Two calls, not one: RESEARCH (free text, real grounding) -> SHAPE (schema, no tools).
    §7.6's "at most 2 attempts" budget now applies separately to each half — a research
    retry only fires if grounding is truly absent, a shape retry only fires on bad JSON."""
    r_attempts = []
    for _ in range(2):
        r = _research(client, system, prompt, thinking)
        r_attempts.append(r)
        if bool(r["search_queries"]) and r["sources_cited"] > 0:
            break
    research = r_attempts[-1]
    research_usage = {k: sum(a["usage"][k] for a in r_attempts) for k in research["usage"]}

    s_attempts = []
    for _ in range(2):
        s = _shape(client, research["text"], resp_schema)
        s_attempts.append(s)
        if s["result"] is not None:
            break
    shaped = s_attempts[-1]
    shape_usage = {k: sum(a["usage"][k] for a in s_attempts) for k in shaped["usage"]}

    total_usage = {k: research_usage[k] + shape_usage[k] for k in research_usage}
    grounded = bool(research["search_queries"]) and research["sources_cited"] > 0
    return {
        "usage": total_usage,
        "seconds": round(research["seconds"] + shaped["seconds"], 1),
        "finish_reason": shaped["finish_reason"],
        "result": shaped["result"],
        "parse_error": shaped.get("parse_error"),
        "search_queries": research["search_queries"],
        "sources_cited": research["sources_cited"],
        "sources_top5": research["sources_top5"],
        "attempts": {"research": len(r_attempts), "shape": len(s_attempts)},
        "unverified": not grounded,
    }


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


# ---------- running token counter (printed live so cost is visible while tuning) ----------
_running_total = {"prompt": 0, "tool_use_prompt": 0, "output": 0, "thinking": 0, "total": 0}


def _add_to_running_total(usage_dict: dict):
    for k in _running_total:
        _running_total[k] += usage_dict.get(k, 0)


def _print_running_total():
    print(f"  running total tokens: {_running_total['total']} "
          f"(prompt {_running_total['prompt']}, output {_running_total['output']}, "
          f"thinking {_running_total['thinking']}, tool_use {_running_total['tool_use_prompt']})")


def run_one(client, item: dict) -> dict:
    headline, source_domain, date = item["headline"], item["source_domain"], item["date"]
    print(f"[{item['label']}] headline dig: {headline!r}")

    hdig = call(client, rules(date) + "\n" + HEADLINE_LENGTHS + "\n\n" + QUESTION_CRAFT,
                HEADLINE_PROMPT.format(headline=headline, source_domain=source_domain, date=date),
                schema(HEADLINE_FIELDS), "low")
    _add_to_running_total(hdig["usage"])
    _print_running_total()
    res = hdig["result"] or {}
    cands = res.get("trails", [])
    shape_check = check_shape(cands)
    loaded = find_loaded_words(res, ["claim", "what_happened", "why_now", "left_out"])

    out = {
        "label": item["label"], "headline": headline, "date": date,
        "headline_dig": hdig, "candidate_shape": shape_check, "loaded_words": loaded,
    }
    if hdig["unverified"] or not cands:
        out["status"] = "unverified"
        return out

    shown, _ = pick(client, f"{headline}. {res.get('what_happened', '')} {res.get('why_now', '')}", cands, [])
    out["shown"] = [{k: c[k] for k in ("rank", "move", "dimension", "question", "hook", "picked_by")} for c in shown]

    first = shown[0]
    print(f"[{item['label']}] trail 1 dig: {first['question']!r}")
    qdig = call(client, rules(date) + "\n" + QUESTION_LENGTHS + "\n\n" + QUESTION_CRAFT
                + f'\nThe question just answered was: "{first["question"]}". Hooks tie new questions to that answer, not the headline.',
                QUESTION_PROMPT.format(question=first["question"], seed=first["seed"],
                                        headline=headline, date=date, path=first["question"]),
                schema(QUESTION_FIELDS), "low")
    _add_to_running_total(qdig["usage"])
    _print_running_total()
    qres = qdig["result"] or {}
    qcands = qres.get("trails", [])
    out["trail1_dig"] = qdig
    out["trail1_candidate_shape"] = check_shape(qcands)
    out["trail1_loaded_words"] = find_loaded_words(qres, ["evidence_story", "still_open"])

    if not qdig["unverified"] and qcands:
        shown2, dropped = pick(client, f"{first['question']} {qres.get('evidence_story', '')}", qcands, shown)
        out["trail1_dropped_loops"] = dropped
        out["trail1_shown"] = [{k: c[k] for k in ("rank", "move", "dimension", "question", "hook", "picked_by")} for c in shown2]

    tot = lambda recs: {k: sum(r["usage"][k] for r in recs) for k in ("prompt", "tool_use_prompt", "output", "thinking", "total")}  # noqa: E731
    out["token_totals"] = {"headline": tot([hdig]), "trail1": tot([qdig])}
    return out


def main():
    client = genai.Client(api_key=key())
    results = {"model": MODEL, "loop_threshold": LOOP_THRESHOLD, "runs": []}
    for item in HEADLINES:
        results["runs"].append(run_one(client, item))
    results["grand_total_tokens"] = dict(_running_total)
    (HERE / "results.json").write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
    print("done -> results.json")
    print(f"GRAND TOTAL TOKENS THIS RUN: {_running_total['total']}")


if __name__ == "__main__":
    main()
