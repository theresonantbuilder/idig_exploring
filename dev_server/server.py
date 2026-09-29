"""
Minimal local stand-in for `exploring_app` (SPEC.md §4.8: the real thing is a Next.js app
on port 3003 with basePath /exploring, backed by Supabase, a worker queue, and demo-gate
rate limiting — none of that exists yet). This is just enough to prove the real loop end to
end: extension sends a snip -> this runs the real two-call Gemini pipeline in a background
thread -> a plain HTML page (opened in a new tab, matching the real UX) polls for the result
and renders it. In-memory only; restarting this process loses every snip.

Run: python server.py
(Reads EXPLORING_GEMINI_API_KEY/EXPLORING_MODEL from iDIGcore_w_domains/.env, same as the
exp04_claims scripts.)
"""
import json
import re
import threading
import time
import uuid
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from google import genai

import pipeline

PORT = 3003
ALLOWED_SOURCES = {"idig-browser-extension"}

# id -> {status, headline, source_url, source_domain, captured_at, dig: {...} | None}
SNIPS: dict = {}
_client = genai.Client(api_key=pipeline.api_key())


def _run_pipeline(snip_id: str):
    snip = SNIPS[snip_id]
    snip["status"] = "researching"
    date = snip["captured_at"][:10]
    try:
        result = pipeline.run_headline_dig(_client, snip["headline"], snip["source_domain"], date)
    except Exception as e:
        snip["status"] = "error"
        snip["error"] = f"{type(e).__name__}: {e}"
        return
    if result["unverified"]:
        snip["status"] = "unverified"
        return
    snip["status"] = "ready"
    snip["dig"] = {
        "id": snip_id,
        "kind": "headline",
        "headline": snip["headline"],
        "source_url": snip["source_url"],
        "source_domain": snip["source_domain"],
        "result": result,
        "sources": result["sources"],
        "coverage": result["coverage"],
        "trails": [t for t in result["trails"] if t["rank"] is not None],
        "more_trails": [t for t in result["trails"] if t["rank"] is None],
        "explorer_count": 1,
        "researched_at": datetime.now(timezone.utc).isoformat(),
    }


def _validate(body: dict) -> str | None:
    headline = (body.get("headline") or "").strip()
    if not (3 <= len(headline) <= 300):
        return "headline must be 3-300 characters"
    url = body.get("source_url") or ""
    if not re.match(r"^https?://", url) or len(url) > 2048:
        return "source_url must be http(s) and ≤ 2048 chars"
    if body.get("source") not in ALLOWED_SOURCES:
        return "source not allowed"
    return None


