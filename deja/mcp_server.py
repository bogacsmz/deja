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
        {summary, memories:[{source_message, what_happened_next, channel, author, ts, permalink,
        score}], searched}. Empty/error cases return memories: [] with an explanatory summary.
    """
    return await recall_memories(query, channel=channel, limit=limit)


def main() -> None:
    transport = os.environ.get(
        "DEJA_MCP_TRANSPORT", "stdio"
    )  # stdio | streamable-http | sse
    mcp.run(transport=transport)


if __name__ == "__main__":
    main()
