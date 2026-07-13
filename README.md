# Déjà — the decision-governance layer for your Slack workspace

> **Slack is filling up with agents. None of them know what your team already decided.**
> **Déjà does — it watches them, and now they can ask.**
>
> *Most AI guardrails make you write the rules. Déjà reads them from what your team already decided.*

When a decision, claim, or proposal comes up in a channel — from a **human or an agent** — Déjà checks
it against the team's standing decisions and, **only when it conflicts**, drops a sourced guardrail:

> ⚠️ **Conflicts with a standing decision** · #eng
> *"Opening a PR to migrate the job queue to Temporal."* — the team **rolled this back** on Apr 23 (@maya):
> *"duplicate task execution under a network partition… sticking with Redis."* · 🔗 source

Two consumers, one engine:
- **Ambient (Mode B)** — Déjà reads every message, human **and agent**, and brakes conflicts. No opt-in
  needed; you don't grant permission, you're watched. ALLOW stays silent — the channel stays clean.
- **MCP (collaborative)** — any agent (or Slackbot) calls `check_decision(proposal)` →
  `ALLOW | CONFLICTS | INCONCLUSIVE`, always sourced. *Any agent in Slack can adopt this in five lines.*

**Slack Agent Builder Challenge · New Slack Agent track.** Required technologies: **RTS** (permission-
aware `assistant.search.context`) + **MCP** (two tools — `recall_memory` + `check_decision`), plus
agent-to-agent governance and ambient agent watching. The LLM trigger runs on a **Claude Max
subscription** — no paid API key. · powered by Legibright

## 👩‍⚖️ Judges start here

