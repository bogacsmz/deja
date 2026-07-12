"""Déjà's memory as a structured lookup — the engine behind both the Slack card and the MCP tool.

`recall_memories(query)` reuses the RTS recall primitive + the conversations.replies enrichment
('what happened next') and returns a clean, LLM-friendly structured result. No LLM here — the
caller (a Slack event, or an external agent via MCP) decides *when* to ask and *what* to ask.
"""

from __future__ import annotations

import asyncio
import logging
import os
import re

from slack_sdk.web.async_client import AsyncWebClient

from deja.recall import (
    RateLimitedError,
    _addressed_to_deja,
    _is_deja_card,
    recall,
)
from deja.thread import fetch_thread_messages, is_thread_alive, pick_decision

_log = logging.getLogger(__name__)
_MARKER = re.compile(r"\s*‹deja-[^›]*›")  # strip any Déjà seed marker (seed/arc/noise)
_USER_ID = re.compile(r"^[UW][A-Z0-9]{6,}$")  # a raw Slack user id, not a display name
_NAME_CACHE: dict[str, str] = {}


def _clean(text: str) -> str:
    return _MARKER.sub("", text or "").strip()


async def _resolve_name(client, author: str) -> str:
    """Turn a raw user id into a display name (cached). Non-ids (override usernames) pass through."""
    if not author or client is None or not _USER_ID.match(author):
        return author
    if author in _NAME_CACHE:
        return _NAME_CACHE[author]
    name = author
    try:
        prof = (await client.users_info(user=author))["user"]["profile"]
        name = prof.get("display_name") or prof.get("real_name") or author
    except Exception as e:  # noqa: BLE001 — best-effort; fall back to the id
        _log.debug("memory: users_info failed for %s: %s", author, e)
    _NAME_CACHE[author] = name
    return name


def _result(summary: str, memories: list[dict], query: str) -> dict:
    return {"summary": summary, "memories": memories, "searched": query}


async def recall_memories(
    query: str,
    channel: str | None = None,
    limit: int = 3,
    *,
    recall_fn=None,
    thread_fn=None,
) -> dict:
    """Return prior team discussions relevant to `query`, newest-decision included.

    Shape: {summary, memories:[{source_message, what_happened_next, channel, author, ts,
    permalink, score}], searched}. Never raises — errors become an empty result + a summary.

    `recall_fn`/`thread_fn` inject the retrieval + thread-fetch primitives (default: live RTS +
    conversations.replies). The benchmark passes local ones to run the same synthesis over a snapshot
    without hitting the RTS rate limit."""
    query = (query or "").strip()
    if not query:
        return _result("No query provided.", [], query)

    _recall = recall_fn or recall
    _thread = thread_fn or fetch_thread_messages

    token = os.environ.get("SLACK_USER_TOKEN")
    if recall_fn is None and not token:
        return _result("Déjà is not configured (SLACK_USER_TOKEN missing).", [], query)

    try:
        # Over-fetch: RTS returns individual messages, so one thread can appear multiple times
        # (its parent AND a reply both match). We dedupe by thread root below, then cap at `limit`.
        hits = await asyncio.to_thread(_recall, query, limit=max(limit * 3, 12))
    except RateLimitedError:
        raise  # let the caller show a 'try again in a minute' message, not silence
    except Exception as e:  # noqa: BLE001 — surface as a clean summary, never throw to the client
        _log.warning("memory: recall failed for %r: %s", query, e)
        return _result(f"Search failed: {e}", [], query)

    if channel:
        wanted = channel.lstrip("#").lower()
        hits = [h for h in hits if h.channel.lower() == wanted]

    if not hits:
        scope = f" in #{channel.lstrip('#')}" if channel else ""
        return _result(f"No prior discussion found{scope} for “{query}”.", [], query)

    client = AsyncWebClient(token=token, timeout=15) if token else None

    # Snippet-level guard first (cheap, no API): drop @Deja questions + Déjà's own cards up front.
    candidates = [
        h
        for h in hits
        if not (_addressed_to_deja(h.snippet) or _is_deja_card(h.snippet))
    ][: max(limit * 3, 12)]

    # Enrich every candidate's thread (conversations.replies) IN PARALLEL — this was the dominant
    # serial cost (N sequential ~250ms round-trips). We over-fetch candidates and cap memories at
    # `limit` after dedupe/filtering below, so a few extra parallel fetches are cheap.
    fetched = await asyncio.gather(
        *(_thread(client, h.channel_id, h.ts) for h in candidates),
        return_exceptions=True,
    )

    memories: list[dict] = []
    seen_roots: set[str] = set()
    for h, msgs in zip(candidates, fetched):
        if len(memories) >= limit:
            break
        decision, author, source, root_ts = "", h.author, _clean(h.snippet), h.ts
        if isinstance(msgs, BaseException):
            _log.debug("memory: enrichment failed for %s: %s", h.ts, msgs)
        elif not is_thread_alive(msgs):
            continue  # stale ghost: RTS returned a message that has since been deleted
        else:
            parent = msgs[0]
            parent_text = parent.get("text", "")
            # A question ADDRESSED to Déjà, or Déjà's own card, is not team discussion — drop it so
            # it never counts toward "discussed N×" (RTS may hand us these via a reply/card snippet
            # whose parent carries the @-mention).
            if _addressed_to_deja(parent_text) or _is_deja_card(parent_text):
                continue
            root_ts = parent.get("ts") or h.ts
            found = pick_decision(msgs, require_decision=True)
            decision = found[0] if found else ""
            # Author = the decider (decision reply) if any, else whoever opened the thread. RTS
            # can't see chat:write.customize usernames — the fetched thread messages can.
            parent_author = parent.get("username") or parent.get("user", "")
            author = (found[1] if found else "") or parent_author or h.author
            source = (
                _clean(parent.get("text", "")) or source
            )  # canonical = the thread's parent
        if root_ts in seen_roots:
            continue  # same thread reached via a second hit (parent + reply both matched)
        seen_roots.add(root_ts)
        memories.append(
            {
                "source_message": source,
                "what_happened_next": decision,
                "channel": h.channel,
                "author": await _resolve_name(client, author),  # id -> display name
                "ts": root_ts,
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
