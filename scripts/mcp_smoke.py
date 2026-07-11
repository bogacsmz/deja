#!/usr/bin/env python3
"""Gate-5 deterministic proof: a real MCP client talks to Déjà's server over stdio.

Spawns `python -m deja.mcp_server`, lists tools, calls recall_memory, and asserts the seeded
Temporal thread (with its rollback decision + permalink) comes back. No browser needed.

Prereqs: seeded workspace, SLACK_USER_TOKEN in .env.  Run:  python scripts/mcp_smoke.py
"""
from __future__ import annotations

import asyncio
import json
import os
import pathlib
import sys

REPO = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(str(REPO / ".env"), override=False)

from mcp import ClientSession, StdioServerParameters  # noqa: E402
from mcp.client.stdio import stdio_client  # noqa: E402

QUERY = "should we migrate our job queue to Temporal"


def _structured(result) -> dict:
    """Pull the tool's structured dict out of a CallToolResult, robustly across SDK versions."""
    data = getattr(result, "structuredContent", None)
    if not data:
        text = "".join(getattr(c, "text", "") for c in result.content)
        data = json.loads(text) if text.strip() else {}
    # FastMCP may wrap a bare return under {"result": ...}
    if isinstance(data, dict) and set(data.keys()) == {"result"}:
        data = data["result"]
    return data or {}


async def call() -> tuple[list[str], dict]:
    params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "deja.mcp_server"],
        cwd=str(REPO),
        env=os.environ.copy(),  # pass SLACK_USER_TOKEN through to the server subprocess
    )
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            listed = await session.list_tools()
            names = [t.name for t in listed.tools]
            result = await session.call_tool("recall_memory", {"query": QUERY})
            return names, _structured(result)


async def main() -> int:
    names, data = await call()
    print("tools exposed:", names)
    print("summary:", data.get("summary"))
    print("searched:", data.get("searched"))
    memories = data.get("memories", [])
    for m in memories:
        print(f"  - #{m['channel']} · score {m['score']} :: {m['source_message'][:60]!r}")
        print(f"      what_happened_next: {(m['what_happened_next'] or '(none)')[:80]!r}")
        print(f"      permalink: {m['permalink']}")

    ok = (
        "recall_memory" in names
        and bool(memories)
        and any("temporal" in m["source_message"].lower() for m in memories)
        and all(m["permalink"].startswith("http") for m in memories)
        and any("rolling back" in (m["what_happened_next"] or "").lower() for m in memories)
    )
    print("\nMCP SMOKE:", "PASS ✅ (external client got the Temporal memory + decision)" if ok else "FAIL ❌")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
