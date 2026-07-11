# Déjà — Robustness Audit

Reviewed every `deja/` module for uncaught exceptions, missing timeouts, and silent-wrong failure
modes. Guiding principle: **fail safe = fail silent.** Déjà is non-disruptive, so on any error it
should go quiet (no crash, no channel spam), log a structured line, and never surface a stack trace
to a user or an MCP client.

## Findings & fixes

| Module | Gap found | Fix |
|---|---|---|
| `trigger.py` | The LLM call (`ClaudeSDKClient`) and `json.loads` of the model output were unguarded — an auth blip, transport error, or non-JSON reply would raise straight into the Slack handler. | `judge()` wraps the SDK call: **any failure → `TriggerDecision(should_recall=False)`** (Déjà simply doesn't trigger). `_parse()` guards `json.loads` → defaults to no-recall. Both log a `warning`. |
| `recall.py` | `WebClient` had no explicit timeout (could hang on a stalled RTS call); RTS failures raised without a log. | `WebClient(…, timeout=15)`; RTS `SlackApiError` is logged (`warning`) before being re-raised with the existing actionable message. |
| `memory.py` | `AsyncWebClient` had no timeout; the recall + enrichment failures were swallowed without a log. | `AsyncWebClient(…, timeout=15)`; recall failure logs a `warning` and returns a clean empty result; per-hit enrichment failure logs `debug` and keeps the memory without a decision. Already never raises to the MCP client. |
| `respond.py` | Enrichment failure in `recall_card` was swallowed silently (no log). | Logs `debug` on enrichment failure; card is still returned. (Judge/recall failures now fail-safe upstream in `trigger`/at the handler.) |
| `thread.py` | `pick_decision` / `is_thread_alive` are pure and already `.get()`-defensive; `fetch_thread_messages` errors propagate to callers that catch them. | No change needed — verified. |
| `card.py` | Pure builder; `_epoch` guards bad timestamps, `_author`/`_quote` handle any string. | No change needed — verified. |
| `mcp_server.py` | The tool delegates to `recall_memories`, which never raises. FastMCP owns transport errors. | No change needed — verified. |
| `listeners/events/*` | Already wrap handling in `try/except` and log (`logger.exception`); auto-trigger stays silent on error, `@mention` posts a friendly warning. | Confirmed — this is the outer safety net. |

## Layered safety net (defense in depth)
1. **`trigger.judge`** — LLM down ⇒ no-recall (silent), never crashes the handler.
2. **`recall` / `memory` / `respond`** — 15s timeouts; failures logged; the MCP path returns a clean
   empty result instead of raising.
3. **Slack listeners** — outer `try/except`: auto-trigger silent on error, `@mention` warns politely.

## Not changed (deliberate)
- No new dependencies (no retry/backoff library) — a single 15s timeout + fail-silent is right for a
  non-disruptive agent; retries would risk duplicate work and add a dep.
- No global exception handler swallowing — errors are handled where the context makes the safe
  behavior obvious (silence vs. warn), and logged so they're diagnosable.
