"""
Tavily search adapter — the "own search" half of the swappable architecture (see SPEC.md
discussion, 2026-09-29): don't depend on any one model vendor's built-in grounding tool
(Google's licensing could change; other vendors don't have an equivalent at all), and get
real URLs back directly from a search call we control, rather than from a model's internal
tool-calling metadata (which we already found gets unreliable under some conditions with
Gemini's response_schema mode — see dev_server/pipeline.py's history).

This file is the ONLY thing that would need to change to swap search providers (Bing, Brave
Search, Google Custom Search JSON API are all viable alternates with the same shape).
"""
import json
import os
import urllib.request

TAVILY_URL = "https://api.tavily.com/search"


def search(query: str, max_results: int = 6) -> list[dict]:
    """Returns [{title, url, content}], content being Tavily's extracted excerpt (not the
    full page — that's Tavily's job, not ours; raw_content is available at extra cost/latency
    if excerpts turn out too thin during evaluation). Raises on missing key or HTTP failure —
    no silent fallback to ungrounded generation."""
    api_key = os.environ.get("TAVILY_API_KEY", "")
    if not api_key:
        raise RuntimeError("TAVILY_API_KEY not set")
    body = json.dumps({
        "api_key": api_key,
        "query": query,
        "search_depth": "advanced",
        "max_results": max_results,
        "include_answer": False,
    }).encode("utf-8")
    req = urllib.request.Request(
        TAVILY_URL, data=body, headers={"Content-Type": "application/json"}, method="POST"
    )
    with urllib.request.urlopen(req, timeout=20) as resp:
        data = json.loads(resp.read())
    return [
        {"title": r.get("title", ""), "url": r["url"], "content": r.get("content", "")}
        for r in data.get("results", [])
        if r.get("url")
    ]
