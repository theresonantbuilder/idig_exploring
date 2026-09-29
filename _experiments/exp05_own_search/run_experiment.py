"""
Experiment 05: does bringing our own search + a swappable, cheap/fast model produce
comparable craft quality to the validated Gemini two-call pipeline (exp04_claims,
dev_server/pipeline.py) — at meaningfully lower cost AND lower latency?

Architecture under test (2026-09-29 discussion): search.py calls Tavily directly instead of
relying on any model vendor's built-in grounding tool (avoids Google-search-licensing
lock-in; not every model has an equivalent tool anyway). Because WE control the search step,
citations are deterministic (we already know each source's real URL) and there's no need for
Gemini's RESEARCH-then-SHAPE split, which existed only to work around search+schema not
reliably coexisting in one Gemini call. So this is ONE call per dig, not two.

Deliberately out of scope for this first pass (isolating the question "is the core
search+write mechanism good, fast, cheap"): the 8-candidate/pick() trail-diversity system —
this asks each model for exactly 4 trails directly. Port pick() back in once the core
mechanism is validated.

This is a fully separate, standalone experiment. It does NOT touch dev_server/ or
exp04_claims/ — the working Gemini pipeline is untouched by anything here.

Run: python run_experiment.py
(Needs TAVILY_API_KEY and DEEPSEEK_API_KEY in this folder's own .env — separate from
iDIGcore_w_domains/.env, since these are new, unproven providers unrelated to any shipping
product line.)

Provider choice (2026-09-29): Groq is infrastructure, not a model — it just runs other
companies' open-weight models (Llama, Mixtral, Gemma, a DeepSeek-distilled variant) on
custom fast chips. The model it would actually run here, Llama 3.3 70B, isn't in the same
quality class as DeepSeek's own flagship model — Groq's only edge is raw speed. Starting
with DeepSeek alone: stronger model, one fewer account to set up. providers.py already
supports Groq as an interchangeable entry if the speed question is worth revisiting later —
add "groq" back to PROVIDERS_TO_TEST below, no other change needed.
"""
import json
import re
import time
from pathlib import Path

from dotenv import load_dotenv

import providers
import search

HERE = Path(__file__).resolve().parent
load_dotenv(HERE / ".env")

# Same 4 headlines as exp04_claims, on purpose — direct comparison against the validated
# Gemini pipeline's output for the same stories, not a fresh, un-comparable sample.
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

PROVIDERS_TO_TEST = ["deepseek"]  # add "groq" back to also test it (see module docstring)

PATTERNS = (
    "Function Creep, Teaching to the Test, Moral Hazard, Survivorship Bias, Selection Bias, "
    "Network Effect, Tragedy of the Commons, Externality, Principal-Agent Problem, "
    "Regulatory Capture, Path Dependency, Threshold Effect, Feedback Loop, Diminishing "
    "Returns, Winner-Take-All Dynamics, Information Asymmetry, Signal vs. Noise, "
    "Compounding, Bottleneck, Redundancy vs. Fragility, Lock-In, Free-Rider Problem, "
    "Diffusion of Responsibility, Margin of Error, Emergent Complexity"
)

# Deliberately condensed vs. pipeline.py's QUESTION_CRAFT (full per-pattern definitions, long
# calibration examples) — partly to keep this cheap/fast pipeline's own prompt lean, and partly
# to test whether a shorter prompt still produces good pattern-tagging on a different model.
SYSTEM_RULES = f"""You are the research engine for iDIG Exploring. Base your answer ONLY on
the numbered sources below — never use outside knowledge, never claim something they don't
support. Say plainly when they're thin or disputed on something.

- The narrator states evidence only. Every judgment is attributed to who holds it (held_by).
  No loaded adjectives in the narrator's voice (theatrical, grandstanding, slammed, etc).
- EVERY factual claim in "established" and every trail's "hook" must name which numbered
  source it came from — this is how a reader (or code) can check the claim against the real
  source afterward, instead of just trusting the instruction that you stuck to the sources.
  Use the source's actual number from the list below. If a claim genuinely combines two
  sources, cite the one that states it most directly.
- Respond with ONLY a single JSON object, no markdown fences, no commentary, matching:

{{
  "claim": "1 sentence, neutral restatement of the headline",
  "what_happened": "1-2 sentences",
  "why_now": "~60 words",
  "established": [{{"text": "a fact the sources agree on", "source": 1}}],
  "contested": [{{"held_by": "who", "position": "~30 words"}}],
  "left_out": "~60 words: context the headline omits that changes how the claim reads",
  "still_unknown": ["up to 3 items"],
  "coverage": "broad | thin | disputed",
  "trails": [
    {{
      "move": "tension | mechanism | precedent | frame | stakes | hidden | scale | unknowns",
      "dimension": "semantic | experiential | social",
      "pattern": "closest fit from the list below",
      "angle": "4-8 words capturing what makes THIS question worth asking, not the category name",
      "question": "the enduring puzzle beneath the news, everyday words, no fixed length",
      "hook": {{"text": "~15 words, a specific fact making the question urgent now", "source": 2}}
    }}
  ]
}}

"established" holds up to 4 facts; each is its own {{text, source}} object, not a plain
string. Exactly 4 trails, each a different move, at least 2 different dimensions. Never
state a verdict on the claim anywhere.

Patterns (name the mechanism, not the drama — pick the closest fit per trail): {PATTERNS}."""

