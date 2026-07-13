"""Déjà over HTTP — an MCP server the Slack **Slackbot MCP Client** connects to.

Separate process from the socket-mode agent (`slack run`): it publishes `recall_memory` and
`check_decision` (reusing `deja.memory` / `deja.govern`) over streamable-HTTP at `/mcp`, behind Slack
request-signature verification (`slack_identity_auth` — every request is signed by Slack; unsigned or
forged requests are rejected 401, fail-closed). Retrieval runs on the single INSTALLER user token
(`SLACK_USER_TOKEN`), so it is scoped to the channels the installing account can access — NOT to the
calling user. Per-caller scoping would need per-user OAuth (documented, not shipped).

Run (production: Railway, bound to $PORT, via railway_start.py; local: expose :3000 over any HTTPS
tunnel and point the manifest `mcp_servers` url at `<tunnel>/mcp`. See docs/DEPLOY.md):
    SLACK_SIGNING_SECRET=… python -m deja.mcp_http
"""

from __future__ import annotations

import contextlib
import logging
import os

from mcp.server.fastmcp import Context, FastMCP
from mcp.server.session import ServerSession
from mcp.server.transport_security import TransportSecuritySettings
from mcp.types import CallToolResult, TextContent, ToolAnnotations
from slack_sdk.signature import SignatureVerifier
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route
from starlette.types import ASGIApp, Receive, Scope, Send

from deja.arc import build_arc, render_record
from deja.govern import check_decision as _check_decision
from deja.memory import recall_memories

_log = logging.getLogger(__name__)

# DNS-rebinding host check is off: the SlackSignatureMiddleware below is the real auth boundary,
# and the check otherwise rejects the ngrok host Slack reaches us through.
mcp_server = FastMCP(
    "Déjà",
    stateless_http=True,
    json_response=True,
    transport_security=TransportSecuritySettings(enable_dns_rebinding_protection=False),
)


def render_memory(query: str, result: dict) -> str:
    """A readable rendering for the calling agent (Slackbot's LLM to relay). Synthesizes the
    recalled threads into a decision record (standing decision · owner · timeline · sources), or
    says INCONCLUSIVE when there's discussion but no clear decision — never a fake one."""
    memories = result.get("memories") or []
    if not memories:
        return result.get("summary", "No prior discussion found.")
    return render_record(build_arc(query, memories))


@mcp_server.tool(
    name="recall_memory",
    title="Recall team memory",
    description=(
        "Search this Slack workspace's history for prior decisions or claims relevant to a "
        "question, and return the concrete past thread plus what the team decided. Scoped to the "
        "channels the installing account can access (not per-caller). Use before acting on a proposal "
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
    # Gather a few extra threads so the arc has material to synthesize (the caller's `limit` is a
    # floor on distinct threads, not a cap on the record).
    result = await recall_memories(query, channel=channel, limit=max(limit, 6))
    return CallToolResult(
        content=[TextContent(type="text", text=render_memory(query, result))]
    )


def render_verdict(v: dict) -> str:
    """A readable rendering of a governance verdict for the calling agent (Slackbot's LLM to relay).
    The structured contract travels in `structuredContent`; this is the human-facing summary."""
    verdict = v.get("verdict", "INCONCLUSIVE")
    if verdict == "ALLOW":
        return f"ALLOW — {v.get('rationale') or 'no standing decision conflicts with this. Proceed.'}"
    if verdict == "CONFLICTS":
        who = v.get("owner") or "the team"
        when = f" on {v['decided_at']}" if v.get("decided_at") else ""
        srcs = "\n".join(f"• {s}" for s in (v.get("sources") or []))
        return (
            f"CONFLICTS — this re-opens a standing decision by {who}{when}: "
            f"“{v.get('standing_decision', '')}”. Discussed {v.get('times_discussed', 0)}×.\n"
            f"Sources:\n{srcs}"
        )
    return f"INCONCLUSIVE — {v.get('rationale') or 'discussed but never resolved; no verdict invented.'}"


@mcp_server.tool(
    name="check_decision",
    title="Check a proposal against the team's standing decisions",
    description=(
        "Governance check: before an agent (or a human) acts on a proposal, check whether it "
        "conflicts with a decision the team already made. Returns a verdict an agent can gate on — "
        "ALLOW (proceed), CONFLICTS (re-opens a settled decision; sources are clickable), or "
        "INCONCLUSIVE (discussed but never resolved — Déjà never invents a verdict, and every "
        "CONFLICTS/INCONCLUSIVE is backed by sources). Call before a consequential action "
        "('migrate the job queue to Temporal', 'switch auth providers'). Any agent can adopt this."
    ),
    annotations=ToolAnnotations(readOnlyHint=True, openWorldHint=False),
)
async def check_decision(
    proposal: str,
    ctx: Context[ServerSession, None],
) -> CallToolResult:
    meta = ctx.request_context.meta
    slack = (meta.model_extra or {}).get("slack", {}) if meta else {}
    _log.info(
        "mcp_http check_decision (slack user=%s team=%s) proposal=%r",
        slack.get("user_id"),
        slack.get("team_id"),
        proposal,
    )
    # Same engine + same sourceless-verdict=0 invariant as the ambient card and the stdio server.
    verdict = await _check_decision(proposal)
    return CallToolResult(
        content=[TextContent(type="text", text=render_verdict(verdict))],
        structuredContent=verdict,
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
        # Fail CLOSED on anything unexpected. slack_sdk's verifier does `int(timestamp)` on the raw
        # X-Slack-Request-Timestamp header with no guard, so a junk value ("abc", "", "1e9999") raises
        # ValueError — which, unhandled, would turn an UNAUTHENTICATED request into a 500 on a public
        # URL. Any failure to prove the request is a genuine, fresh Slack request is a 401, full stop.
        # (slack_sdk also enforces the 5-minute replay window and compares in constant time; both are
        # pinned by tests/test_robustness.py.)
        ok = False
        try:
            ok = bool(secret) and SignatureVerifier(
                signing_secret=secret
            ).is_valid_request(body, dict(request.headers))
        except Exception as e:  # noqa: BLE001 — malformed headers are an auth failure, not a crash
            _log.warning("mcp_http: malformed signature headers, rejecting: %s", e)
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
    # Railway (and most PaaS) inject the public port as $PORT; fall back to DEJA_MCP_HTTP_PORT/3000 locally.
    port = int(os.environ.get("PORT") or os.environ.get("DEJA_MCP_HTTP_PORT", "3000"))
    uvicorn.run(app, host="0.0.0.0", port=port)


if __name__ == "__main__":
    main()
