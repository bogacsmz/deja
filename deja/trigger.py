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
import re
from dataclasses import dataclass

from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    ClaudeSDKClient,
    TextBlock,
)

_SYSTEM = """You are Déjà's trigger gate inside Slack. Given ONE message, decide whether it is a
decision, claim, proposal, or substantive question that a team might have discussed or tried
before — i.e. worth surfacing the past thread. Greetings, small talk, logistics, thanks, and
acknowledgements are NOT worth recalling.

Respond with ONLY a JSON object and nothing else:
{"should_recall": true|false, "query": "<short keyword search query, or empty>", "reason": "<one short phrase>"}
The query is the few keywords you would search past messages for (topic + key nouns)."""


@dataclass(frozen=True)
class TriggerDecision:
    should_recall: bool
    query: str
    reason: str


def _parse(text: str) -> TriggerDecision:
    match = re.search(r"\{.*\}", text, re.S)
    data = json.loads(match.group(0)) if match else {}
    return TriggerDecision(
        should_recall=bool(data.get("should_recall", False)),
        query=str(data.get("query") or "").strip(),
        reason=str(data.get("reason") or "").strip(),
    )


async def judge(message: str) -> TriggerDecision:
    """Return Déjà's judgment on whether `message` warrants a recall (+ a search query)."""
    options = ClaudeAgentOptions(
        system_prompt=_SYSTEM,
        permission_mode="bypassPermissions",
        allowed_tools=[],  # pure judgment, no tools
    )
    text = ""
    async with ClaudeSDKClient(options) as client:
        await client.query(message)
        async for msg in client.receive_response():
            if isinstance(msg, AssistantMessage):
                for block in msg.content:
                    if isinstance(block, TextBlock):
                        text += block.text
    return _parse(text)
