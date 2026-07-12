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
from deja.owner import resolve_owner_id
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
    text: str,
    client,
    *,
    limit: int = 3,
    exclude_ts: str | None = None,
    on_status=None,
    is_agent: bool = False,
    recall_fn=None,
    thread_fn=None,
) -> dict | None:
    """Full pipeline: judge -> reconstruct the decision ARC -> build the Block Kit card.

    Returns {"blocks": [...], "text": fallback} or None when there's nothing worth surfacing.

    Two consumers of the same engine:
    - Human (is_agent=False): the ambient memory card — surfaces a standing decision or recurring
      discussion; silent otherwise.
    - Agent (is_agent=True, Mode B): a GOVERNANCE brake — posts ONLY when the proposal CONFLICTS with a
      standing decision (⚠️ header) or the topic is inconclusive-but-recurring. ALLOW stays silent
      (rule: a channel-clean guardrail — nothing to post means nothing posted).

    `on_status(str)` (optional async) emits progress lines for an agent-design status indicator."""
    from deja.govern import _conflicts

    async def _status(msg: str) -> None:
        if on_status:
            await on_status(msg)

    decision = await judge(text)
    # The should_recall gate applies to BOTH consumers — the agent path must NEVER be more permissive
    # than the human one. Word overlap with a decision's subject is not, by itself, a proposal to
    # re-open it: "anyone up for coffee before standup?" hits the async-standup decision lexically but
    # is not a proposal, so the judge says should_recall=False → stay silent. Grounding + the conflict
    # test are a second line of defense, not the first.
    if not decision.should_recall or not decision.query:
        return None
    query = decision.query

    # expand=False: the live card stays fast + light on the rate-limited RTS (no LLM in the hot path).
    try:
        arc = await recall_arc(
            query,
            exclude_ts=exclude_ts,
            expand=False,
            recall_fn=recall_fn,
            thread_fn=thread_fn,
        )
    except RateLimitedError:
        return RATE_LIMITED  # tell the user to retry, don't fail silently
    if arc is None or (arc.inconclusive and not arc.is_recurring):
        return None  # nothing found, or a single unresolved proposal — stay quiet

    # Mode B guardrail: only speak up on a genuine CONFLICT (or an inconclusive-recurring topic).
    # A settled decision the proposal is CONSISTENT with is an ALLOW → stay silent, don't clutter.
    agent_conflict = False
    if is_agent and not arc.inconclusive:
        agent_conflict = _conflicts(text, arc.standing_decision)
        if not agent_conflict:
            return None

    await _status(
        f":books: _Found {arc.times_discussed} related thread(s) — reconstructing…_"
    )
    owner_uid = ""
    if not arc.inconclusive and arc.owner:
        owner_uid = await resolve_owner_id(client, arc.owner)
    warning = detect_conflict(text, arc)
    blocks, fallback = build_arc_card(
        query, arc, warning, owner_uid=owner_uid, agent_conflict=agent_conflict
    )
    return {"blocks": blocks, "text": fallback}
