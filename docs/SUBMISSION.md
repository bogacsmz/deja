# Déjà — Submission

> **Slack Agent Builder Challenge · Track: New Slack Agent**
> The team memory that stops you re-litigating decisions you already made.

## The problem

Every team re-opens settled debates. *"Should we migrate the job queue to Temporal?"* — you tried it
four months ago and rolled it back for a concrete reason, but that thread is buried and nobody
remembers. The knowledge exists in Slack; it's just unfindable at the moment it matters. So the
discussion runs again, the same mistakes get re-proposed, and time evaporates.

## The solution — Déjà

Déjà is a Slack agent that watches for a decision/claim/proposal and quietly surfaces the **concrete
past thread** the team already had on it — including **what was decided** — as a clean memory card:

> ⏳ **Déjà vu — your team already discussed this** (searched *migrate job queue Temporal*)
> **#eng** · @alex · Jul → *"Kicking off the migration from Redis to Temporal…"*
> 🧵 **What happened next:** *"Update after 3 weeks: we're ROLLING BACK… operational overhead isn't worth it. Sticking with Redis."*
> [🔗 Open source thread] [🙅 Not relevant] · 🔒 Only searches channels you can access

It's **non-disruptive** (silent unless it finds a real match), **permission-aware** (only your
channels), and its memory is also a standalone **MCP tool** any external agent can call.

## The two required technologies

1. **Real-Time Search (RTS)** — `deja/recall.py` calls `assistant.search.context` with the user's
   token to find prior discussions, permission-aware by construction.
2. **MCP** — `deja/mcp_server.py` publishes a `recall_memory` tool (FastMCP, stdio + HTTP) so Cursor,
   Claude Desktop, or Agentforce can query the team's memory. Both share one engine.

**LLM:** the trigger judgment runs on a **Claude Max subscription** (Claude Agent SDK via
`CLAUDE_CODE_OAUTH_TOKEN`) — no paid API key.

## How it works

`Slack message → judge (LLM) → recall (RTS) → rank + drop noise → enrich with the decision
(conversations.replies) → Block Kit card`. The MCP arm skips the LLM (the caller is the LLM) and
returns structured `{summary, memories[], searched}`. See [`architecture.md`](architecture.md).

## How to run

```bash
pip install -e ".[test]"
# .env: SLACK_USER_TOKEN=xoxp-…  ·  CLAUDE_CODE_OAUTH_TOKEN=…  (from `claude setup-token`)
slack run                         # Slack app (Socket Mode) — auto-trigger + cards
python -m deja.mcp_server         # MCP server (stdio) for external agents
python scripts/verify_all.py      # the cross-phase gate (see below)
```

## What's proven

`scripts/verify_all.py` is a single cross-phase gate; every phase maps to a check in it
(`--no-live` runs the hermetic subset for CI):

| Phase | Delivered | Proof in `verify_all` |
|---|---|---|
| 1 · Skeleton | Bolt app boots, listeners wired, manifest valid | `deja package imports`, `manifest.json valid` |
| 2 · Recall (RTS) | Forgotten thread resurfaces, deterministic | `recall resurfaces decision 3/3` (repeatable) |
| 3 · Judge→Recall→Reply | LLM trigger on the Max subscription, end-to-end | `end-to-end pipeline PASS`, `trigger-judgment 4/4 (subscription)` |
| 4 · Block Kit card | Interactive card + App Home + privacy | `memory-card builders`, `App Home view` |
| 5 · MCP | `recall_memory` tool, real external client | `recall_memory logic (unit)`, `real MCP client over stdio` |
| 6 · Seed | Realistic 8-thread / 5-channel workspace | `seed-data integrity`, `realistic seed (unit)`, `seed dry-run` |

Plus `pytest` (hermetic unit + integration) — see [`../README.md`](../README.md) and
[`PHASE-REVIEW.md`](PHASE-REVIEW.md).

## Privacy

Déjà searches on the user's behalf with their RTS token, so it only ever sees channels that user can
already access — it never widens anyone's reach. Secrets live only in `.env` (git-ignored). In
production this becomes per-user OAuth.

## Built with

Slack (Bolt for Python, Socket Mode, Real-Time Search API, Block Kit) · MCP (official Python SDK /
FastMCP) · Claude Agent SDK on a Max subscription · Python 3.12+.
