"""Integration smoke: a real MCP client talks to Déjà's server over stdio.

Needs a live Slack RTS token + the seeded workspace, so it skips when SLACK_USER_TOKEN / .env
is absent (e.g. tokenless CI). Runs headless — no browser.
"""

import asyncio
import os
import pathlib
import sys

import pytest

REPO = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))

_HAS_TOKEN = bool(os.environ.get("SLACK_USER_TOKEN")) or (REPO / ".env").exists()


@pytest.mark.skipif(
    not _HAS_TOKEN, reason="needs a live Slack RTS token + seeded workspace"
)
def test_mcp_stdio_recall_memory():
    import mcp_smoke  # noqa: PLC0415 — imported lazily so collection doesn't require the token

    names, data = asyncio.run(mcp_smoke.call())
    assert "recall_memory" in names
    memories = data.get("memories", [])
    assert memories, "MCP client got no memories"
    assert any("temporal" in m["source_message"].lower() for m in memories)
    assert all(m["permalink"].startswith("http") for m in memories)
