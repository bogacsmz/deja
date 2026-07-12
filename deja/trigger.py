"""Déjà trigger judgment — Phase 3 (minimal primitive).

Given one Slack message, decide whether it is a decision / claim / proposal / substantive
question the team may have discussed or tried before — i.e. worth surfacing the past thread —
and if so produce a concise search query for `recall()`.

LLM auth: the Claude Agent SDK authenticates from the environment — a Claude Max/Pro
subscription via CLAUDE_CODE_OAUTH_TOKEN (from `claude setup-token`), or ANTHROPIC_API_KEY.
No API key is set in code; nothing here bills per token when the subscription token is used.

This is the Phase 3 seed: the judgment primitive + its own harness. Wiring it into the Slack
event handlers (auto-trigger on channel messages) is the rest of Phase 3.
"""

from __future__ import annotations

import json
import logging
import os
import pathlib
import re
from dataclasses import dataclass

from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    ClaudeSDKClient,
    TextBlock,
)

# Optional on-disk cache (DEJA_JUDGE_CACHE=<path>): judge each message once. The benchmark sets it so
# it runs the SAME judge step the live app does, reproducibly, without an LLM call per case in a loop.
_CACHE_PATH = (
    pathlib.Path(os.environ["DEJA_JUDGE_CACHE"])
    if os.environ.get("DEJA_JUDGE_CACHE")
    else None
)


def _load_cache() -> dict:
    if _CACHE_PATH and _CACHE_PATH.exists():
        try:
            return json.loads(_CACHE_PATH.read_text())
        except (ValueError, OSError):
            return {}
    return {}


_CACHE: dict = _load_cache()

_SYSTEM = """You are Déjà's trigger gate inside Slack. Given ONE message, decide whether it is a
decision, claim, proposal, or substantive question that a team might have discussed or tried
before — i.e. worth surfacing the past thread. Greetings, small talk, logistics, thanks, and
acknowledgements are NOT worth recalling.

Respond with ONLY a JSON object and nothing else:
{"should_recall": true|false, "query": "<short keyword search query, or empty>", "reason": "<one short phrase>"}
The query is the SEARCH TERMS for past messages — keep it to **2–3 core keywords**: the distinctive
topic/product/process name and its key noun (e.g. "Temporal job queue", "Datadog monitoring", "RFC
design-doc"). Do NOT pad it with generic words like "adoption", "process", "system", "approach", or
verbs — extra terms make the search miss. Prefer the distinctive name over the filler around it."""


@dataclass(frozen=True)
class TriggerDecision:
    should_recall: bool
    query: str
    reason: str


_log = logging.getLogger(__name__)

# Judge model: default to the SDK's default (best accuracy for the classification). Overridable via
# env if a smaller/faster alias is ever wanted — but measurement showed the win is in startup, not
# the model. Empty/unset -> None -> SDK default.
_JUDGE_MODEL = os.environ.get("DEJA_JUDGE_MODEL") or None


def _parse(text: str) -> TriggerDecision:
    try:
        match = re.search(r"\{.*\}", text, re.S)
        data = json.loads(match.group(0)) if match else {}
    except (ValueError, json.JSONDecodeError):
        _log.warning(
            "trigger: model output was not valid JSON; defaulting to no-recall"
        )
        data = {}
    return TriggerDecision(
        should_recall=bool(data.get("should_recall", False)),
        query=str(data.get("query") or "").strip(),
        reason=str(data.get("reason") or "").strip(),
    )


_OPTIONS = ClaudeAgentOptions(
    system_prompt=_SYSTEM,
    permission_mode="bypassPermissions",
    allowed_tools=[],  # pure judgment, no tools
    model=_JUDGE_MODEL,  # None -> the SDK default (measured: switching to Haiku barely moved the
    # needle since STARTUP, not inference, dominates — and it produced worse queries; not worth it)
    # Startup, not inference, dominated the judge latency: the CLI was loading the developer's whole
    # ~/.claude environment (many MCP servers + settings files) on every call. This is a zero-tool
    # classifier — load NONE of it (output-identical, ~1s faster). Auth still comes from the env token.
    mcp_servers={},
    strict_mcp_config=True,  # ignore the user's global MCP config, don't spawn those servers
    setting_sources=[],  # don't read settings.json / CLAUDE.md / project config
    max_turns=1,
)


async def judge(message: str) -> TriggerDecision:
    """Return Déjà's judgment on whether `message` warrants a recall (+ a search query)."""
    if message in _CACHE:
        c = _CACHE[message]
        return TriggerDecision(c["should_recall"], c["query"], c["reason"])
    text = ""
    try:
        async with ClaudeSDKClient(_OPTIONS) as client:
            await client.query(message)
            async for msg in client.receive_response():
                if isinstance(msg, AssistantMessage):
                    for block in msg.content:
                        if isinstance(block, TextBlock):
                            text += block.text
    except Exception as e:  # noqa: BLE001 — LLM/auth/transport failure -> fail safe, don't trigger
        _log.warning("trigger: judge unavailable (%s); defaulting to no-recall", e)
        return TriggerDecision(False, "", "judge unavailable")
    decision = _parse(text)
    if _CACHE_PATH:
        _CACHE[message] = {
            "should_recall": decision.should_recall,
            "query": decision.query,
            "reason": decision.reason,
        }
        try:
            _CACHE_PATH.write_text(json.dumps(_CACHE, ensure_ascii=False, indent=1))
        except OSError:
            pass
    return decision
