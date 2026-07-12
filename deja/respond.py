"""Déjà end-to-end pipeline — Phase 3.

`recall_reply(text)` chains the trigger judgment and the retrieval primitive:
  judge(text) -> if it's a decision/claim worth recalling -> recall(query) -> format a reply.

Returns a plain-text Slack message (permalink to the surfaced thread) or None when there is
nothing worth saying — Déjà stays silent unless it actually found the past thread. Block Kit
formatting is Phase 4; this is deliberately plain text.
"""

from __future__ import annotations

import asyncio
import logging
import re

from deja.arc import recall_arc
from deja.card import build_arc_card
from deja.conflict import detect_conflict
from deja.recall import RateLimitedError, recall
from deja.trigger import judge

# Sentinel recall_card returns when Slack's search is throttling us — so the caller can say so out
# loud instead of going silent (silence reads as 'broken', especially to someone testing fast).
RATE_LIMITED = {"rate_limited": True}

_log = logging.getLogger(__name__)
_SEED_MARKER = re.compile(r"\s*‹deja-seed:[^›]*›")


async def recall_reply(
    text: str, *, limit: int = 3, exclude_ts: str | None = None
) -> str | None:
    decision = await judge(text)
    if not decision.should_recall or not decision.query:
        return None

    # recall() is sync (Slack WebClient) — run it off the event loop.
    hits = await asyncio.to_thread(
        recall, decision.query, limit=limit, exclude_ts=exclude_ts
    )
    if not hits:
        return None

    top = hits[0]
    snippet = _SEED_MARKER.sub("", top.snippet).strip().replace("\n", " ")
    if len(snippet) > 160:
        snippet = snippet[:160] + "…"
    return (
        ":hourglass_flowing_sand: *Déjà vu* — your team already touched on this "
        f"(I searched _{decision.query}_):\n"
        f"• <{top.permalink}|#{top.channel}>: “{snippet}”"
    )


async def recall_card(
    text: str, client, *, limit: int = 3, exclude_ts: str | None = None, on_status=None
) -> dict | None:
    """Full pipeline: judge -> reconstruct the decision ARC -> build the Block Kit card.

    Returns {"blocks": [...], "text": fallback} or None when there's nothing worth surfacing.
    Déjà stays silent unless it found either a standing decision or a recurring discussion — a lone
    proposal with no outcome isn't worth interrupting for. `client` is accepted for signature
    compatibility (the arc engine fetches threads itself). `on_status(str)` (optional async) is
    called with progress lines for an agent-design status indicator."""

    async def _status(msg: str) -> None:
        if on_status:
            await on_status(msg)

    await _status(":mag: _Searching your workspace…_")
    decision = await judge(text)
    if not decision.should_recall or not decision.query:
        return None

    # expand=False: the live card stays fast + light on the rate-limited RTS (no LLM in the hot
    # path). Seeded/real topics retrieve directly; MCP + benchmark keep full expansion.
    try:
        arc = await recall_arc(decision.query, exclude_ts=exclude_ts, expand=False)
    except RateLimitedError:
        return RATE_LIMITED  # tell the user to retry, don't fail silently
    if arc is None or (arc.inconclusive and not arc.is_recurring):
        return None  # nothing found, or just a single unresolved proposal — stay quiet

    await _status(f":books: _Found {arc.times_discussed} related thread(s)…_")
    await _status(":jigsaw: _Reconstructing the decision…_")
    warning = detect_conflict(text, arc)
    blocks, fallback = build_arc_card(decision.query, arc, warning)
    return {"blocks": blocks, "text": fallback}
