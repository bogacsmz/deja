# Deploying Déjà (Railway)

Déjà must stay up for the whole judging window, so it runs on Railway, not a laptop + ngrok. One
Railway **web** service runs both long-lived processes in a single event loop via `railway_start.py`:
the Socket-Mode agent (ambient governance) **and** the MCP HTTP server (`/mcp`, bound to `$PORT`). If
either task fails, the process exits and Railway restarts the whole container — they recover together.

## One-time setup

```bash
railway login
railway init --name deja
railway add --service deja
```

Set the service variables (same values as local `.env`, minus the Planner Bot token which runs
separately):

| Variable | Purpose |
|---|---|
| `SLACK_BOT_TOKEN` (`xoxb-`) | the bot identity that posts cards |
| `SLACK_APP_TOKEN` (`xapp-`) | Socket Mode connection |
| `SLACK_USER_TOKEN` (`xoxp-`) | RTS search (installer-scoped — see README Honest limits) |
| `SLACK_SIGNING_SECRET` | verifies Slack's signature on `/mcp` (fail-closed 401) |
| `CLAUDE_CODE_OAUTH_TOKEN` | the judge LLM, on a **Claude Max subscription** (no paid API key) |
| `DEJA_BOT_USER_ID`, `DEJA_OWNER_FALLBACK` | self-message filter + Ask-the-owner routing |
| **`IS_SANDBOX=1`** | **required** — see below |

```bash
railway up --service deja --detach     # build (Nixpacks reads pyproject + Procfile) + deploy
railway domain --service deja          # public HTTPS URL, e.g. https://deja-production.up.railway.app
```

Point the Slack app's **MCP server URL** (and the manifest `mcp_servers` url) at
`https://<railway-domain>/mcp`. Verify: `GET /healthz` → `{"ok":true}`; an unsigned `POST /mcp` → `401`.

## 🔴 `IS_SANDBOX=1` is required

Railway containers run as **root**. The judge uses the Claude Agent SDK with
`permission_mode="bypassPermissions"` → `--dangerously-skip-permissions`, which the Claude Code CLI
**refuses to run as root** ("cannot be used with root/sudo privileges for security reasons") → the
judge fails closed (no-recall, no card). Setting `IS_SANDBOX=1` tells the CLI it is in an isolated
container and allows it. This is the single non-obvious deploy requirement; without it the ambient
agent connects and the MCP endpoint serves, but every judgment silently degrades to no-recall.

## Cost

The judge runs on the **Max subscription** (`CLAUDE_CODE_OAUTH_TOKEN`), so there is **no per-token
API bill** — the same auth as local dev. (`ANTHROPIC_API_KEY` is supported by the SDK as an
alternative but is not used here.)
