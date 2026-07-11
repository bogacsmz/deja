"""Déjà end-to-end pipeline — Phase 3.

`recall_reply(text)` chains the trigger judgment and the retrieval primitive:
  judge(text) -> if it's a decision/claim worth recalling -> recall(query) -> format a reply.

Returns a plain-text Slack message (permalink to the surfaced thread) or None when there is
nothing worth saying — Déjà stays silent unless it actually found the past thread. Block Kit
formatting is Phase 4; this is deliberately plain text.
"""
from __future__ import annotations

import asyncio
import re

from deja.card import build_memory_card
from deja.recall import recall
from deja.thread import fetch_decision
from deja.trigger import judge

_SEED_MARKER = re.compile(r"\s*‹deja-seed:[^›]*›")


async def recall_reply(text: str, *, limit: int = 3, exclude_ts: str | None = None) -> str | None:
    decision = await judge(text)
    if not decision.should_recall or not decision.query:
        return None

    # recall() is sync (Slack WebClient) — run it off the event loop.
    hits = await asyncio.to_thread(recall, decision.query, limit=limit, exclude_ts=exclude_ts)
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


async def recall_card(text: str, client, *, limit: int = 3, exclude_ts: str | None = None) -> dict | None:
    """Full Phase-4 pipeline: judge -> recall -> fetch the decision -> build the Block Kit card.

    Returns {"blocks": [...], "text": fallback} or None when there's nothing worth surfacing.
    `client` is a Slack (Async)WebClient used to fetch the thread's replies.
    """
    decision = await judge(text)
    if not decision.should_recall or not decision.query:
        return None

    hits = await asyncio.to_thread(recall, decision.query, limit=limit, exclude_ts=exclude_ts)
    if not hits:
        return None
    top = hits[0]

    outcome = None
    try:
        outcome = await fetch_decision(client, top.channel_id, top.ts)
    except Exception:  # enrichment is best-effort — a card without it is still useful
        outcome = None

    blocks, fallback = build_memory_card(decision.query, top, outcome)
    return {"blocks": blocks, "text": fallback}
