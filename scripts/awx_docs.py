"""Query the Airwallex Docs MCP (no login). Usage: python scripts/awx_docs.py "question" """
import json
import sys as _s; _s.stdout.reconfigure(encoding="utf-8")
import sys

import httpx

URL = "https://mcp.sandbox.airwallex.com/docs"
HEADERS = {"Content-Type": "application/json", "Accept": "application/json, text/event-stream"}


def call(method, params, id_=1):
    r = httpx.post(URL, headers=HEADERS, timeout=90,
                   json={"jsonrpc": "2.0", "id": id_, "method": method, "params": params})
    r.raise_for_status()
    # SSE body: take the last "data:" line
    data = [line[5:] for line in r.text.splitlines() if line.startswith("data:")][-1]
    return json.loads(data)


if __name__ == "__main__":
    res = call("tools/call", {"name": "search_public_docs", "arguments": {"question": sys.argv[1]}})
    for c in res.get("result", {}).get("content", []):
        print(c.get("text", ""))