PAGE_TEMPLATE = """<!doctype html>
<html><head><meta charset="utf-8"><title>iDIG Exploring</title>
<style>
body {{ font: 15px/1.5 system-ui, sans-serif; max-width: 640px; margin: 40px auto; padding: 0 20px; color: #16202e; }}
.muted {{ color: #5b6676; font-size: 13px; }}
h1 {{ font-size: 20px; }}
.claim {{ font-style: italic; border-left: 3px solid #d9b45a; padding-left: 12px; }}
h2 {{ font-size: 12px; text-transform: uppercase; letter-spacing: .06em; color: #5b6676; margin-top: 24px; }}
.contested {{ border-left: 3px solid #9a3412; padding: 8px 12px; background: #faf9f7; margin-bottom: 8px; }}
.held-by {{ font-weight: 700; font-size: 12px; color: #9a3412; display: block; }}
.trail {{ border: 1px solid #dcd7cc; border-radius: 8px; padding: 10px 12px; margin-bottom: 8px; }}
.move {{ font-size: 11px; font-weight: 700; text-transform: uppercase; background: #d9b45a; padding: 2px 6px; border-radius: 4px; }}
a {{ color: #b8912f; }}
</style></head>
<body>
<div id="root">Loading your dig&hellip;</div>
<script>
const id = {snip_id_json};
async function poll() {{
  const r = await fetch(`/exploring/api/snips/${{id}}`);
  const data = await r.json();
  if (data.status === 'received' || data.status === 'researching') {{
    document.getElementById('root').textContent = 'Researching… (' + data.status + ')';
    setTimeout(poll, 3000);
    return;
  }}
  if (data.status === 'unverified') {{
    document.getElementById('root').innerHTML = '<p>We could not confirm this against search results. Treat it with care.</p>';
    return;
  }}
  if (data.status === 'error') {{
    document.getElementById('root').innerHTML = '<p>Something went wrong: ' + (data.error || '') + '</p>';
    return;
  }}
  render(data.dig);
}}
function esc(s) {{ const d = document.createElement('div'); d.textContent = s ?? ''; return d.innerHTML; }}
function render(dig) {{
  const r = dig.result;
  const list = (items) => '<ul>' + items.map(i => `<li>${{esc(i)}}</li>`).join('') + '</ul>';
  const contested = r.contested.map(c => `<div class="contested"><span class="held-by">${{esc(c.held_by)}}</span>${{esc(c.position)}}</div>`).join('');
  const sources = dig.sources.map(s => `<li><a href="${{s.url}}" target="_blank" rel="noopener noreferrer">${{esc(s.title)}}</a></li>`).join('');
  const trail = (t) => `<div class="trail"><span class="move">${{esc(t.move)}}</span><p><strong>${{esc(t.question)}}</strong></p><p class="muted">${{esc(t.hook)}}</p></div>`;
  document.getElementById('root').innerHTML = `
    <p class="muted">From ${{esc(dig.source_domain)}} — <a href="${{dig.source_url}}" target="_blank" rel="noopener noreferrer">${{esc(dig.source_url)}}</a></p>
    <h1>${{esc(dig.headline)}}</h1>
    <p class="claim">${{esc(r.claim)}}</p>
    <h2>What happened</h2><p>${{esc(r.what_happened)}}</p>
    <h2>Why now</h2><p>${{esc(r.why_now)}}</p>
    <h2>Established</h2>${{list(r.established)}}
    <h2>Contested</h2>${{contested}}
    <h2>Left out</h2><p>${{esc(r.left_out)}}</p>
    <h2>Still unknown</h2>${{list(r.still_unknown)}}
    <h2>Sources</h2><ul>${{sources}}</ul>
    <h2>Trails</h2>${{dig.trails.map(trail).join('')}}
    <p class="muted">${{dig.explorer_count}} explorer${{dig.explorer_count === 1 ? '' : 's'}} dug this</p>
  `;
}}
poll();
</script>
</body></html>"""


class Handler(BaseHTTPRequestHandler):
    def _cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def _json(self, status: int, payload: dict):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self._cors()
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _html(self, status: int, body_str: str):
        body = body_str.encode("utf-8")
        self.send_response(status)
        self._cors()
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(204)
        self._cors()
        self.end_headers()

    def do_POST(self):
        if self.path != "/exploring/api/snips":
            return self._json(404, {"error": "not found"})
        length = int(self.headers.get("Content-Length", 0))
        try:
            body = json.loads(self.rfile.read(length) or b"{}")
        except Exception:
            return self._json(400, {"error": "invalid JSON"})

        err = _validate(body)
        if err:
            return self._json(400, {"error": err})

        snip_id = uuid.uuid4().hex
        SNIPS[snip_id] = {
            "status": "received",
            "headline": body["headline"].strip(),
            "source_url": body["source_url"],
            "source_domain": body.get("source_domain", ""),
            "captured_at": body.get("captured_at") or datetime.now(timezone.utc).isoformat(),
            "dig": None,
        }
        threading.Thread(target=_run_pipeline, args=(snip_id,), daemon=True).start()
        print(f"[snip] {snip_id}: {SNIPS[snip_id]['headline']!r} -- researching in background")
        self._json(201, {"id": snip_id, "status": "received", "delete_token": uuid.uuid4().hex})

    def do_GET(self):
        m = re.match(r"^/exploring/api/snips/([0-9a-f]+)$", self.path)
        if m:
            snip = SNIPS.get(m.group(1))
            if not snip:
                return self._json(404, {"error": "not found"})
            return self._json(200, {"status": snip["status"], "dig": snip["dig"], "error": snip.get("error")})

        m = re.match(r"^/exploring/([0-9a-f]+)", self.path)
        if m:
            if m.group(1) not in SNIPS:
                return self._html(404, "<p>This snip has expired or never existed.</p>")
            return self._html(200, PAGE_TEMPLATE.format(snip_id_json=json.dumps(m.group(1))))

        self._json(404, {"error": "not found"})

    def log_message(self, fmt, *args):
        pass  # keep the console to our own [snip]/pipeline prints


def main():
    print(f"iDIG Exploring dev server on http://localhost:{PORT}  (Ctrl+C to stop)")
    ThreadingHTTPServer(("localhost", PORT), Handler).serve_forever()


if __name__ == "__main__":
    main()
