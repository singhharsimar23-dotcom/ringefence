"""Run payroll through Ringfence with any model on OpenRouter.

Ringfence is an MCP server, so the model only needs tool calling. This script lists the Ringfence tools,
hands them to an OpenRouter model, and runs the tool calls the model asks for.

    OPENROUTER_API_KEY=... uv run python examples/openrouter_agent.py demo/payday
    uv run python examples/openrouter_agent.py --tools      # connect and list the tools, no key needed

Env: RINGFENCE_MCP_URL (default: the public demo), OPENROUTER_MODEL (default anthropic/claude-sonnet-4.5).
"""
import asyncio
import json
import os
import sys
from pathlib import Path

import httpx
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

URL = os.environ.get("RINGFENCE_MCP_URL", "https://ringfence-hs23-eu.indiasouthcentral.cloudapp.azure.com/mcp")
MODEL = os.environ.get("OPENROUTER_MODEL", "anthropic/claude-sonnet-4.5")
PROMPT = "Run this week's payroll from the files I gave you. Show what will be paid and anything suspicious."


def as_openai_tool(t) -> dict:
    return {"type": "function", "function": {"name": t.name, "description": t.description or "", "parameters": t.inputSchema}}


async def main(folder: str | None) -> None:
    async with streamable_http_client(URL) as streams, ClientSession(*streams[:2]) as mcp:
        await mcp.initialize()
        tools = (await mcp.list_tools()).tools
        if folder is None:
            for t in tools:
                print(t.name, "-", (t.description or "").split("\n")[0])
            return
        files = {p.name: p.read_text(encoding="utf-8") for p in sorted(Path(folder).iterdir()) if p.is_file()}
        msgs = [{"role": "user", "content": f"{PROMPT}\n\nFiles (pass them to run_payroll verbatim):\n{json.dumps(files)}"}]
        async with httpx.AsyncClient(timeout=300) as http:
            for _ in range(8):  # a few tool rounds are enough: run, show the link, stop
                r = await http.post("https://openrouter.ai/api/v1/chat/completions",
                                    headers={"Authorization": f"Bearer {os.environ['OPENROUTER_API_KEY']}"},
                                    json={"model": MODEL, "messages": msgs, "tools": [as_openai_tool(t) for t in tools]})
                r.raise_for_status()
                msg = r.json()["choices"][0]["message"]
                msgs.append(msg)
                if not msg.get("tool_calls"):
                    print(msg.get("content"))
                    return
                for c in msg["tool_calls"]:
                    out = await mcp.call_tool(c["function"]["name"], json.loads(c["function"]["arguments"] or "{}"))
                    text = "".join(b.text for b in out.content if hasattr(b, "text"))
                    msgs.append({"role": "tool", "tool_call_id": c["id"], "content": text})


if __name__ == "__main__":
    asyncio.run(main(None if "--tools" in sys.argv else sys.argv[1]))
