"""Déjà's memory as an MCP server — any agent/IDE can query the team's past decisions.

Run (stdio, the default for local clients like Cursor / Claude Desktop):
    python -m deja.mcp_server

Remote transport (Agentforce / hosted clients):
    DEJA_MCP_TRANSPORT=streamable-http python -m deja.mcp_server

Auth: the server uses the RTS user token from .env (SLACK_USER_TOKEN), so results stay
permission-aware — only channels that user can access. In production this would be per-user
OAuth; for the sandbox the single user token is enough.
"""

from __future__ import annotations

import os

from dotenv import load_dotenv

load_dotenv(
    ".env", override=False
)  # make SLACK_USER_TOKEN available to the server process

from mcp.server.fastmcp import FastMCP  # noqa: E402

from deja.arc import as_record, build_arc  # noqa: E402
from deja.govern import check_decision as _check_decision  # noqa: E402
from deja.memory import recall_memories  # noqa: E402

mcp = FastMCP("deja")


@mcp.tool()
async def recall_memory(query: str, channel: str | None = None, limit: int = 3) -> dict:
    """Search this Slack workspace's history for prior decisions or claims relevant to a question,
    and return the concrete past thread plus what the team decided. Permission-aware: only searches
    channels the configured user can already access.

    Use this before acting on a proposal ("should we migrate to X?", "let's switch to Y") to check
    whether the team already discussed or tried it — and what the outcome was.

    Args:
        query: The question/claim to check the team's memory for (e.g. "should we migrate to Temporal?").
        channel: Optional channel name to restrict the search to (without the leading '#').
        limit: Maximum number of memories to return (default 3).

    Returns:
        {summary, memories:[…], searched, record}. `record` is the synthesized decision record —
        {found, standing_decision, owner, decided_at, times_discussed, confidence|inconclusive,
        timeline[], sources[]} — or found: false when nothing was recalled. Empty/error cases
        return memories: [] with an explanatory summary.
    """
    result = await recall_memories(query, channel=channel, limit=max(limit, 6))
    result["record"] = as_record(build_arc(query, result.get("memories", [])))
    return result


@mcp.tool(
    annotations={
        "title": "Check a proposal against the team's standing decisions",
        "readOnlyHint": True,  # never mutates — safe to call without per-call approval
        "openWorldHint": False,
    }
)
async def check_decision(proposal: str) -> dict:
    """Governance check: before an agent (or a human) acts on a proposal, check whether it conflicts
    with a decision the team already made. Returns a verdict an agent can gate on.

    Call this before taking an action a team might have already settled — "migrate the job queue to
    Temporal", "switch auth providers", "adopt an RFC process". Any agent in Slack can adopt this.

    Args:
        proposal: The action/proposal in free text (e.g. "migrate the job queue to Temporal").

    Returns:
        {verdict, standing_decision, owner, decided_at, times_discussed, sources[], rationale} where
        verdict is one of:
          ALLOW        — nothing on record contradicts it (proceed).
          CONFLICTS    — re-opens a decision the team settled the other way; `sources` are clickable.
          INCONCLUSIVE — discussed but never resolved, or grounding can't confirm a decision. Déjà
                         never invents a verdict — every CONFLICTS/INCONCLUSIVE is backed by sources.
    """
    return await _check_decision(proposal)


def main() -> None:
    transport = os.environ.get(
        "DEJA_MCP_TRANSPORT", "stdio"
    )  # stdio | streamable-http | sse
    mcp.run(transport=transport)


if __name__ == "__main__":
    main()
