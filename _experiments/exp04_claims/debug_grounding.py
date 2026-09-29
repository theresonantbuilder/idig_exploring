"""
One minimal grounded call, dumping the raw response so we can tell whether search
genuinely didn't fire (grounding_metadata is None / empty) or whether it fired and
run_experiment.py's extraction just isn't reading it correctly. Costs one small call.

Run: python debug_grounding.py
(Reads EXPLORING_GEMINI_API_KEY from iDIGcore_w_domains/.env — Exploring's own dedicated
key, not the one shared by Hiring/Knowledge Center/Jobs Manager or Movies' separate key.)
"""
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from google import genai
from google.genai import types

HERE = Path(__file__).resolve().parent
CORE = HERE.parents[2] / "iDIGcore_w_domains"
load_dotenv(CORE / ".env")

MODEL = os.environ.get("EXPLORING_MODEL", "gemini-3.8-flash")

# A prompt that's IMPOSSIBLE to answer from training data alone, forcing the model
# to search if it's going to search at all.
PROMPT = "What is today's top headline on the BBC News homepage right now? Search for it."

cfg = types.GenerateContentConfig(
    system_instruction="Always run Google Search before answering. Only search results count.",
    temperature=0.4,
    tools=[types.Tool(google_search=types.GoogleSearch())],
    thinking_config=types.ThinkingConfig(thinking_level="low"),
)

client = genai.Client(api_key=os.environ["EXPLORING_GEMINI_API_KEY"])
print(f"Calling {MODEL}...")
resp = client.models.generate_content(model=MODEL, contents=PROMPT, config=cfg)

print("\n--- response text ---")
print(resp.text)

print("\n--- finish_reason ---")
print(resp.candidates[0].finish_reason)

gm = resp.candidates[0].grounding_metadata
print("\n--- grounding_metadata is None? ---")
print(gm is None)

if gm is not None:
    print("\n--- raw grounding_metadata repr ---")
    print(repr(gm))
    print("\n--- web_search_queries ---")
    print(gm.web_search_queries)
    print("\n--- grounding_chunks count ---")
    print(len(gm.grounding_chunks or []))
    print("\n--- grounding_supports count ---")
    print(len(gm.grounding_supports or []))

print("\n--- google-genai SDK version ---")
try:
    import google.genai as g
    print(getattr(g, "__version__", "unknown"))
except Exception as e:
    print(f"couldn't read version: {e}")
