"""
The real iDIG Exploring dig pipeline, for one headline at a time — the same validated
two-call design as _experiments/exp04_claims/run_experiment.py (RESEARCH: free text, tools
on, real grounding_metadata; SHAPE: schema on, tools off, cheap reformat). Deliberately a
separate copy for now rather than a shared import, so the validated experiment script stays
untouched while this becomes the live server-side pipeline; consolidate later.

This is the MINIMAL LOCAL LOOP version (SPEC.md's full contract, sprint E1-E3, isn't built
yet): no Supabase, no queue/worker process, no demo-gate rate limiting, no embedding-based
dedup against other snips of the same headline. One in-memory dict, one background thread
per snip. Good enough to prove the extension -> real Gemini -> real page loop end to end.
"""
import json
import os
import re
import time
import urllib.error
import urllib.request
from collections import Counter
from pathlib import Path

from dotenv import load_dotenv
from google import genai
from google.genai import types

HERE = Path(__file__).resolve().parent
CORE = HERE.parent.parent / "iDIGcore_w_domains"
load_dotenv(CORE / ".env")

MODEL = os.environ.get("EXPLORING_MODEL", "gemini-3.8-flash")
EMBED_MODEL = "gemini-embedding-001"
EMBED_DIMS = 768
MMR_LAMBDA = 0.7
LOOP_THRESHOLD = 0.85
DIMENSIONS = ("semantic", "experiential", "social")
MOVES = ["tension", "mechanism", "precedent", "frame", "stakes", "hidden", "scale", "unknowns"]

# Closed vocabulary of recurring structural/causal patterns (D35) — deliberately NOT
# narrative archetypes ("Maverick vs. The System"): those describe the shape of the drama,
# these describe the shape of the mechanism underneath it, which is what actually lets two
# unrelated stories connect (SPEC §7.3a). Built ahead of D34 (trails as connectors) so a
# future cross-dig match is a shared, explainable tag, not a fragile embedding coincidence.
PATTERNS = [
    "Function Creep", "Teaching to the Test", "Moral Hazard", "Survivorship Bias",
    "Selection Bias", "Network Effect", "Tragedy of the Commons", "Externality",
    "Principal-Agent Problem", "Regulatory Capture", "Path Dependency", "Threshold Effect",
    "Feedback Loop", "Diminishing Returns", "Winner-Take-All Dynamics",
    "Information Asymmetry", "Signal vs. Noise", "Compounding", "Bottleneck",
    "Redundancy vs. Fragility", "Lock-In", "Free-Rider Problem",
    "Diffusion of Responsibility", "Margin of Error", "Emergent Complexity",
]

