"""Probe: which models accept google_search + response_schema in one call, and at what cost."""
import json
from google import genai
from google.genai import types

client = genai.Client()
schema = {"type": "object", "properties": {"what_happened": {"type": "string"},
          "president_title": {"type": "string"}}, "required": ["what_happened", "president_title"]}
prompt = ("As of 2026-09-23: in one sentence, what did Donald Trump say about Iran at the UN General "
          "Assembly this week? Also give his current title exactly as sources state it.")

for model in ["gemini-2.5-flash", "gemini-3-flash-preview", "gemini-3.5-flash", "gemini-3.8-flash"]:
    try:
        r = client.models.generate_content(model=model, contents=prompt, config=types.GenerateContentConfig(
            tools=[types.Tool(google_search=types.GoogleSearch())],
            response_mime_type="application/json", response_schema=schema, temperature=0.3))
        u = r.usage_metadata
        gm = r.candidates[0].grounding_metadata
        print(f"{model}: OK  json={json.loads(r.text)}  "
              f"tokens in/tool/out/think={u.prompt_token_count}/{u.tool_use_prompt_token_count}/"
              f"{u.candidates_token_count}/{u.thoughts_token_count}  queries={len(gm.web_search_queries or []) if gm else 0}")
    except Exception as e:
        print(f"{model}: FAIL {type(e).__name__}: {str(e)[:200]}")
