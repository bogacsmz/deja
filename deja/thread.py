"""Fetch 'what happened next' — the decision/outcome inside a recalled thread.

RTS surfaces a thread by its parent (the question). The value is the conclusion, which lives in
the replies, so we pull `conversations.replies` and pick the reply that best reads like a decision.
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


async def fetch_decision(client, channel_id: str, thread_ts: str) -> tuple[str, str] | None:
    """Return (decision_text, author_user_id) — the reply that best reads like the outcome, or None.

    Best-effort enrichment: any error (not in channel, no replies) just yields None.
    """
    if not channel_id or not thread_ts:
        return None
    resp = await client.conversations_replies(channel=channel_id, ts=thread_ts, limit=50)
    replies = [
        m for m in resp.get("messages", [])[1:]  # skip the parent
        if not m.get("subtype")
        and (m.get("text") or "").strip()
        and not _is_deja_card(m.get("text") or "")  # skip Déjà's own cards, keep real discussion
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
