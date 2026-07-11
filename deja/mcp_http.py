"""Déjà over HTTP — an MCP server the Slack **Slackbot MCP Client** connects to.

Separate process from the socket-mode agent (`slack run`): it publishes the same `recall_memory`
tool (reusing `deja.memory.recall_memories`) over streamable-HTTP at `/mcp`, behind Slack request-
signature verification. Uses `slack_identity_auth` — Slack signs every request and delivers the
caller's identity in `_meta.slack`, so recall stays permission-aware without a separate user OAuth.

Run (expose with ngrok; point the manifest `mcp_servers` url at `<ngrok>/mcp`):
    SLACK_SIGNING_SECRET=… python -m deja.mcp_http
"""

from __future__ import annotations

import contextlib
import logging
import os

from mcp.server.fastmcp import Context, FastMCP
from mcp.server.session import ServerSession
from mcp.types import CallToolResult, TextContent, ToolAnnotations
from slack_sdk.signature import SignatureVerifier
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route
from starlette.types import ASGIApp, Receive, Scope, Send

from deja.memory import recall_memories

_log = logging.getLogger(__name__)

mcp_server = FastMCP("Déjà", stateless_http=True, json_response=True)


def render_memory(result: dict) -> str:
    """A readable rendering of a recall result for the calling agent (Slackbot's LLM to relay)."""
    memories = result.get("memories") or []
    if not memories:
        return result.get("summary", "No prior discussion found.")
    lines = [result.get("summary", ""), ""]
    for m in memories:
        lines.append(f"• #{m['channel']}: {m['source_message']}")
        if m.get("what_happened_next"):
            lines.append(f"    → what happened next: {m['what_happened_next']}")
        lines.append(f"    {m['permalink']}")
    return "\n".join(line for line in lines if line is not None)


@mcp_server.tool(
    name="recall_memory",
    title="Recall team memory",
    description=(
        "Search this Slack workspace's history for prior decisions or claims relevant to a "
        "question, and return the concrete past thread plus what the team decided. Permission-"
        "aware — only channels the caller can access. Use before acting on a proposal "
        "('should we migrate to X?') to check whether the team already discussed or tried it."
    ),
    annotations=ToolAnnotations(readOnlyHint=True),
)
async def recall_memory(
    query: str,
    ctx: Context[ServerSession, None],
    channel: str | None = None,
    limit: int = 3,
) -> CallToolResult:
    meta = ctx.request_context.meta
    slack = (meta.model_extra or {}).get("slack", {}) if meta else {}
    _log.info(
        "mcp_http recall_memory (slack user=%s team=%s) query=%r",
        slack.get("user_id"),
        slack.get("team_id"),
        query,
    )
    result = await recall_memories(query, channel=channel, limit=limit)
    return CallToolResult(
        content=[TextContent(type="text", text=render_memory(result))]
    )


class SlackSignatureMiddleware:
    """Verify each request is a genuine, unmodified Slack request before the MCP app sees it.

    The signing secret is read lazily (per request) so the module imports without it — only a real
    run needs SLACK_SIGNING_SECRET in the environment.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request = Request(scope, receive, send)
        body = await request.body()

        secret = os.environ.get("SLACK_SIGNING_SECRET")
        ok = bool(secret) and SignatureVerifier(signing_secret=secret).is_valid_request(
            body, dict(request.headers)
        )
        if not ok:
            if not secret:
                _log.error("SLACK_SIGNING_SECRET not set — rejecting /mcp request")
            response = JSONResponse(
                {
                    "jsonrpc": "2.0",
                    "error": {"code": -32600, "message": "Invalid request"},
                    "id": None,
                },
                status_code=401,
            )
            await response(scope, receive, send)
            return

        async def replay_receive():
            return {"type": "http.request", "body": body, "more_body": False}

        await self.app(scope, replay_receive, send)


@contextlib.asynccontextmanager
async def _lifespan(_app):
    async with mcp_server.session_manager.run():
        yield


def build_app() -> Starlette:
    return Starlette(
        routes=[
            Route("/healthz", lambda _r: JSONResponse({"ok": True}), methods=["GET"]),
            Route(
                "/mcp",
                SlackSignatureMiddleware(mcp_server.streamable_http_app()),
                methods=["POST"],
            ),
        ],
        lifespan=_lifespan,
    )


app = build_app()


def main() -> None:
    import uvicorn
    from dotenv import load_dotenv

    load_dotenv(
        ".env", override=False
    )  # SLACK_SIGNING_SECRET + SLACK_USER_TOKEN for the running server
    port = int(os.environ.get("DEJA_MCP_HTTP_PORT", "3000"))
    uvicorn.run(app, host="0.0.0.0", port=port)


if __name__ == "__main__":
    main()
