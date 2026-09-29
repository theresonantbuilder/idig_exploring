"""
A/B report: the validated Gemini two-call pipeline (exp04_claims/results.json) vs. the new
own-search + swappable-model architecture (this folder's results.json), same 4 headlines.

Scope note: this compares the HEADLINE DIG step only on both sides. exp04_claims also runs a
trail1 follow-up dig, and the real dev_server/pipeline.py additionally runs a whole separate
Deeper pass — neither of those exists in exp05 yet (see run_experiment.py's docstring), so
including them would compare unequal amounts of work. This is deliberately the narrower,
fair comparison: same input, same job (one headline -> one dig), different architecture.

Run: python compare.py
(exp04_claims/results.json already exists from validated runs. This folder's results.json
needs a real run of run_experiment.py first, which needs TAVILY_API_KEY and at least one of
GROQ_API_KEY/DEEPSEEK_API_KEY in this folder's .env.)
"""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
EXP04 = HERE.parent / "exp04_claims" / "results.json"
EXP05 = HERE / "results.json"


def load(path: Path) -> dict:
    if not path.exists():
        raise SystemExit(f"Missing {path} - run that experiment's script first.")
    return json.loads(path.read_text(encoding="utf-8"))


def gemini_rows(data: dict) -> dict:
    rows = {}
    for run in data["runs"]:
        hd = run["headline_dig"]
        res = hd.get("result") or {}
        rows[run["label"]] = {
            "provider": "gemini (2-call)",
            "tokens": hd["usage"]["total"],
            "seconds": hd["seconds"],
            "trails": len(res.get("trails", [])),
            "sources": hd.get("sources_cited", 0),
            "citation_issues": "n/a",  # Gemini's grounding_supports do this differently; not directly comparable
            "claim": (res.get("claim") or "")[:90],
        }
    return rows


def exp05_rows(data: dict) -> list:
    rows = []
    for run in data["runs"]:
        res = run.get("result") or {}
        rows.append({
            "label": run["label"],
            "provider": run["provider"],
            "tokens": run["usage"]["total"],
            "seconds": round(run["seconds"] + run.get("search_seconds", 0), 1),
            "trails": len(res.get("trails", [])),
            "sources": len(run.get("sources", [])),
            "citation_issues": len(run.get("citation_issues", [])),
            "claim": (res.get("claim") or "")[:90],
        })
    return rows


def main():
    gemini = gemini_rows(load(EXP04))
    exp05 = exp05_rows(load(EXP05))

    header = f"{'label':<24}{'provider':<18}{'tokens':>8}{'seconds':>9}{'trails':>8}{'sources':>9}{'issues':>8}"
    print(header)
    print("-" * len(header))
    for label, row in gemini.items():
        print(f"{label:<24}{row['provider']:<18}{row['tokens']:>8}{row['seconds']:>9}"
              f"{row['trails']:>8}{row['sources']:>9}{row['citation_issues']:>8}")
        print(f"    claim: {row['claim']}")
    for row in exp05:
        print(f"{row['label']:<24}{row['provider']:<18}{row['tokens']:>8}{row['seconds']:>9}"
              f"{row['trails']:>8}{row['sources']:>9}{row['citation_issues']:>8}")
        print(f"    claim: {row['claim']}")

    g_tokens = sum(r["tokens"] for r in gemini.values())
    g_seconds = sum(r["seconds"] for r in gemini.values())
    print(f"\nGemini totals (headline dig only, {len(gemini)} headlines): {g_tokens} tokens, {round(g_seconds, 1)}s")
    for provider in sorted({r["provider"] for r in exp05}):
        p_rows = [r for r in exp05 if r["provider"] == provider]
        p_tokens = sum(r["tokens"] for r in p_rows)
        p_seconds = sum(r["seconds"] for r in p_rows)
        p_issues = sum(r["citation_issues"] for r in p_rows)
        tok_pct = round(100 * p_tokens / g_tokens) if g_tokens else 0
        sec_pct = round(100 * p_seconds / g_seconds) if g_seconds else 0
        print(f"{provider} totals ({len(p_rows)} headlines): {p_tokens} tokens ({tok_pct}% of Gemini's), "
              f"{round(p_seconds, 1)}s ({sec_pct}% of Gemini's), {p_issues} citation issue(s) across all runs")


if __name__ == "__main__":
    main()
