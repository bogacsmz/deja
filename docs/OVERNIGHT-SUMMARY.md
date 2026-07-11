# Overnight Summary — Déjà

Autonomous backlog run (no human-loop). Each item is its own commit; `verify_all` (`--no-live` per
item, full-live after code changes) stayed green throughout. No live Slack writes, no `.env`/secret
edits, no new runtime dependencies.

## What was done (in order)

| # | Item | Commit |
|---|---|---|
| — | Track the untracked gate script (`verify_all.py`) | `50aec16` |
| 1 | **Architecture** — `docs/architecture.md` + Mermaid (RTS + MCP arms, shared engine) | `bfbce51` |
| 2 | **Submission** — `docs/SUBMISSION.md` (problem, solution, two techs, run, per-phase proof map) | `11308fb` |
| 3 | **Demo runbook** — `docs/DEMO.md` (verified queries + outcomes, verify_all/mcp_smoke fallback) | `7190f1b` |
| 4 | **README reorg** — clean top-README (phase story + gate table + MCP); starter demoted below | `58ac215` |
| 5 | **CI** — `.github/workflows/ci.yml` (pip install + pytest + `verify_all --no-live`) | `57afc52` |
| 6 | **Lint/format** — `ruff format` whole repo + enforce ruff in CI | `1222935` |
| 7 | **Test hardening** — `test_recall.py` + `test_edge_cases.py` (24→32 tests) | `ec0cd40` |
| 8 | **Robustness** — fail-safe `deja/` + timeouts + logs + `docs/HARDENING.md` | `f4e2378` |
| 9 | **Self-review** — `docs/PHASE-REVIEW.md` (rubric + open items) | `f382071` |

**Final state:** `verify_all` 15/15 live green · `--no-live` 10/10 green · `pytest` 32 passed ·
`ruff check` + `ruff format --check` clean.

## Decisions made
- **ruff format across the whole repo** (25 files, whitespace-only) rather than scoping to `deja/` —
  keeps `ruff format --check` clean repo-wide and lets CI enforce it. `ruff check` was already clean.
- **No mypy** — it would add a dependency and be noisy against scaffold + SDK stubs; `deja/` is
  already type-annotated. Recorded in PHASE-REVIEW / HARDENING.
- **No new deps** for robustness — a single 15s timeout + fail-silent behavior fits a non-disruptive
  agent better than a retry/backoff library.
- **Gate cadence** — `--no-live` after each item (fast, hermetic, deterministic); one **full-live**
  `verify_all` after the robustness changes (they touch `trigger`/`recall`/`memory`/`respond`) to
  confirm trigger 4/4, pipeline, recall 3/3, and MCP stdio still pass.
- **CI runs the hermetic subset** (`--no-live`) — live proofs need secrets a public runner won't have;
  they SKIP (never fail) there, and are proven locally.
- **Test mocking** — `deja` re-exports `recall`, so `from deja import recall` yields the function, not
  the module; recall unit tests patch the string target `deja.recall.WebClient`.

## What's open (honest)
- **Human-loop screenshots** (not code): the live Slack card render, App Home tab, the two button
  behaviors, and the Cursor MCP call. The underlying paths are all proven headlessly (Block Kit
  accepted, handlers registered, `mcp_smoke` green).
- **CI on GitHub**: committed, will run on the next push; verified locally via `--no-live`.
- **Production**: per-user OAuth (sandbox uses one user token); realistic multi-author seed history;
  optional cheap pre-filter before the LLM trigger. All scoped/noted, none blocking.

## Nothing was reverted
No item broke the gate, so nothing had to be rolled back. Every commit left `verify_all` green.
