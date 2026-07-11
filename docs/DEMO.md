# Déjà — Demo Runbook

Everything below is seeded and verified. The card is posted **by Déjà** when you post a triggering
message in a channel it's in — so the demo is: *you type a normal question, Déjà surfaces the past
decision.*

## Setup (once, before the demo)
- Déjà app running: `slack run` (Socket Mode).
- Déjà is a **member** of the demo channels (`/invite @Déjà` in #eng, #product, #ops, #design, #general).
- Workspace already seeded (8 decision threads across 5 channels) — verify with
  `python scripts/seed_deja.py --dry-run` → expect **8 skipped**.
- One-liner health check: `python scripts/verify_all.py` → **GATE ✅ PASS**.

## Live script — type these, Déjà answers

Post each line as a normal message in the named channel. Déjà replies in-thread with a memory card;
the **"what happened next"** is the punchline.

| # | Channel | Type this | Déjà surfaces → *what happened next* |
|---|---|---|---|
| 1 (hero) | **#eng** | `Should we finally migrate our job queue to Temporal?` | *"…ROLLING BACK the Temporal migration — duplicate task execution + operational overhead. Sticking with Redis."* |
| 2 | **#product** | `Can we switch to usage-based pricing?` | *"We TRIED usage-based for a quarter and REVERTED — customers hated the unpredictable bills."* |
| 3 | **#product** | `Should we build our own auth?` | *"Decision: we're BUYING auth (Auth0), not building in-house."* |
| 4 | **#general** | `Let's do a daily sync standup` | *"We KILLED the sync standup and moved to an ASYNC thread."* |
| 5 | **#eng** | `postgres or mongodb for the main datastore?` | *"ADR-014: Postgres is the system of record."* |

Also seeded (spare): #eng monorepo→*"consolidated into a monorepo with Turborepo"*, #ops
k8s→*"managed containers (ECS Fargate), not self-hosted"*, #design CSS→*"standardizing on Tailwind +
Radix, dropping MUI."*

Show the buttons too: **🔗 Open source thread** jumps to the real thread; **🙅 Not relevant**
collapses the card. Point out the 🔒 privacy line.

## MCP arm — any agent can ask (Cursor / Claude Desktop)

With `.cursor/mcp.json` wired (see README), in Cursor:

> **"check our team's memory: should we migrate to Temporal?"**

Cursor calls the `recall_memory` tool → returns the structured memory (source message, *what happened
next* = the rollback, permalink). This is the composability story: the same memory, callable from
outside Slack.

## If the live demo wobbles — backup plan

Don't fight flaky Wi-Fi or RTS indexing on stage. Fall back to the deterministic proofs:

```bash
python scripts/verify_all.py        # cross-phase gate — one green table for every phase
python scripts/mcp_smoke.py         # a real MCP client over stdio pulls the Temporal memory
```

`verify_all` prints a phase-by-phase ✅ table (recall 3/3, pipeline, trigger 4/4, card, MCP stdio,
seed) — a single screen that proves every capability without touching the network UI. Keep a
screen-recording of the live cards as the ultimate fallback.

## Talking points (one line each)
- **Non-disruptive:** silent unless there's a real past decision — no channel spam.
- **Permission-aware:** searches only channels *you* can see (RTS on the user token).
- **Two required techs:** RTS recall + an MCP tool, sharing one engine.
- **Honest memory:** it shows *what was decided*, pulled from the thread — not just "you discussed this."
