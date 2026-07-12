#!/usr/bin/env python3
"""Phase 6 — realistic workspace seed data for Déjà.

A small but believable team memory: several *forgotten decisions* spread across the channels a
real product team would use. Each thread is a proposal/question (the parent) followed by the
discussion and — crucially — one reply that records the DECISION or OUTCOME ("what happened
next"). That decision reply is what `recall_memory` resurfaces months later when someone asks
the same question again.

Design rules (kept deliberately simple so the seeder and tests stay hermetic):
  * Each `SeedThread` targets exactly one channel and carries a unique idempotency `marker`.
  * The marker is appended to the parent text; the seeder skips a thread if its marker is
    already present in the channel history, so re-running is safe and additive.
  * Every thread has at least one reply whose text reads like a concrete decision/outcome
    (rolled back / going with / decided / reverted / chose …). `test_seed_data.py` enforces this.

This module holds DATA only — no Slack calls. `scripts/seed_deja.py` consumes it.
"""

from __future__ import annotations

from dataclasses import dataclass

# Words/phrases that mark a reply as the concrete decision or outcome of a thread — this is the
# "what happened next" signal recall surfaces. Used by the seeder summary and enforced by tests.
DECISION_MARKERS: tuple[str, ...] = (
    "decision:",
    "decided",
    "outcome:",
    "update:",
    "update after",
    "rolling back",
    "rolled back",
    "reverted",
    "we're going with",
    "going with",
    "we're buying",
    "we killed",
    "killed the",
    "dropping",
    "standardizing on",
    "we tried",
    "we reverted",
    "consolidated",
)


def is_decision(text: str) -> bool:
    """True if a reply reads like a concrete decision/outcome (not just discussion)."""
    low = text.lower()
    return any(m in low for m in DECISION_MARKERS)


@dataclass(frozen=True)
class SeedThread:
    channel: str  # channel name without leading '#'
    marker: str  # unique hidden idempotency marker, appended to the parent
    parent: str  # the opening proposal / question
    replies: tuple[str, ...]  # discussion; at least one is the decision/outcome
    topic: str  # short human label for summaries/logs

    def has_decision(self) -> bool:
        return any(is_decision(r) for r in self.replies)


# All seeded decisions now live in scripts/seed_arcs.py as back-dated, persona-attributed threads
# (posted with the BOT token + chat:write.customize), so no decision is ever owned by the raw
# sandbox account. This raw-user single seeder is therefore empty — kept only for its schema +
# `is_decision` helper, which seed_arcs' tests and the benchmark mirror still import.
SEEDS: tuple[SeedThread, ...] = ()
