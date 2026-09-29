"""Same guaranteed-search prompt, but JSON requested via prompt text, no response_schema/mime."""
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
SCHEMA = {"type": "object", "properties": {"headline": {"type": "string"}, "summary": {"type": "string"}},
          "required": ["headline", "summary"]}
PROMPT = ("What is today's top headline on the BBC News homepage right now? Search for it. "
          f"Respond with ONLY a JSON object matching this schema: {json.dumps(SCHEMA)}")

client = genai.Client(api_key=os.environ["EXPLORING_GEMINI_API_KEY"])
cfg = types.GenerateContentConfig(
    system_instruction="Always run Google Search before answering. Only search results count.",
    temperature=0.4,
    tools=[types.Tool(google_search=types.GoogleSearch())],
    thinking_config=types.ThinkingConfig(thinking_level="low"),
)
resp = client.models.generate_content(model=MODEL, contents=PROMPT, config=cfg)
gm = resp.candidates[0].grounding_metadata
grounded = bool(gm and gm.web_search_queries)
print(f"finish_reason: {resp.candidates[0].finish_reason}")
print(f"grounded: {grounded}")
if grounded:
    print(f"queries: {list(gm.web_search_queries)}")
    print(f"chunks: {len(gm.grounding_chunks or [])}")
print(f"text: {resp.text}")
