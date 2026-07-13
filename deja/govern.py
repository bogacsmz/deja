"""Décision governance — the second consumer of the same engine.

`recall_memory` (MCP) answers "what did the team decide about X?". `check_decision` turns that into a
GOVERNANCE VERDICT on a proposal: may an agent (or a human) proceed, or does the proposal conflict
with a standing decision? Same engine — recall the arc, then run the existing conflict detector — but
the output is a verdict an agent can gate on.

Sourceless verdict = 0 (a hard safety rule): CONFLICTS/INCONCLUSIVE are only returned with clickable
sources behind them; when the grounding gate can't confirm a real, on-topic, sourced decision, the
verdict is INCONCLUSIVE — Déjà never invents a brake. A fabricated brake is worse than no brake.
"""

from __future__ import annotations

import re

from deja.arc import _REVERSAL_CUES, _STOP
from deja.conflict import _REJECTION

ALLOW = "ALLOW"
CONFLICTS = "CONFLICTS"
INCONCLUSIVE = "INCONCLUSIVE"

# The rejection vocabulary must match what build_arc's state machine uses to mark a decision
# "reversed" — otherwise a decision the arc calls a reversal ("stepped away from X") wouldn't be seen
# as a rejection here, and every proposal against it would wrongly ALLOW. Union the two lists.
_REJECTION_ALL = tuple(set(_REJECTION) | set(_REVERSAL_CUES))

# A standing decision that rejects one option usually names the KEPT one in a trailing clause
# ("…back to seat-based with a usage add-on", "…staying on Redis"). A proposal CONFLICTS only when it
# re-proposes the REJECTED subject — not when it restates the kept one. This split is what tells
# "migrate to Temporal" (rejected → CONFLICTS) from "add a usage add-on" (kept → ALLOW), without a
# false alarm and without rewriting the conflict engine.
_KEEP_CUES = (
    "back to",
    "staying on",
    "sticking with",
    "going with",
    "in favor of",
    "we keep",
    "we kept",
    "keeping",
    "kept",
    "instead we",
    "switched to",
    "moved to",
)
_TOK = re.compile(r"[a-z0-9][a-z0-9-]{2,}")
# End the kept clause at the first clause boundary so a rejected alternative mentioned *after* it
# ("staying on Postgres, though we discussed CockroachDB") doesn't get misfiled as kept.
_CLAUSE_END = re.compile(r"[.,;:—–]|\b(?:though|but|however|while|whereas)\b")


def _terms(text: str) -> set[str]:
    return {w for w in _TOK.findall((text or "").lower())} - _STOP


def _conflicts(proposal: str, standing_decision: str) -> bool:
    """True when the proposal re-proposes the subject the decision REJECTED (not the one it kept)."""
    sd = (standing_decision or "").lower()
    if not any(r in sd for r in _REJECTION_ALL):
        return False  # the decision doesn't reject anything → a proposal can't contradict it
    kept_at = [sd.rfind(c) + len(c) for c in _KEEP_CUES if c in sd]
    kept = sd[max(kept_at) :] if kept_at else ""
    if kept:
        boundary = _CLAUSE_END.search(kept)
        if boundary:
            kept = kept[: boundary.start()]
    rejected = sd.replace(kept, " ") if kept else sd
    p, kt, rt = _terms(proposal), _terms(kept), _terms(rejected)
    return bool(p & rt) and len(p & rt) > len(p & kt)


def _verdict(
    verdict: str,
    *,
    standing_decision: str = "",
    owner: str = "",
    decided_at: str = "",
    times_discussed: int = 0,
    sources: tuple[str, ...] | list[str] = (),
    rationale: str = "",
) -> dict:
    return {
        "verdict": verdict,
        "standing_decision": standing_decision,
        "owner": owner,
        "decided_at": decided_at,
        "times_discussed": times_discussed,
        "sources": list(sources),
        "rationale": rationale,
    }


async def check_decision(
    proposal: str,
    *,
    recall_fn=None,
    thread_fn=None,
    expand: bool = False,
) -> dict:
    """Return a governance verdict on `proposal` against the team's standing decisions.

    ALLOW      — no standing decision is contradicted (either none on record, or the proposal is
                 consistent with the one that is).
    CONFLICTS  — the proposal re-opens a decision the team already settled the other way; returned
                 ONLY with a real, on-topic, sourced standing decision behind it.
    INCONCLUSIVE — the topic was discussed but never resolved (or grounding can't confirm a decision);
                 Déjà won't invent one.

    Runs the SAME live path as the Slack card — judge(proposal) for the search query, then
    recall_arc (grounding gate, expand off), then the existing conflict detector. `recall_fn`/
    `thread_fn` inject retrieval for the governance benchmark; live uses RTS.
    """
    from deja.arc import recall_arc
    from deja.trigger import judge

    proposal = (proposal or "").strip()
    if not proposal:
        return _verdict(INCONCLUSIVE, rationale="No proposal provided.")

    # Same judge as the live path — and the SAME should_recall gate the ambient card uses, so the
    # verdict is never more permissive than the human path. If the input isn't a decision/proposal
    # ("anyone up for coffee before standup?", "let's grab lunch after the deploy"), there is nothing
    # to govern → ALLOW. Word overlap with a decision's subject is not, by itself, a proposal to
    # re-open it; a brake that fires on chit-chat is the most expensive error we can make.
    decision = await judge(proposal)
    if not decision.should_recall or not decision.query:
        return _verdict(
            ALLOW, rationale="Not a decision or proposal — nothing to govern."
        )
    query = decision.query

    arc = await recall_arc(
        query, recall_fn=recall_fn, thread_fn=thread_fn, expand=expand
    )

    if arc is None:
        return _verdict(
            ALLOW,
            rationale="No prior decision found on this topic — nothing to conflict with.",
        )

    if arc.inconclusive:
        return _verdict(
            INCONCLUSIVE,
            times_discussed=arc.times_discussed,
            sources=arc.sources,
            rationale=(
                f"Discussed {arc.times_discussed}× but no clear decision was recorded — "
                "I won't invent one."
            ),
        )

    # Settled decision on record. CONFLICTS only when the proposal re-proposes the subject the team
    # REJECTED (not the one it kept) — so "migrate to Temporal" conflicts with the rollback, but
    # "add a usage add-on" is consistent with "reverted usage-based, kept a usage add-on" → ALLOW.
    common = dict(
        standing_decision=arc.standing_decision,
        owner=arc.owner,
        decided_at=arc.decided_at,
        times_discussed=arc.times_discussed,
        sources=arc.sources,
    )
    if _conflicts(proposal, arc.standing_decision):
        if (
            not arc.sources
        ):  # sourceless verdict = 0: a conflict we can't link is only INCONCLUSIVE
            return _verdict(
                INCONCLUSIVE,
                standing_decision=arc.standing_decision,
                owner=arc.owner,
                decided_at=arc.decided_at,
                times_discussed=arc.times_discussed,
                rationale="A conflict looks likely but I can't attach a source — I won't claim it.",
            )
        return _verdict(
            CONFLICTS,
            rationale="The proposal re-opens a decision the team already settled the other way.",
            **common,
        )
    return _verdict(
        ALLOW,
        rationale="Consistent with the standing decision on record — no conflict.",
        **common,
    )