- **▶️ Live 24/7** — Déjà runs on Railway (Socket-Mode agent + MCP server in one service), not a
  laptop: [`deja-production.up.railway.app/healthz`](https://deja-production.up.railway.app/healthz) → `{"ok":true}`.
- **🎥 Demo video** — _<!-- add the Devpost/YouTube link here -->_ (the Planner-Bot "agents on trial" run: ALLOW→silent, CONFLICTS, INCONCLUSIVE).
- **✅ Prove it yourself — one command, no secrets, no API key:**
  ```bash
  pip install -e ".[test]" && python scripts/verify_all.py --no-live
  ```
  a phase-by-phase ✅ table. Then the numbers below, reproducibly:
  ```bash
  python benchmarks/run.py          # arc vs single-hit (held-out 4/6·3/5·0/4)
  python benchmarks/adversarial.py  # 83 hostile queries → 0 confident-wrong, recall 96%
  python benchmarks/governance.py   # 27 proposals → false-CONFLICTS 0, sourceless 0
  ```
  (The LLM judge is cached in `benchmarks/.judge_cache.json`, committed — so these run with **no API key**.)

## Quick start
```bash
pip install -e ".[test]"
cp .env.sample .env         # SLACK_USER_TOKEN (xoxp) + CLAUDE_CODE_OAUTH_TOKEN (`claude setup-token`)
slack run                   # the Slack app (Socket Mode): auto-trigger + memory cards
python -m deja.mcp_server   # the MCP server (stdio) for external agents
python scripts/verify_all.py   # the cross-phase gate — one green table (below)
```

## How it was built (the phase story)
| Phase | What shipped | Gate proof in `verify_all` |
|---|---|---|
| 1 · Skeleton | Bolt app boots, listeners wired | `deja imports`, `manifest valid` |
| 2 · Recall (RTS) | Forgotten thread resurfaces, deterministic | `recall resurfaces decision 3/3` |
| 3 · Judge→Recall→Reply | LLM trigger (Max subscription), end-to-end | `pipeline PASS`, `trigger 4/4` |
| 4 · Block Kit card | Interactive card + App Home + privacy | `card builders`, `App Home view` |
| 5 · MCP | `recall_memory` tool + real stdio client | `recall_memory unit`, `MCP stdio` |
| 6 · Seed | Realistic multi-author workspace + decision arcs | `seed integrity`, `seed dry-run` |
| 6 · Decision arc | Timeline + standing decision + owner + INCONCLUSIVE + save→Canvas | `arc synthesis`, `arc card`, `decision store` |
| v2 · Governance | `check_decision` verdict + ambient watch + Planner-Bot trial | `govern verdict`, `ambient loop-safety`, `governance benchmark` |
| 7 · Docs | Architecture · submission · demo · review | — |

**One command proves it all:** `python scripts/verify_all.py` → a phase-by-phase ✅ table
(`--no-live` for the hermetic subset in CI). See [`docs/architecture.md`](docs/architecture.md) ·
[`docs/SUBMISSION.md`](docs/SUBMISSION.md) · [`docs/DEMO.md`](docs/DEMO.md) ·
[`docs/PHASE-REVIEW.md`](docs/PHASE-REVIEW.md) · [`docs/HARDENING.md`](docs/HARDENING.md).

## Does the arc beat search? (benchmark)

Measured on the **exact live pipeline** (`judge(sentence) → recall_arc`). On a **held-out set we
never tuned on**, single-hit search surfaces the standing decision **1/6** times and drifts onto an
unrelated decision **1/4** times. **Déjà → 4/6 recurring · 3/5 single, never invents one (0/4).**
(Dev set: 6/6 recurring, 7/7 single, 0 false decisions.)

> **We surface this, we don't hide it:** Slack's Real-Time Search is rate-limited to ~1 call every
> few minutes (measured `Retry-After: 288s`), so a 100+-query *live* benchmark isn't possible. The
> benchmark runs the **real engine including the LLM judge** (cached) through a reproducible RTS-free
> mirror, **calibrated to live** — sentences that fail live route through the same code here and were
> verified to match. Held-out recurring is **4/6, not higher**, because the live card path is
> lexical-only (no LLM in the hot path): the semantic-gap cases ('observability stack' → the *Datadog*
> decision) need the LLM expansion, which is available but off live for speed. Honest cost, not a
> hidden failure. Method + limits: [`docs/BENCHMARK.md`](docs/BENCHMARK.md) · `python benchmarks/run.py --md`.

## Robustness — silence is cheap, a confident wrong answer is fatal

`benchmarks/adversarial.py` runs the live pipeline over **83 hostile queries** (paraphrases,
never-discussed topics, **lexical traps**, nonsense, typos, multi-topic, other languages,
false-premise provocations) and splits the result honestly: **correct 49 · MISS 2 · correct-silent
32 · CONFIDENT-WRONG 0** → **recall 96%, zero confident-wrong.** It runs against a *permissive* mirror
(a superset of live search), so a trap like "did we decide to **buy** a boat?" surfaces the "**BUYING**
auth" thread and the **grounding gate** must reject it: a decision shows only if one of the query's
distinctive *subject* words is in the retrieved threads — a shared action verb (buy · migrate · drop ·
launch) is not a topic match. See [`docs/ROBUSTNESS.md`](docs/ROBUSTNESS.md).

## Does the brake fire on the right proposal? (governance benchmark)

`benchmarks/governance.py` runs 27 labelled proposals through the **exact live verdict**
(`judge → check_decision`) — genuine conflicts, aligned proposals, never-discussed topics, lexical
traps, and discussed-but-undecided. Run once, no tuning: **false CONFLICTS 0 · sourceless verdict 0 ·
owner attribution 11/11 · precision 100% / recall 62%.** The 3 missed brakes are one honest class
(a positive adoption naming its rejected alternative *without* a rejection cue) — we would rather miss
a brake than raise a false one. Full method + the missed cases: [`docs/GOVERNANCE.md`](docs/GOVERNANCE.md).
External validation on 8 real OSS decision histories: [`docs/EXTERNAL.md`](docs/EXTERNAL.md).

## The governance contract — any agent can ask before it acts

Déjà's MCP server exposes **two** tools. The second is the interface contract: **any agent in Slack
can adopt this in five lines** — call it before a consequential action and honour the verdict.

```python
verdict = await mcp.call("check_decision", {"proposal": "Migrate the job queue to Temporal"})
if verdict["verdict"] == "CONFLICTS":
    # the team already rolled this back — stop and cite verdict["sources"]
    raise Halt(verdict["standing_decision"], by=verdict["owner"], at=verdict["decided_at"])
# ALLOW / INCONCLUSIVE → proceed (INCONCLUSIVE = discussed, never decided — Déjà won't invent one)
```

`check_decision(proposal)` → `{verdict: ALLOW|CONFLICTS|INCONCLUSIVE, standing_decision, owner,
decided_at, times_discussed, sources: [permalink, …], rationale}`. The verdict runs
the **same engine** as the ambient guardrail (judge → recall_arc → grounding gate). **A CONFLICTS with
no sources downgrades to INCONCLUSIVE** — a fabricated brake is worse than none. Measured:
[`docs/GOVERNANCE.md`](docs/GOVERNANCE.md) — false-conflicts **0**, sourceless **0**, owner **11/11**.

`recall_memory(query, channel=None, limit=3)` → `{summary, memories:[{source_message,
what_happened_next, channel, author, ts, permalink, score}], searched}` is unchanged and still there
for pure lookup. Both run on the installer's user token, so they only ever reach the channels the
installing account can access (not per-caller — see Honest limits). Verify end-to-end with `python scripts/mcp_smoke.py`.

```bash
python -m deja.mcp_server   # stdio (Cursor/Claude Desktop); DEJA_MCP_TRANSPORT=streamable-http for remote
```
```json
{ "mcpServers": { "deja": {
  "command": ".venv/bin/python", "args": ["-m", "deja.mcp_server"],
  "cwd": "/absolute/path/to/slackhack"
} } }
```

### Agents on trial — the brake, live (Mode B, no cooperation needed)
Déjà also watches the channel. A separate demo app, the **Planner Bot** (`planner_bot/`), posts action
proposals with **no awareness of Déjà** — Déjà catches the conflicting one and drops a sourced card,
stays silent on the aligned one, and refuses to invent a verdict on the undecided one. Governance
*without* the agent's opt-in. See [`planner_bot/README.md`](planner_bot/README.md).

## Layout
`deja/` — the engine (`recall`/RTS · `trigger`/LLM · `thread` enrichment · `card` · `store` ·
`govern`/the verdict · `mcp_server`/two tools) · `listeners/` — Slack events (incl. the ambient
watcher)/actions/views · `planner_bot/` — the demo agent Déjà puts on trial · `scripts/` — seed +
verify + smoke · `benchmarks/` · `tests/` · `docs/`.

<sub>Scaffolded from [Slack's Bolt for Python starter template](https://github.com/slack-samples/bolt-python-starter-agent) (MIT). The recall engine, decision arc, governance layer, MCP tools, benchmarks, and everything above are Déjà's own.</sub>