LOADED_WORDS = [
    "theatrical", "grandstanding", "posturing", "slammed", "blasted", "so-called",
    "shocking", "stunning", "blistering", "scathing", "explosive",
]

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
        "pattern": {"type": "string", "enum": PATTERNS},
        "angle": {"type": "string"},
        "question": {"type": "string"}, "hook": {"type": "string"}, "seed": {"type": "string"},
    },
    "required": ["move", "dimension", "pattern", "angle", "question", "hook", "seed"],
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
- "pattern": the ONE structural/causal pattern from this fixed list that best fits this
  trail's question — pick the closest match, even if imperfect. This is NOT a narrative label
  ("Maverick vs. The System") — it names the underlying mechanism, independent of who the
  players are, so a completely unrelated story with the same mechanism could share the tag:
  Function Creep (a system's scope quietly expands past its original purpose) · Teaching to
  the Test (optimizing for the measure instead of the goal it represents) · Moral Hazard
  (being shielded from consequences changes the behavior it was meant to guard against) ·
  Survivorship Bias (only the outcomes that made it through get counted) · Selection Bias
  (the sample isn't representative of what it claims to describe) · Network Effect (value
  compounds simply because more people/nodes join) · Tragedy of the Commons (a shared
  resource degrades because no one owns the cost of using it) · Externality (the cost or
  benefit lands on someone who wasn't part of the decision) · Principal-Agent Problem (the
  person acting doesn't bear the consequences the person affected does) · Regulatory Capture
  (the overseer starts serving the overseen) · Path Dependency (an early, possibly arbitrary
  choice locks in everything downstream) · Threshold Effect (nothing changes until a line is
  crossed, then everything does) · Feedback Loop (an effect loops back and amplifies or
  dampens its own cause) · Diminishing Returns (the same input produces less benefit over
  time) · Winner-Take-All Dynamics (small early advantages compound into total dominance) ·
  Information Asymmetry (one side knows something the other doesn't, and that gap drives the
  outcome) · Signal vs. Noise (what looks meaningful is statistical variation, or vice versa)
  · Compounding (small, steady effects accumulate into something large) · Bottleneck (the
  whole system's speed is set by its single slowest part) · Redundancy vs. Fragility (a
  system's backup capacity, or lack of it, determines what survives) · Lock-In (switching
  costs trap people/systems in a choice long after it stops being the best one) · Free-Rider
  Problem (some benefit from a shared effort without contributing to it) · Diffusion of
  Responsibility (when everyone is accountable, no one is) · Margin of Error (the gap between
  a measurement and the truth becomes the whole story) · Emergent Complexity (simple rules,
  followed at scale, produce behavior nobody designed).
- "angle": a short phrase (4-8 words) that captures what makes THIS SPECIFIC question worth
  asking — never the category name ("mechanism", "tension"). This is what the reader sees
  first, before the question itself, so it has to earn the click on its own. Write it like a
  compelling pull-quote fragment, not a restatement of the question or the hook.
  Weak (just the category): "Mechanism" / "Hidden Actors"
  Strong (the specific angle): "How a database mismatch actually happens" / "Who makes the
  final call"
- "question": aims at the enduring puzzle BENEATH the news. It would still be worth asking a
  year from now and could be reached from many headlines. As long as it needs to be, in
  everyday words — no fixed word limit. Compressing a question into a soundbite tends to force
  a verdict into it, which is exactly what this must not do.
- "hook": ~15 words. A SPECIFIC fact from this story that makes the question urgent right now.
  It must add something the question doesn't say. Never restate the question or the angle.
- "seed": a neutral search query for researching the question on its own.

A great question opens a gap the reader didn't know existed:
- It contains a twist: "why would...", "how can... when...", "even though", "yet", "despite".
- It names something concrete: a mechanism, an institution, a place, a pattern.
- It's answerable with evidence (history, data, how a system works). No opinion, no "should".
- A bored person reading it thinks "huh... I don't actually know that."

Reject these question shapes outright:
- Textbook abstractions: "How do nations balance sovereignty with cooperation?"
- Impact templates: "What are the impacts/effects/implications of X on Y?"
- Anything the dig already answers, anything yes/no, anything with "you"/"your".

Moves (one per trail): tension (the contradiction inside the story), mechanism (how the
underlying thing works), precedent (when it happened before and how it ended), frame (how
sides tell it differently), stakes (what changes on the ground), hidden (who isn't in the
headline but matters), scale (how big, against something familiar), unknowns (what isn't
settled and what evidence would settle it).
Dimensions: semantic (mechanism, precedent, scale), experiential (stakes, life under it),
social (tension, frame, hidden actors, incentives).

Write 8 trails: at least 2 per dimension, at least 6 different moves. List each trail's
move, dimension, pattern, angle, question, hook, and seed clearly."""

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

CITATION_MARKER = re.compile(r"\[\d+(?:\.\d+)*\]")


def strip_citations(obj):
    if isinstance(obj, str):
        return CITATION_MARKER.sub("", obj)
    if isinstance(obj, list):
        return [strip_citations(v) for v in obj]
    if isinstance(obj, dict):
        return {k: strip_citations(v) for k, v in obj.items()}
    return obj


def find_loaded_words(result: dict, narrator_fields: list) -> list:
    hits = []
    for field in narrator_fields:
        text = str(result.get(field, "")).lower()
        hits += [w for w in LOADED_WORDS if w in text]
    return hits


def check_shape(trails: list) -> dict:
    dims = Counter(t.get("dimension") for t in trails)
    moves = {t.get("move") for t in trails}
    return {
        "trail_count": len(trails),
        "per_dimension": dict(dims),
        "distinct_moves": len(moves),
        "meets_shape": len(trails) >= 6 and all(dims.get(d, 0) >= 2 for d in DIMENSIONS) and len(moves) >= 6,
    }


def api_key() -> str:
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
        "sources_top5": [{"title": chunks[i].web.title, "url": resolve_redirect(chunks[i].web.uri)}
                         for i, n in cites.most_common(5) if i < len(chunks) and chunks[i].web],
    }


def _shape(client, research_text: str, resp_schema: dict) -> dict:
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
        "result": shaped["result"],
        "sources_top5": research["sources_top5"],
        "unverified": not grounded,
    }


def embed(client, texts):
    r = client.models.embed_content(model=EMBED_MODEL, contents=texts, config=types.EmbedContentConfig(
        output_dimensionality=EMBED_DIMS, task_type="SEMANTIC_SIMILARITY"))
    return [list(e.values) for e in r.embeddings]


def _cosine(a, b) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = sum(x * x for x in a) ** 0.5
    nb = sum(y * y for y in b) ** 0.5
    return dot / (na * nb) if na and nb else 0.0


def pick(client, anchor: str, cands: list, path: list) -> tuple:
    vecs = embed(client, [anchor] + [f"{c['question']} {c['hook']}" for c in cands] + [p["question"] for p in path])
    a, cv, pv = vecs[0], vecs[1:1 + len(cands)], vecs[1 + len(cands):]
    pool, dropped = [], []
    for c, v in zip(cands, cv):
        c["relevance"], c["_v"] = round(_cosine(v, a), 4), v
        loop = max((_cosine(v, p) for p in pv), default=0.0)
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
        mmr = lambda c: MMR_LAMBDA * c["relevance"] - (1 - MMR_LAMBDA) * max(_cosine(c["_v"], p["_v"]) for p in picked)  # noqa: E731
        n = max(rest, key=mmr); n["picked_by"] = f"MMR {mmr(n):.3f}"; picked.append(n)
    for r, c in enumerate(picked, 1):
        c["rank"] = r
    for c in cands:
        c.pop("_v", None)
    return picked, dropped


DEEPER_TYPES = ["book", "course", "podcast", "video", "article", "exhibit"]
DEEPER_ITEM = {
    "type": "object",
    "properties": {
        "trail_index": {"type": "integer"},
        "type": {"type": "string", "enum": DEEPER_TYPES},
        "title": {"type": "string"},
        "source": {"type": "string"},
        "reason": {"type": "string"},
        "url": {"type": "string"},
    },
    "required": ["trail_index", "type", "title", "source", "reason", "url"],
}
DEEPER_SCHEMA = {
    "type": "object",
    "properties": {"resources": {"type": "array", "items": DEEPER_ITEM, "maxItems": 8}},
    "required": ["resources"],
}

DEEPER_RULES = """You are finding further-reading resources for iDIG Exploring's "iDIG Deeper"
feature. ALWAYS run Google Search before writing, even if you think you know the answer —
every resource you name must be something you actually found via search just now, with its
real URL from the search result. Never invent a title, source, or URL.
- For EACH trail listed below, find 1-2 resources that would genuinely help someone go
  deeper on THAT trail's specific question — not the headline in general.
- TYPE DISTRIBUTION IS A REQUIREMENT, NOT A PREFERENCE. A plain web search naturally surfaces
  news articles first, which is exactly the bias to fight: article is the LAST type to reach
  for, not the first. Before settling for an article on any trail, run an additional, more
  targeted search for that trail's topic — append "book", "documentary", "podcast episode",
  "explainer video", or "online course" to the query, rather than searching the bare topic
  again. Only fall back to an article if a real book/video/podcast/course genuinely doesn't
  exist after that targeted search.
- Across the FULL set of resources you return (all trails combined): use no single type more
  than twice, and cover at least 3 different types overall. If your first pass would produce
  4+ articles, that's a sign you didn't search specifically enough — go back and search again
  with a type-specific query before giving up on variety.
- Prefer variety in subject/source too: don't recommend the same resource for two trails.
- "reason" ties the resource to the specific trail's question in one sentence, not just its
  general topic.
- If you genuinely can't find a real resource of any type for a trail after searching, skip
  it — never substitute something only loosely related just to hit a type quota.
- Write your findings as prose first (title, type, where it's from, the real URL, and why it
  fits which trail) — a second pass converts this into JSON."""

DEEPER_PROMPT = """Headline: "{headline}"
Claim: {claim}

Find resources for these trails (indexed from 0):
{trails_block}"""


def run_deeper(client, headline: str, claim: str, shown_trails: list) -> tuple:
    """Real per-trail 'iDIG Deeper' resources: its own grounded two-call pass (call()), run
    after the main dig, over just the trails actually shown. Supplementary — if this comes
    back unverified or empty, the dig still renders fine with no Deeper section, so a
    failure here never blocks the main dig. Returns (by_trail, usage) — usage is returned
    even on failure, since the tokens were still spent on that attempt regardless of whether
    it produced usable resources."""
    trails_block = "\n".join(
        f'{i}. [{t["move"]}] {t["question"]} (hook: {t["hook"]})' for i, t in enumerate(shown_trails)
    )
    result = call(client, DEEPER_RULES,
                  DEEPER_PROMPT.format(headline=headline, claim=claim, trails_block=trails_block),
                  DEEPER_SCHEMA, "low")
    if result["unverified"] or not result["result"]:
        return {}, result["usage"]
    by_trail: dict = {}
    for item in result["result"].get("resources", []):
        idx = item.get("trail_index")
        if not isinstance(idx, int) or not (0 <= idx < len(shown_trails)):
            continue
        url = item.get("url", "")
        if not url.startswith(("http://", "https://")):
            continue
        by_trail.setdefault(idx, []).append({
            "type": item["type"], "title": item["title"], "source": item["source"],
            "reason": item["reason"], "url": url,
        })
    return by_trail, result["usage"]


def run_headline_dig(client, headline: str, source_domain: str, date: str) -> dict:
    """The one entry point the dev server calls. Returns a dict shaped for the extension's
    HeadlineDig type (mockDig.ts) plus a couple of internal fields (usage, unverified)."""
    hdig = call(client, rules(date) + "\n" + HEADLINE_LENGTHS + "\n\n" + QUESTION_CRAFT,
                HEADLINE_PROMPT.format(headline=headline, source_domain=source_domain, date=date),
                schema(HEADLINE_FIELDS), "low")
    res = hdig["result"] or {}
    cands = res.get("trails", [])

    if hdig["unverified"] or not cands:
        return {"unverified": True, "usage": hdig["usage"]}

    shown, _ = pick(client, f"{headline}. {res.get('what_happened', '')} {res.get('why_now', '')}", cands, [])
    shown_qs = {c["question"] for c in shown}
    for i, c in enumerate(shown, 1):
        c["rank"] = i
    more = [c for c in cands if c["question"] not in shown_qs]

    deeper_by_index, deeper_usage = run_deeper(client, headline, res.get("claim", ""), shown)
    total_usage = {k: hdig["usage"][k] + deeper_usage[k] for k in hdig["usage"]}

    trails = [
        {"move": c["move"], "dimension": c["dimension"], "pattern": c["pattern"], "angle": c["angle"],
         "question": c["question"], "hook": c["hook"], "rank": c["rank"], "deeper": deeper_by_index.get(i, [])}
        for i, c in enumerate(shown)
    ] + [
        {"move": c["move"], "dimension": c["dimension"], "pattern": c["pattern"], "angle": c["angle"],
         "question": c["question"], "hook": c["hook"], "rank": None}
        for c in more
    ]

    return {
        "unverified": False,
        "usage": total_usage,
        "claim": res.get("claim", ""),
        "what_happened": res.get("what_happened", ""),
        "why_now": res.get("why_now", ""),
        "established": res.get("established", []),
        "contested": res.get("contested", []),
        "left_out": res.get("left_out", ""),
        "still_unknown": res.get("still_unknown", []),
        "coverage": res.get("coverage", "broad"),
        "sources": hdig["sources_top5"],
        "trails": trails,
    }
