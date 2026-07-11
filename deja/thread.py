"""Fetch 'what happened next' — the decision/outcome inside a recalled thread.

RTS surfaces a thread by its parent (the question). The value is the conclusion, which lives in
the replies, so we pull `conversations.replies` and pick the reply that best reads like a decision.
We also expose an aliveness check: RTS can lag on deletions, so a hit whose parent is a tombstone
is a stale ghost to be dropped.
"""
from __future__ import annotations

import re

from deja.recall import _is_deja_card

_MARKER = re.compile(r"\s*‹deja-seed:[^›]*›")
_DECISION_HINTS = (
    "roll back", "rolled back", "rolling back", "reverted", "decided", "went with",
    "sticking with", "instead", "in the end", "chose", "final", "won't", "abandon",
    "not worth", "postpone", "shelved", "conclusion", "we'll keep", "keeping",
)


def _clean(text: str) -> str:
    return _MARKER.sub("", text or "").strip().replace("\n", " ")


def is_thread_alive(messages: list[dict]) -> bool:
    """False if the thread's parent was deleted (a tombstone RTS may still be indexing)."""
    parent = messages[0] if messages else None
    if not parent or parent.get("subtype") == "tombstone":
        return False
    return "This message was deleted" not in (parent.get("text") or "")


def pick_decision(messages: list[dict]) -> tuple[str, str] | None:
    """From a thread's messages, return (decision_text, author_user_id) — the reply that best
    reads like the outcome — or None. Skips Déjà's own cards/replies."""
    replies = [
        m for m in messages[1:]  # skip the parent
        if not m.get("subtype")
        and (m.get("text") or "").strip()
        and not _is_deja_card(m.get("text") or "")
    ]
    if not replies:
        return None

    def decision_score(m: dict) -> int:
        t = (m.get("text") or "").lower()
        return sum(hint in t for hint in _DECISION_HINTS)

    best = max(replies, key=decision_score)
    if decision_score(best) == 0:
        best = replies[-1]  # no clear decision cue -> the latest reply is the freshest state

    text = _clean(best.get("text", ""))
    if len(text) > 240:
        text = text[:240] + "…"
    return text, best.get("user", "")


async def fetch_thread_messages(client, channel_id: str, ts: str) -> list[dict]:
    """Fetch a thread's messages. If `ts` is a reply, resolve to the thread root first.

    RTS can return a reply (not the parent) as a hit, and `conversations.replies` on a reply's ts
    returns only that reply. The reply carries `thread_ts` (the root), so we re-fetch from it — that
    way reply-level hits still get the full thread (parent + decision)."""
    resp = await client.conversations_replies(channel=channel_id, ts=ts, limit=50)
    msgs = resp.get("messages", [])
    if msgs:
        first = msgs[0]
        root = first.get("thread_ts") or first.get("ts")
        if root and root != first.get("ts"):  # `ts` was a reply — re-fetch from the thread root
            resp = await client.conversations_replies(channel=channel_id, ts=root, limit=50)
            msgs = resp.get("messages", [])
    return msgs


async def fetch_decision(client, channel_id: str, thread_ts: str) -> tuple[str, str] | None:
    """Convenience: fetch the thread and pick its decision. Best-effort — errors yield None."""
    if not channel_id or not thread_ts:
        return None
    return pick_decision(await fetch_thread_messages(client, channel_id, thread_ts))
