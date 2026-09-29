"""Same schema+tools+guaranteed-search-prompt test as debug_forced_search.py, but sweeping
thinking_level to see if more deliberation budget restores grounding_metadata in JSON mode."""
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
SCHEMA = {"type": "object", "properties": {"headline": {"type": "string"}, "summary": {"type": "string"}},
          "required": ["headline", "summary"]}

client = genai.Client(api_key=os.environ["EXPLORING_GEMINI_API_KEY"])

for level in ("low", "medium", "high"):
    cfg = types.GenerateContentConfig(
        system_instruction="Always run Google Search before answering. Only search results count.",
        temperature=0.4,
        response_mime_type="application/json", response_schema=SCHEMA,
        tools=[types.Tool(google_search=types.GoogleSearch())],
        thinking_config=types.ThinkingConfig(thinking_level=level),
    )
    resp = client.models.generate_content(model=MODEL, contents=PROMPT, config=cfg)
    gm = resp.candidates[0].grounding_metadata if resp.candidates else None
    grounded = bool(gm and gm.web_search_queries)
    print(f"level={level}: grounded={grounded}  text={resp.text[:120]!r}")
