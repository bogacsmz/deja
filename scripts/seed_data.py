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


# The original Phase-2 thread is preserved verbatim (same channel + marker) so re-seeding an
# already-seeded workspace does not duplicate it.
_TEMPORAL = SeedThread(
    channel="eng",
    marker="‹deja-seed:eng-temporal-v1›",
    topic="Temporal job-queue migration",
    parent=(
        "Kicking off the migration from our Redis-based job queue to Temporal next sprint — the "
        "durability + retries story is much nicer. Any objections?"
    ),
    replies=(
        "+1, the Temporal UI for debugging stuck workflows alone is worth it.",
        "Update after 3 weeks: we're ROLLING BACK the Temporal migration. Two blockers — (1) "
        "duplicate task execution under a network partition, and (2) the operational overhead of "
        "running the Temporal cluster isn't worth it at our scale. Sticking with Redis + a thin "
        "idempotency wrapper.",
        "Noted. Documenting the decision so nobody relitigates the Temporal move in six months.",
    ),
)

SEEDS: tuple[SeedThread, ...] = (
    _TEMPORAL,
    SeedThread(
        channel="eng",
        marker="‹deja-seed:eng-db-postgres-v1›",
        topic="Primary datastore: Postgres vs MongoDB",
        parent=(
            "Proposing we standardize the primary datastore on MongoDB — the flexible schema will "
            "let us move faster on the new features. Thoughts before I write the ADR?"
        ),
        replies=(
            "My worry is transactions across collections — a lot of our flows need multi-row "
            "consistency.",
            "Decision: we're going with Postgres, not Mongo. JSONB gives us the schema flexibility "
            "we wanted, and we keep real transactions + mature tooling. Mongo stays out of the core "
            "stack.",
            "Agreed. ADR-014 written up: Postgres is the system of record.",
        ),
    ),
    SeedThread(
        channel="eng",
        marker="‹deja-seed:eng-monorepo-v1›",
        topic="Repo layout: monorepo vs polyrepo",
        parent=(
            "The polyrepo setup is getting painful — shared types drift and cross-repo PRs are a "
            "nightmare. Should we consolidate into a monorepo?"
        ),
        replies=(
            "Big +1. Version skew between the web and api repos cost us two incidents last month.",
            "Outcome: we consolidated everything into a single monorepo with Turborepo for task "
            "caching. Shared packages now live in packages/*. Migration done, CI is green.",
        ),
    ),
    SeedThread(
        channel="ops",
        marker="‹deja-seed:ops-managed-k8s-v1›",
        topic="Self-hosted Kubernetes vs managed containers",
        parent=(
            "For the new services, do we stand up our own Kubernetes cluster or use a managed "
            "container platform? Leaning k8s for the flexibility."
        ),
        replies=(
            "We're a small team — who babysits the control plane at 3am?",
            "Decided: managed containers (ECS Fargate), not self-hosted k8s. We revisit only if we "
            "outgrow it. The ops overhead of running our own cluster isn't justified at our size.",
            "Runbook updated. No one has to become a full-time k8s admin. 🎉",
        ),
    ),
    SeedThread(
        channel="product",
        marker="‹deja-seed:product-pricing-v1›",
        topic="Pricing model: usage-based vs seat-based",
        parent=(
            "Should we switch our pricing from seat-based to pure usage-based billing? Usage-based "
            "feels more modern and aligned with value."
        ),
        replies=(
            "Sales is nervous about unpredictable bills scaring off procurement.",
            "Update: we TRIED usage-based for a quarter and REVERTED. Customers hated the "
            "unpredictable invoices and churn ticked up. We're back to seat-based with a usage "
            "add-on for overages — predictable base, upside on heavy users.",
        ),
    ),
    SeedThread(
        channel="product",
        marker="‹deja-seed:product-auth-v1›",
        topic="Auth: build in-house vs buy",
        parent=(
            "Do we build our own auth (sessions, SSO, MFA) or buy a provider? Building it keeps us "
            "flexible and avoids per-MAU fees."
        ),
        replies=(
            "Auth is a security minefield — SAML edge cases alone will eat weeks.",
            "Decision: we're BUYING auth (Auth0) rather than building in-house. Not worth owning "
            "the security surface pre-scale. We'll re-evaluate bringing it in-house if per-MAU cost "
            "becomes a real line item.",
        ),
    ),
    SeedThread(
        channel="design",
        marker="‹deja-seed:design-tailwind-v1›",
        topic="Styling: component library vs utility CSS",
        parent=(
            "Our UI is a mix of MUI and hand-rolled CSS and it's inconsistent. Should we go all-in "
            "on a component library like MUI to unify it?"
        ),
        replies=(
            "MUI's theming fought us every time we needed something custom.",
            "Decided: we're standardizing on Tailwind + Radix primitives and DROPPING MUI. Utility "
            "CSS + headless primitives gave us consistency without the theming fights. Design tokens "
            "live in the Tailwind config now.",
        ),
    ),
    SeedThread(
        channel="general",
        marker="‹deja-seed:general-async-standup-v1›",
        topic="Daily standup: sync meeting vs async",
        parent=(
            "The 10am daily standup keeps getting derailed and eats focus time across timezones. "
            "Should we keep the sync meeting?"
        ),
        replies=(
            "Half the team is heads-down by then anyway and just repeats their Jira board.",
            "Outcome: we KILLED the sync standup and moved to an ASYNC thread — everyone posts "
            "yesterday/today/blockers by 11am local, and we only jump on a call when a blocker "
            "actually needs it. Focus time went up, no one misplaced context.",
        ),
    ),
)
