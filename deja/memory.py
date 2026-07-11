"""Déjà's memory as a structured lookup — the engine behind both the Slack card and the MCP tool.

`recall_memories(query)` reuses the RTS recall primitive + the conversations.replies enrichment
('what happened next') and returns a clean, LLM-friendly structured result. No LLM here — the
caller (a Slack event, or an external agent via MCP) decides *when* to ask and *what* to ask.
"""

from __future__ import annotations

import asyncio
import os
import re

from slack_sdk.web.async_client import AsyncWebClient

from deja.recall import recall
from deja.thread import fetch_thread_messages, is_thread_alive, pick_decision

_MARKER = re.compile(r"\s*‹deja-seed:[^›]*›")


def _clean(text: str) -> str:
    return _MARKER.sub("", text or "").strip()


def _result(summary: str, memories: list[dict], query: str) -> dict:
    return {"summary": summary, "memories": memories, "searched": query}


async def recall_memories(
    query: str, channel: str | None = None, limit: int = 3
) -> dict:
    """Return prior team discussions relevant to `query`, newest-decision included.

    Shape: {summary, memories:[{source_message, what_happened_next, channel, author, ts,
    permalink, score}], searched}. Never raises — errors become an empty result + a summary.
    """
    query = (query or "").strip()
    if not query:
        return _result("No query provided.", [], query)

    token = os.environ.get("SLACK_USER_TOKEN")
    if not token:
        return _result("Déjà is not configured (SLACK_USER_TOKEN missing).", [], query)

    try:
        hits = await asyncio.to_thread(recall, query, limit=max(limit, 5))
    except Exception as e:  # noqa: BLE001 — surface as a clean summary, never throw to the client
        return _result(f"Search failed: {e}", [], query)

    if channel:
        wanted = channel.lstrip("#").lower()
        hits = [h for h in hits if h.channel.lower() == wanted]
    hits = hits[:limit]

    if not hits:
        scope = f" in #{channel.lstrip('#')}" if channel else ""
        return _result(f"No prior discussion found{scope} for “{query}”.", [], query)

    client = AsyncWebClient(token=token)
    memories: list[dict] = []
    for h in hits:
        decision = ""
        try:
            msgs = await fetch_thread_messages(
                client, h.channel_id, h.ts
            )  # reply-aware
            if not is_thread_alive(msgs):
                continue  # stale ghost: RTS returned a message that has since been deleted
            found = pick_decision(msgs)
            decision = found[0] if found else ""
        except Exception:  # noqa: BLE001 — enrichment is best-effort; keep the memory without a decision
            decision = ""
        memories.append(
            {
                "source_message": _clean(h.snippet),
                "what_happened_next": decision,
                "channel": h.channel,
                "author": h.author,
                "ts": h.ts,
                "permalink": h.permalink,
                "score": h.score,
            }
        )

    if not memories:
        return _result(f"No live prior discussion found for “{query}”.", [], query)

    # A memory with a known outcome outranks a bare restatement of the question.
    memories.sort(key=lambda m: 0 if m["what_happened_next"] else 1)

    top = memories[0]
    outcome = top["what_happened_next"] or top["source_message"]
    plural = "discussion" if len(memories) == 1 else "discussions"
    summary = (
        f"Your team already had {len(memories)} relevant {plural} — most relevant in "
        f"#{top['channel']}: {outcome[:200]}"
    )
    return _result(summary, memories, query)
