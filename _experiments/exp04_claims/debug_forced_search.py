"""
Isolates the schema variable from the 'does the model feel it needs to search' variable,
by reusing the ORIGINAL debug_grounding.py prompt (today's BBC front page — structurally
impossible to answer without a live search) and testing it WITH response_schema/mime type
added. If this still grounds, schema was never the problem — the real issue is the model's
own judgment call on whether a topic needs searching, which prompt-engineering (headline
digs sound answerable) can't fully control.

Run: python debug_forced_search.py
"""
import os
from pathlib import Path

from dotenv import load_dotenv
from google import genai
from google.genai import types

HERE = Path(__file__).resolve().parent
CORE = HERE.parents[2] / "iDIGcore_w_domains"
load_dotenv(CORE / ".env")

MODEL = os.environ.get("EXPLORING_MODEL", "gemini-3.8-flash")
PROMPT = "What is today's top headline on the BBC News homepage right now? Search for it."
SCHEMA = {
    "type": "object",
    "properties": {"headline": {"type": "string"}, "summary": {"type": "string"}},
    "required": ["headline", "summary"],
}

client = genai.Client(api_key=os.environ["EXPLORING_GEMINI_API_KEY"])

cfg = types.GenerateContentConfig(
    system_instruction="Always run Google Search before answering. Only search results count.",
    temperature=0.4,
    response_mime_type="application/json", response_schema=SCHEMA,
    tools=[types.Tool(google_search=types.GoogleSearch())],
    thinking_config=types.ThinkingConfig(thinking_level="low"),
)
resp = client.models.generate_content(model=MODEL, contents=PROMPT, config=cfg)

if not resp.candidates:
    print(f"NO CANDIDATES. prompt_feedback: {resp.prompt_feedback}")
else:
    gm = resp.candidates[0].grounding_metadata
    grounded = bool(gm and gm.web_search_queries)
    print(f"finish_reason: {resp.candidates[0].finish_reason}")
    print(f"grounded: {grounded}")
    if grounded:
        print(f"queries: {list(gm.web_search_queries)}")
    print(f"text: {resp.text}")
