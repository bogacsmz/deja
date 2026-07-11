# Déjà — Phase Review (self-assessment)

Rubric per phase: **Works** (runs correctly) · **Tested** (hermetic and/or live proof) ·
**Documented** · **Demo-ready**. ✅ met · ◐ met with a human-loop caveat.

| Phase | Works | Tested | Documented | Demo-ready | Evidence |
|---|:--:|:--:|:--:|:--:|---|
| 1 · Skeleton (Bolt app, listeners, manifest) | ✅ | ✅ | ✅ | ✅ | `verify_all`: deja imports, manifest valid |
| 2 · Recall (RTS) | ✅ | ✅ | ✅ | ✅ | `test_recall.py` (unit) + `recall 3/3` (live, repeatable) |
| 3 · Judge→Recall→Reply + trigger | ✅ | ✅ | ✅ | ✅ | `pipeline PASS` + `trigger 4/4` (Max subscription) |
| 4 · Block Kit card + App Home + privacy | ✅ | ✅ | ✅ | ◐ | card/home unit tests + validated render (Slack accepted blocks); **live card/App Home/button screenshots are human-loop** |
| 5 · MCP (`recall_memory`) | ✅ | ✅ | ✅ | ◐ | unit + real stdio smoke (`mcp_smoke`); **Cursor/Claude-Desktop screenshot is human-loop** |
| 6 · Realistic seed (8 threads / 5 channels) | ✅ | ✅ | ✅ | ✅ | seed unit + integrity + dry-run; 8 topics recall with their decisions |
| 7 · Docs (architecture · submission · demo · hardening · this) | ✅ | — | ✅ | ✅ | `docs/` |
| — · CI + lint + robustness | ✅ | ✅ | ✅ | ✅ | `ci.yml`, ruff clean, `HARDENING.md`, `verify_all --no-live` |

**One-command gate:** `python scripts/verify_all.py` → 15/15 live green; `--no-live` → 10/10 hermetic
green. `pytest` → 32 passed. `ruff check` + `ruff format --check` clean.

## Open items (honest)

**Human-loop (Code can't do headless):**
- Live Slack screenshots — the memory card rendering, the App Home tab, and the two button behaviors
  (`open thread`, `not relevant`) — need a person in Slack. Code validated the Block Kit is accepted
  and the handlers are registered; the *click* is bogac's.
- Cursor / Claude Desktop MCP screenshot — the stdio path is proven by `mcp_smoke`; the IDE call is bogac's.

**Product/scope (intentional, noted):**
- **Per-user OAuth** is the production auth story; the sandbox uses a single user token (permission-aware to that user). Documented in `architecture.md`.
- **Seed authorship** — seeded threads all post from one sandbox user; realistic multi-author history is a future polish (retrieval doesn't depend on it).
- **RTS indexing lag** — freshly posted messages take a short while to be searchable; seed ahead of a demo (noted in `DEMO.md`).
- **Trigger cost** — every channel message gets an LLM judgment; fine at demo volume. A cheap keyword pre-filter before the LLM is a possible optimization.

**Tooling (deliberate):**
- **mypy** not run — would add a dep and be noisy on scaffold/SDK stubs; `deja/` is already type-annotated.
- **CI** is committed but hasn't run on GitHub yet (it runs on the next push); it's the hermetic subset, verified locally with `--no-live`.

## Overall
All six product phases are working, tested, and documented; the only gaps are human-loop
screenshots (not code) and clearly-scoped production items. The `verify_all` gate makes the whole
thing provable in one command — the demo's safety net.
