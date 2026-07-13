# Déjà — Submission

> **Slack Agent Builder Challenge · Track: New Slack Agent**
> **Slack is filling up with agents. None of them know what your team already decided. Déjà does —
> it watches them, and now they can ask.**
> *Most AI guardrails make you write the rules. Déjà reads them from what your team already decided.*

## The problem

Your workspace is filling up with agents that take actions — open PRs, change pricing, pick a
datastore. **None of them know what your team already decided.** *"Migrate the job queue to
Temporal?"* — the team tried it four months ago and rolled it back for a concrete reason, but that
thread is buried. So a human re-opens the debate, or worse, **an agent just does it.** Most AI
guardrails ask you to write the rules up front. Teams never do — but they *have* already decided,
over and over, in Slack. That record is the rulebook; it's just unreadable at the moment it matters.

## The solution — a decision-governance layer

Déjà reads the standing decision out of the team's own history and, when a proposal **conflicts** with
it, drops a sourced brake. Same engine, **two consumers**:

- **Ambient (Mode B)** — Déjà watches every message, **human and agent**. On a conflict it posts a
  sourced card; on an aligned or never-discussed proposal it stays **silent** (the channel stays
  clean). No opt-in — you don't grant it permission, you're watched.
- **MCP (collaborative)** — any agent (or Slackbot) calls `check_decision(proposal)` →
  `ALLOW | CONFLICTS | INCONCLUSIVE`, always sourced. **Any agent in Slack can adopt this in five lines.**

> ⚠️ **Conflicts with a standing decision** · #eng
> *"Opening a PR to migrate the job queue to Temporal."* — the team **rolled this back** Apr 23 (@maya):
> *"duplicate task execution under a network partition… sticking with Redis."*
> [🔗 Open source thread] · 🔒 Only searches channels this app can access

Under the hood is the **decision arc**: threads debated repeatedly across months are stitched into a
timeline with the **standing decision**, its **owner**, how many times it's come up, and every source
link — or **INCONCLUSIVE** when the evidence doesn't support a verdict (**it never invents one; a
sourceless CONFLICTS downgrades to INCONCLUSIVE**). You can **💾 Save** a decision to a canonical log
that feeds a live Slack **Canvas** and the App Home digest.

## The two required technologies (and what we added)

1. **Real-Time Search (RTS)** — `deja/recall.py` calls `assistant.search.context` with the user's
   token to find prior discussions — scoped to the channels the installing account can access (not
   per-caller; see Honest limits).
2. **MCP** — `deja/mcp_server.py` publishes **two** tools (FastMCP, stdio + HTTP): `recall_memory`
   (lookup) and **`check_decision`** (the governance verdict — the interface contract other agents
   adopt). Both share one engine.

