"""
The "swappable model" half of the architecture. Groq and DeepSeek both expose an
OpenAI-compatible /chat/completions endpoint, so one adapter covers both — and covers any
future provider (Mistral, OpenAI itself, a self-hosted Qwen behind an OpenAI-compatible
proxy, etc.) that speaks the same shape. Adding a provider is adding one entry to PROVIDERS,
not writing a new client.

Neither Groq nor DeepSeek offers Gemini-style strict response_schema enforcement — only
"give me back valid JSON" (response_format: json_object). The schema itself is described in
the prompt instead, and run_experiment.py retries once on a parse failure, same guard
philosophy as dev_server/pipeline.py's SHAPE step, just enforced by us instead of the API.
"""
import json
import os
import time
import urllib.error
import urllib.request

PROVIDERS = {
    "groq": {
        "url": "https://api.groq.com/openai/v1/chat/completions",
        "key_env": "GROQ_API_KEY",
        "model_env": "GROQ_MODEL",
        "default_model": "llama-3.3-70b-versatile",
    },
    "deepseek": {
        "url": "https://api.deepseek.com/chat/completions",
        "key_env": "DEEPSEEK_API_KEY",
        "model_env": "DEEPSEEK_MODEL",
        # Current naming per platform.deepseek.com/pricing (2026-09): "deepseek-chat" is the
        # legacy V3-era name. deepseek-flash (V4.1) is today's cheap/fast tier; deepseek-v4-pro
        # is the stronger, pricier tier.
        "default_model": "deepseek-flash",
        # DeepSeek's docs show a "thinking"/"reasoning_effort" mode (their example uses
        # enabled + high). Explicitly disabled here: this task is extraction and writing from
        # provided sources, not multi-step reasoning, and we're specifically optimizing for
        # speed/cost — same call Gemini's pipeline made with thinking_level="low". Leaving it
        # unset would mean not knowing whether we're silently paying for and waiting on
        # reasoning tokens we don't need.
        "extra_body": {"thinking": {"type": "disabled"}},
    },
}


def generate(provider: str, system: str, prompt: str) -> dict:
    """Returns {"text", "usage": {"prompt", "output", "total"}, "seconds", "model"}."""
    cfg = PROVIDERS[provider]
    api_key = os.environ.get(cfg["key_env"], "")
    if not api_key:
        raise RuntimeError(f"{cfg['key_env']} not set")
    model = os.environ.get(cfg["model_env"], cfg["default_model"])
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.4,
        "response_format": {"type": "json_object"},
    }
    payload.update(cfg.get("extra_body", {}))
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(cfg["url"], data=body, headers={
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }, method="POST")
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read())
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"{provider} HTTP {e.code}: {e.read().decode(errors='replace')}") from e
    seconds = round(time.time() - t0, 1)
    usage = data.get("usage", {})
    return {
        "text": data["choices"][0]["message"]["content"],
        "usage": {
            "prompt": usage.get("prompt_tokens", 0),
            "output": usage.get("completion_tokens", 0),
            "total": usage.get("total_tokens", 0),
        },
        "seconds": seconds,
        "model": model,
    }
