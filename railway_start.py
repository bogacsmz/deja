"""Single Railway entrypoint — runs BOTH long-lived processes in one asyncio event loop:

  * the Socket-Mode agent (`app.py`, ambient governance over the Slack websocket), and
  * the MCP HTTP server (`deja.mcp_http`, the Slackbot MCP endpoint, bound to $PORT).

Railway runs one start command per service; this lets a single `web` service serve both. If either
task raises, `asyncio.gather` propagates it, the process exits, and Railway restarts the whole
container — so the socket agent and the MCP endpoint always recover together, never half-up.

Local dev still runs them separately (`python app.py` + `python -m deja.mcp_http`); this file is the
deploy entrypoint only (Procfile `web`).
"""

from __future__ import annotations

import asyncio
import logging
import os

from dotenv import load_dotenv

# Configure logging BEFORE importing app.py (whose module-level basicConfig would otherwise win at
# DEBUG). First basicConfig call wins, so this pins the deployed logs to INFO.
logging.basicConfig(level=logging.INFO)
load_dotenv(".env", override=False)


async def main() -> None:
    import uvicorn
    from slack_bolt.adapter.socket_mode.async_handler import AsyncSocketModeHandler

    from app import app as bolt_app
    from deja.mcp_http import app as mcp_asgi

    app_token = os.environ.get("SLACK_APP_TOKEN")
    if not app_token:
        raise SystemExit(
            "SLACK_APP_TOKEN missing — socket mode needs an app-level token (xapp-…)."
        )

    port = int(os.environ.get("PORT") or os.environ.get("DEJA_MCP_HTTP_PORT", "3000"))
    handler = AsyncSocketModeHandler(bolt_app, app_token)
    server = uvicorn.Server(
        uvicorn.Config(mcp_asgi, host="0.0.0.0", port=port, log_level="info")
    )
    logging.getLogger(__name__).info(
        "Déjà deploy: starting socket-mode agent + MCP HTTP server on :%s", port
    )
    await asyncio.gather(handler.start_async(), server.serve())


if __name__ == "__main__":
    asyncio.run(main())
