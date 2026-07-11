# Slackbot MCP Client → Déjà (Phase 5b)

Let **Slackbot** itself call Déjà's `recall_memory` — agent-to-agent, inside Slack. This kills the
"isn't this just Slackbot?" objection on camera and uses Slack's newest capability (Slackbot MCP
Client, still rolling out).

**What's built (code, locally verified):** `deja/mcp_http.py` — a **separate HTTP process** (the
socket-mode agent is untouched) serving the same `recall_memory` tool over streamable-HTTP at `/mcp`,
behind Slack request-signature verification, classified **read-only**, reading the caller's identity
from `_meta.slack` (`slack_identity_auth`). Verified hermetically in `tests/test_mcp_http.py`
(signature gate + read-only annotation).

**What's NOT done (human-loop — needs you):** ngrok, the signing secret, the manifest reinstall, and
the actual Slackbot connect + call. Code can't do these. Runbook below.

## Runbook (bogac)

1. **ngrok** — install + authtoken (one-time):
   ```bash
   brew install ngrok && ngrok config add-authtoken <YOUR_TOKEN>   # token from ngrok.com dashboard
   ```
2. **Signing secret** — App Settings → **Basic Information → Signing Secret**; add to `.env`:
   ```
   SLACK_SIGNING_SECRET=…
   ```
3. **Run the endpoint** (separate terminal; leave `slack run` running too):
   ```bash
   python -m deja.mcp_http          # serves :3000 (/mcp, /healthz); reads .env
   curl -s localhost:3000/healthz   # -> {"ok": true}
   ```
4. **Expose it** (separate terminal; keep open — if the tunnel dies, the endpoint dies):
   ```bash
   ngrok http 3000                  # copy the https URL, e.g. https://abc123.ngrok-free.app
   ```
5. **Manifest** — add to the Déjà app manifest, set the url to `<ngrok>/mcp`, then **reinstall**
   (this keeps socket-mode + the ambient agent intact — the additions are additive):
   ```jsonc
   // oauth_config.scopes.bot += these:
   "mcp:connect", "users:read.email"        // (users:read is already present)
   // oauth_config.redirect_urls += :
   "https://<ngrok>.ngrok-free.app/slack/oauth_redirect"
   // top-level, new block:
   "mcp_servers": {
     "Déjà": { "url": "https://<ngrok>.ngrok-free.app/mcp", "auth_type": "slack_identity_auth" }
   }
   ```
6. **Connect in Slackbot:** DM **Slackbot** → **Apps** button → **+** next to **Déjà**.
7. **Discovery test:** ask Slackbot *"What tools are available from Déjà?"* → `recall_memory` listed. 📸
8. **Call test (the money beat):** ask Slackbot *"What did we decide about migrating the job queue to
   Temporal?"* → it calls `recall_memory` (**Allow once**) → returns the rollback memory + permalink. 📸

## Gate 5b
- ✅ Slackbot discovers the tool · ✅ Slackbot calls it and returns Déjà's memory → **screenshots**.
- ✅ Ambient side (channel card / auto-trigger) still works — it's a separate process, untouched.

## Open questions to confirm live (report back)
- **OAuth vs. no-OAuth:** this endpoint verifies the Slack signature and uses the workspace RTS token
  (`SLACK_USER_TOKEN`) — it does **not** implement the OAuth install routes the slack-samples example
  has (that example needed per-team bot tokens; we don't). Per the docs, `slack_identity_auth` needs
  no separate *user* OAuth. **If Slackbot rejects the connection asking for OAuth**, tell me — I'll add
  the `/slack/install` + `/slack/oauth_redirect` routes + installation store (the sample pattern).
- **Rollout:** the feature is "still rolling out." If Déjà doesn't appear under Slackbot → Apps, the
  sandbox may not have it enabled yet.

## If blocked
Per the plan: **stop and report the reason** (rollout / sandbox / auth). No loss — the ambient agent
(channel cards) and the Cursor/stdio MCP arm (`scripts/mcp_smoke.py`) already prove the tech.