Added on top: **agent-to-agent governance** (an agent asks Déjà before it acts) and **ambient agent
watching** (Déjà brakes an agent that *didn't* ask), demonstrated live by a standalone **Planner Bot**.

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
| v2 · Governance | `check_decision` verdict + ambient watch + loop-safety + Planner-Bot trial | `govern verdict`, `ambient loop-safety`, `governance benchmark` |

Plus `pytest` (hermetic unit + integration, 123 tests) and `python scripts/verify_all.py --no-live` —
see [`../README.md`](../README.md).

## Benchmark — the arc beats single-hit search

Déjà's claim is that reconstructing the **decision arc** beats returning the single most relevant
message. We measured it on a labelled set (recurring decisions, one-off decisions, and noise),
running the *real* synthesis engine.

Measured on the **exact live pipeline** — every case runs `judge(sentence) → recall_arc`, the same
LLM trigger and retrieval the live card uses.

**On a held-out set we never tuned on:** single-hit search surfaces the standing decision **1/6**
times and drifts onto an unrelated decision **1/4** times. **Déjà → 4/6 recurring, 3/5 single, and
never invents one (0/4).** On the development set Déjà reaches **6/6** recurring decisions, single
**7/7**, and **0** false decisions.

> **We surface this, we don't hide it (Legibright DNA):** Slack's Real-Time Search is rate-limited to
> roughly **one call every few minutes** (measured `Retry-After: 288s`), so a 100+-query *live*
> benchmark is not possible. We run the **real engine including the LLM judge** (cached) through a
> reproducible RTS-free mirror, injected via `recall_fn`/`thread_fn`, and **calibrated to live**:
> sentences that fail live (the judge emits 'continuous deployment', which RTS misses) route through
> the same lexical expansion here and were verified to render the same result live. Held-out recurring
> is **4/6, not higher**, because the live card path is **lexical-only** (no LLM in the hot path, light
> on the rate-limited RTS) — the semantic-gap cases ('observability stack' → the *Datadog* decision)
> need the LLM expansion, which is available but off on the live card. An honest cost, stated plainly.
> Full method + limits in [`BENCHMARK.md`](BENCHMARK.md); one command: `python -m benchmarks.run --md`.

## Robustness — the number we lead with

A jury will type anything into the sandbox. **Principle: silence is cheap, a confident wrong answer
is fatal — but a silent bot is a cheap victory, so we measure recall too.**
`benchmarks/adversarial.py` runs the full live pipeline over **83 hostile queries** (paraphrases,
never-discussed topics, **lexical traps**, nonsense, typos, multi-topic, other languages,
false-premise provocations) and splits the outcome honestly:

> **correct 49 · MISS 2 · correct-silent 32 · CONFIDENT-WRONG 0** → **recall 49/51 = 96%** on the
> queries that have a real decision to find, with **zero** confident-wrong answers.

It runs against a **permissive** RTS mirror — a *superset* of what live search returns — so a lexical
trap deliberately surfaces the off-topic arc ("did we decide to **buy** a boat?" pulls the "we're
**BUYING** auth (Auth0)" thread) and the **grounding gate** must reject it. Confident-wrong 0 under
retrieval looser than live means confident-wrong 0 live.

Déjà is a decision **engine**, not a search box: each retrieved thread is a state-machine transition
(proposed → adopted → reversed → revived) and the standing decision is *derived* from the last
state-changing one, so a re-opened topic never overturns the decision on record. The **grounding
gate** (`deja/arc.py` `_grounded`, on EVERY query) shows a decision only if one of the query's
*distinctive subject words* actually appears in the retrieved threads — a shared decision/action verb
(buy · migrate · drop · launch · roll · stay) is **not** a topic match, so "buy a boat" ≠ "buy auth".
Provocations get the *actual* decision (contradicting the false premise) or nothing. The 2 misses are
honest silences, never wrong answers (one French phrasing — Déjà is monolingual; and "did we already
launch GA?", whose only subject is the 2-letter "GA"). Full run in [`ROBUSTNESS.md`](ROBUSTNESS.md). Plus
**rate-limit grace**: when Slack throttles the search, Déjà says so ("ask again in a minute").

## Governance — does the brake fire on the right proposal?

`benchmarks/governance.py` runs 27 labelled proposals through the **exact live verdict**
(`judge → check_decision`): genuine conflicts, aligned proposals, never-discussed topics, lexical
traps, discussed-but-undecided. Run once, no tuning:

> **CONFLICTS precision 100% · recall 62% · false CONFLICTS 0 · sourceless verdict 0 · owner
> attribution 11/11 right.**

The two errors that would disqualify a brake — a **false alarm** and an **unsourced verdict** — never
happened. The 3 missed brakes are one honest class (a positive adoption that names its rejected
alternative *without* a rejection cue the engine reads); we would rather miss a brake than raise a
false one. Method + the missed cases: [`GOVERNANCE.md`](GOVERNANCE.md). External validation on 8 real
open-source decision histories (multi-author, months apart, with a real reversal): [`EXTERNAL.md`](EXTERNAL.md).

### Agents on trial — the brake, live
A separate demo app, the **Planner Bot** (`planner_bot/`), posts three proposals with **no awareness
of Déjà**. Déjà — running independently — watches the channel and: **brakes** the Temporal migration
(CONFLICTS, sourced), stays **silent** on the aligned usage add-on (ALLOW), and **refuses to invent a
verdict** on the RFC-process question discussed-but-never-decided (INCONCLUSIVE). One AI stopping
another, live, with sourced evidence — governance *without* the watched agent's cooperation.

**Bot-loop safety (day one):** Déjà never reacts to its own output, never answers another bot's reply
to Déjà (no ping-pong), posts **at most once per proposal** (atomic in-process claim, race-tested),
and backs off on rate limits. ALLOW is never posted to the channel — only CONFLICTS and, when needed,
INCONCLUSIVE are visible. Loop-safety is covered by hermetic tests (`tests/test_ambient.py`).

## Honest limits

- **We can't force an agent, only watch it.** Mode A (the agent asks) needs the agent to adopt
  `check_decision`; Mode B (we watch) catches messages posted to a channel Déjà is in — a silent
  side-channel API call we can't see.
- **The seed is synthetic.** A realistic multi-author workspace with back-dated arcs, not a real org's
  history. External validation on real OSS histories is the counterweight, but it's 8 cases.
- **Monolingual.** The judge and grounding gate are English; a French phrasing is an honest miss, not
  a wrong answer.
- **The single-hit / recall trade.** The live card path is lexical-only (no LLM in the hot path) to
  stay light on rate-limited RTS, so semantic-gap recalls need the (available but off-by-default) LLM
  expansion. We publish the real number (recurring 4/6) rather than the tuned one.
- **Owner attribution is measured, not assumed.** 11/11 right here; if a future regression makes it
  wrong, the honest fix is to show no owner rather than the wrong one.
- **Permission scope is the installer's, not the viewer's.** Déjà searches with the installing
  account's user token, so it reaches exactly the channels that one account can — not the channels the
  *asking* user can. Per-viewer permission scoping requires per-user OAuth: documented here, not
  shipped. We say "channels this app can access," never "channels *you* can access."
- **Two MCP tools, two jobs.** `recall_memory` is a **lexical lookup** (the raw retrieval); on a bare
  question it can surface an adjacent thread. `check_decision` is the **governance path** — judge →
  arc → grounded verdict, sourceless-verdict = 0. For "did we decide X?" questions, use `check_decision`.

## Security

The MCP endpoint verifies Slack's request signature and is **fail-closed**: an unsigned or forged
request gets `401` before it can reach a tool — no valid Slack identity, no access. The signing secret
is read per-request and, when unset, every request is rejected (never fail-open). Retrieval is scoped
to one installer token (above), and secrets live only in `.env` (git-ignored, never committed).

## Privacy

Déjà searches with the installing account's RTS token, so it only ever sees channels **that account**
can already access — it never widens anyone's reach beyond one real user's permissions. Secrets live
only in `.env` (git-ignored). In production this becomes per-user OAuth (per-viewer scoping).

## Built with

Slack (Bolt for Python, Socket Mode, Real-Time Search API, Block Kit) · MCP (official Python SDK /
FastMCP) · Claude Agent SDK on a Max subscription · Python 3.12+.
