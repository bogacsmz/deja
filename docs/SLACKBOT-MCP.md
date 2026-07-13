# Slackbot calls Déjà — agent-to-agent governance, inside Slack

Déjà's headline proof: **Slackbot itself** — Slack's own built-in AI — calls Déjà's MCP tools to
answer *"what did we decide?"* and *"does this conflict with a standing decision?"*. One agent asking
another, live, with sourced answers. It retires the "isn't this just Slackbot?" objection by making
Slackbot the **client** of Déjà's governance, and it demonstrates the thesis literally: *any* agent in
Slack — including Slack's own — can adopt `check_decision` in five lines.

## What's live

`deja/mcp_http.py` serves **two** MCP tools over streamable-HTTP at `/mcp`, running on Railway
(`https://deja-production.up.railway.app/mcp`) in the same service as the Socket-Mode agent
(`railway_start.py`):

| Tool | Slackbot asks | Returns |
|---|---|---|
| `recall_memory` | "what did we decide about X?" | the standing decision + sources |
| `check_decision` | "does *\<proposal\>* conflict with a standing decision?" | `ALLOW / CONFLICTS / INCONCLUSIVE`, always sourced |

Every request is **Slack-signature verified and fail-closed**: an unsigned or forged `POST /mcp` gets
`401` before it reaches a tool (`SlackSignatureMiddleware`, `slack_identity_auth`). Both tools are
annotated **read-only**. Retrieval runs on the installer's user token (permission-scoped to that
account, not per-caller — see SUBMISSION.md → Honest limits). Covered hermetically in
`tests/test_mcp_http.py`.

## Verified live (the money beat)

Asked in Slack, Slackbot invoked Déjà's tools and relayed the sourced answers verbatim:

- **`recall_memory`** — *"what did we decide about our observability stack?"* → Slackbot returned the
  datastore decision on record (Postgres over Mongo, ADR-014) with its source, and honestly noted that
  no *observability* decision is recorded — it didn't invent one.
- **`check_decision`** — *"does migrating the job queue to Temporal conflict with a standing
  decision?"* → **Verdict: CONFLICTS** — the team rolled this back (Maya Chen, Apr 23), discussed 8×,
  backed by 8 sources, with the honest "loop in Maya to formally revisit."

Railway logs confirm both calls landed on the deployed endpoint and returned `200`.

## Connect Slackbot to Déjà (reproduce it)

1. The endpoint is already live on Railway; the app manifest's `mcp_servers` block points at
   `https://deja-production.up.railway.app/mcp` (`auth_type: slack_identity_auth`).
2. In Slack: DM **Slackbot** → **Apps** → **+** next to **Déjà** to connect.
3. Ask Slackbot, e.g. *"use check_decision: does migrating the job queue to Temporal conflict with a
   standing decision?"* → it calls Déjà and relays the sourced `CONFLICTS` verdict.

Local dev without Railway: `python -m deja.mcp_http` serves `:3000` (`/mcp`, `/healthz`); expose it
over any HTTPS tunnel and point the manifest `mcp_servers` url at `<tunnel>/mcp`. See
[`DEPLOY.md`](DEPLOY.md).

## Why it matters

The ambient agent watches the channel; this is the **collaborative** half — an agent (here, Slackbot)
*asks Déjà before it acts*. Same engine, same **sourceless-verdict = 0** guarantee, exposed as an
interface contract any agent can call. Slack's own AI adopting it is the strongest possible proof that
"any agent in Slack can adopt this" is real, not a slogan.
