"""
Isolates whether response_schema (forced JSON) is what's silently killing grounding in
run_experiment.py, by running the same real, post-cutoff headline three ways:
  A) tools + response_schema + response_mime_type=json  (what run_experiment.py does)
  B) tools + response_mime_type=json, NO response_schema
  C) tools only, plain text, JSON requested via prompt instead of API param

Run: python debug_schema_grounding.py
"""
import json
import os
from pathlib import Path

from dotenv import load_dotenv
from google import genai
from google.genai import types

HERE = Path(__file__).resolve().parent
CORE = HERE.parents[2] / "iDIGcore_w_domains"
load_dotenv(CORE / ".env")

MODEL = os.environ.get("EXPLORING_MODEL", "gemini-3.8-flash")
HEADLINE = "Government can use Social Security data to identify noncitizen voters, Supreme Court rules"

SCHEMA = {
    "type": "object",
    "properties": {"claim": {"type": "string"}, "what_happened": {"type": "string"}},
    "required": ["claim", "what_happened"],
}

SYSTEM = ("You are a research engine. ALWAYS run Google Search before writing, even if you "
          "think you know the answer. Your memory is out of date; only search results count.")
PROMPT = f'Headline: "{HEADLINE}". Research the news event this describes, as of 2026-09-25.'

client = genai.Client(api_key=os.environ["EXPLORING_GEMINI_API_KEY"])


def report(label, resp):
    print(f"\n=== {label} ===")
    if not resp.candidates:
        print(f"NO CANDIDATES. prompt_feedback: {resp.prompt_feedback}")
        return
    gm = resp.candidates[0].grounding_metadata
    grounded = bool(gm and gm.web_search_queries)
    print(f"finish_reason: {resp.candidates[0].finish_reason}")
    print(f"grounded: {grounded}")
    if grounded:
        print(f"queries: {list(gm.web_search_queries)}")
    try:
        print(f"text head: {resp.text[:200]!r}")
    except Exception as e:
        print(f"text access failed: {e}")


# A) schema + mime type (current run_experiment.py behavior)
cfg_a = types.GenerateContentConfig(
    system_instruction=SYSTEM, temperature=0.4,
    response_mime_type="application/json", response_schema=SCHEMA,
    tools=[types.Tool(google_search=types.GoogleSearch())],
    thinking_config=types.ThinkingConfig(thinking_level="low"),
)
report("A: schema + mime + tools", client.models.generate_content(model=MODEL, contents=PROMPT, config=cfg_a))

# B) mime type only, no schema
cfg_b = types.GenerateContentConfig(
    system_instruction=SYSTEM, temperature=0.4,
    response_mime_type="application/json",
    tools=[types.Tool(google_search=types.GoogleSearch())],
    thinking_config=types.ThinkingConfig(thinking_level="low"),
)
report("B: mime only + tools", client.models.generate_content(model=MODEL, contents=PROMPT, config=cfg_b))

# C) plain text, ask for JSON in prompt
cfg_c = types.GenerateContentConfig(
    system_instruction=SYSTEM, temperature=0.4,
    tools=[types.Tool(google_search=types.GoogleSearch())],
    thinking_config=types.ThinkingConfig(thinking_level="low"),
)
prompt_c = PROMPT + f" Respond with ONLY a JSON object matching this schema: {json.dumps(SCHEMA)}"
report("C: plain text + tools, JSON via prompt", client.models.generate_content(model=MODEL, contents=prompt_c, config=cfg_c))
