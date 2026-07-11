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

Beyond a single thread, Déjà reconstructs the **decision arc**: when a topic was debated repeatedly
across months, it stitches the threads into a timeline with the **standing decision**, its **owner**,
how many times it's come up, and every source link — or says **INCONCLUSIVE** when the evidence
doesn't support a decision (it never invents one). You can **💾 Save** a decision to a canonical log
that feeds a live Slack **Canvas** and the App Home digest.

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
| 6 · Seed | Realistic multi-author workspace + decision arcs | `seed-data integrity`, `realistic seed (unit)`, `seed dry-run` |
| 6 · Decision arc | Timeline + standing decision + owner + INCONCLUSIVE + save→Canvas | `arc synthesis`, `conflict/staleness`, `arc card`, `decision store` (hermetic) |

Plus `pytest` (hermetic unit + integration) — see [`../README.md`](../README.md) and
[`PHASE-REVIEW.md`](PHASE-REVIEW.md).

## Benchmark — the arc beats single-hit search

Déjà's claim is that reconstructing the **decision arc** beats returning the single most relevant
message. We measured it on a labelled set (recurring decisions, one-off decisions, and noise),
running the *real* synthesis engine.

Measured on the **exact live pipeline** — every case runs `judge(sentence) → recall_arc`, the same
LLM trigger and retrieval the live card uses.

**On a held-out set we never tuned on:** single-hit search surfaces the standing decision **1/6**
times and drifts onto an unrelated decision **1/4** times. **Déjà → 4/6, and never invents one
(0/4).** On the development set Déjà reaches **6/6** recurring decisions, single **7/7**, and **0**
false decisions.

> **We surface this, we don't hide it (Legibright DNA):** Slack's Real-Time Search is rate-limited to
> roughly **one call every few minutes** (measured `Retry-After: 288s`), so a 100+-query *live*
> benchmark is not possible. We run the **real engine including the LLM judge** (cached) through a
> reproducible RTS-free mirror, injected via `recall_fn`/`thread_fn`, and **calibrated to live**:
> sentences that fail live (the judge emits 'continuous deployment', which RTS misses) route through
> the same lexical expansion here and were verified to render the same result live. Held-out recurring
> is **4/6, not higher**, because the live card path is **lexical-only** (no LLM in the hot path, light
> on the rate-limited RTS) — the semantic-gap cases ('observability stack' → the *Datadog* decision)
> need the LLM expansion, which is available but off on the live card. An honest cost, stated plainly.
> Full method + limits in [`BENCHMARK.md`](BENCHMARK.md); one command: `python benchmarks/run.py --md`.

## Privacy

Déjà searches on the user's behalf with their RTS token, so it only ever sees channels that user can
already access — it never widens anyone's reach. Secrets live only in `.env` (git-ignored). In
production this becomes per-user OAuth.

## Built with

Slack (Bolt for Python, Socket Mode, Real-Time Search API, Block Kit) · MCP (official Python SDK /
FastMCP) · Claude Agent SDK on a Max subscription · Python 3.12+.