PROMPT_TEMPLATE = """Headline: "{headline}"
Source outlet: {source_domain} (captured {date})

Sources:
{sources_block}"""

FENCE = re.compile(r"^```(?:json)?\s*|\s*```$", re.MULTILINE)


def build_sources_block(sources: list) -> str:
    parts = []
    for i, s in enumerate(sources, 1):
        content = s["content"][:600]
        parts.append(f'[{i}] {s["title"]} — {s["url"]}\n{content}')
    return "\n\n".join(parts)


def check_citations(result: dict, num_sources: int) -> list:
    """Doesn't verify the claim is actually TRUE to the cited source's content (that would
    need a separate semantic check, e.g. embedding similarity between claim and source
    excerpt — worth adding later) — only that every claim that's supposed to carry a
    citation has one, and it points at a source that actually exists. Closes the "trust the
    instruction" gap named in the 2026-09-29 discussion: this makes missing/bad citations
    visible in the output instead of silently assumed."""
    problems = []
    for i, fact in enumerate(result.get("established", [])):
        if not isinstance(fact, dict) or "source" not in fact:
            problems.append(f"established[{i}] has no source citation")
        elif not (1 <= fact["source"] <= num_sources):
            problems.append(f"established[{i}] cites source {fact['source']}, but only {num_sources} sources exist")
    for i, trail in enumerate(result.get("trails", [])):
        hook = trail.get("hook")
        if not isinstance(hook, dict) or "source" not in hook:
            problems.append(f"trails[{i}].hook has no source citation")
        elif not (1 <= hook["source"] <= num_sources):
            problems.append(f"trails[{i}].hook cites source {hook['source']}, but only {num_sources} sources exist")
    return problems


def run_one(provider: str, item: dict, sources: list) -> dict:
    prompt = PROMPT_TEMPLATE.format(
        headline=item["headline"], source_domain=item["source_domain"], date=item["date"],
        sources_block=build_sources_block(sources),
    )
    attempts = []
    for _ in range(2):
        r = providers.generate(provider, SYSTEM_RULES, prompt)
        attempts.append(r)
        try:
            r["result"] = json.loads(FENCE.sub("", r["text"]).strip())
            break
        except Exception as e:
            r["result"], r["parse_error"] = None, f"{type(e).__name__}: {e}"
    final = attempts[-1]
    total_usage = {k: sum(a["usage"][k] for a in attempts) for k in attempts[0]["usage"]}
    total_seconds = round(sum(a["seconds"] for a in attempts), 1)
    citation_issues = check_citations(final["result"], len(sources)) if final["result"] else []
    return {
        "provider": provider, "model": final["model"], "attempts": len(attempts),
        "usage": total_usage, "seconds": total_seconds,
        "result": final["result"], "parse_error": final.get("parse_error"),
        "citation_issues": citation_issues,
        "sources": [{"title": s["title"], "url": s["url"]} for s in sources],
    }


def main():
    results = {"runs": []}
    grand_total = {"tokens": 0, "seconds": 0.0}
    for item in HEADLINES:
        print(f"[{item['label']}] searching: {item['headline']!r}")
        t0 = time.time()
        sources = search.search(f"{item['headline']} {item['source_domain']}")
        search_seconds = round(time.time() - t0, 1)
        print(f"  tavily: {len(sources)} results in {search_seconds}s")

        for provider in PROVIDERS_TO_TEST:
            print(f"  [{provider}] generating...")
            out = run_one(provider, item, sources)
            out["label"], out["headline"], out["search_seconds"] = item["label"], item["headline"], search_seconds
            results["runs"].append(out)
            grand_total["tokens"] += out["usage"]["total"]
            grand_total["seconds"] += out["seconds"] + search_seconds
            ok = "OK" if out["result"] else f"PARSE FAILED: {out['parse_error']}"
            print(f"  [{provider}] {ok} — {out['usage']['total']} tokens, "
                  f"{out['seconds']}s generate + {search_seconds}s search, {out['attempts']} attempt(s)")
            if out["citation_issues"]:
                print(f"  [{provider}] CITATION ISSUES: {out['citation_issues']}")
            print(f"  running total: {grand_total['tokens']} tokens, {round(grand_total['seconds'], 1)}s")

    results["grand_total"] = grand_total
    (HERE / "results.json").write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\ndone -> results.json  ({grand_total['tokens']} tokens, {round(grand_total['seconds'], 1)}s total)")


if __name__ == "__main__":
    main()
