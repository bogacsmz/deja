"""Hermetic tests for the governance layer (deja.govern.check_decision) over the local mirror.

The judge (LLM) is monkeypatched to a fixed keyword query so the test is deterministic and offline;
retrieval uses the seeded local mirror. Verifies the three verdicts AND the hard safety rule: every
CONFLICTS / INCONCLUSIVE is backed by clickable sources (sourceless verdict = 0)."""

import asyncio

import deja.trigger as trigger
from benchmarks.local import local_recall, local_thread
from deja.govern import ALLOW, CONFLICTS, INCONCLUSIVE, _conflicts, check_decision
from deja.trigger import TriggerDecision


def _verdict(proposal, query, monkeypatch):
    async def _judge(msg):
        return TriggerDecision(True, query, "")

    monkeypatch.setattr(trigger, "judge", _judge)
    return asyncio.run(
        check_decision(proposal, recall_fn=local_recall, thread_fn=local_thread)
    )


def test_conflicts_re_proposes_a_rolled_back_decision(monkeypatch):
    v = _verdict(
        "Opening a PR to migrate the job queue to Temporal.",
        "Temporal job queue migration",
        monkeypatch,
    )
    assert v["verdict"] == CONFLICTS
    assert v["sources"], "a CONFLICTS verdict MUST be sourced"
    assert "rolling back" in v["standing_decision"].lower()


def test_allow_when_proposal_matches_the_kept_option(monkeypatch):
    # The team reverted usage-BASED pricing but KEPT a usage add-on — proposing the add-on is fine.
    v = _verdict(
        "Proposing we add a usage add-on for heavy accounts.",
        "usage-based pricing seat",
        monkeypatch,
    )
    assert v["verdict"] == ALLOW


def test_inconclusive_when_discussed_but_undecided(monkeypatch):
    v = _verdict(
        "Should we adopt an RFC process for big decisions?",
        "RFC design-doc process",
        monkeypatch,
    )
    assert v["verdict"] == INCONCLUSIVE
    assert v["sources"], "even INCONCLUSIVE is backed by the discussion's sources"
    assert not v["standing_decision"]  # never invents a decision


def test_allow_when_nothing_on_record(monkeypatch):
    v = _verdict("should we adopt GraphQL for the API?", "GraphQL API", monkeypatch)
    assert v["verdict"] == ALLOW
    assert v["sources"] == []


def test_conflict_split_kept_vs_rejected():
    # re-proposing the rejected subject conflicts; restating the kept one does not
    assert _conflicts("migrate to Temporal", "rolling back the Temporal migration, staying on Redis")
    assert not _conflicts(
        "add a usage add-on", "reverted usage-based, back to seat-based with a usage add-on"
    )
    assert not _conflicts("migrate to Temporal", "we're going with continuous deploy")  # no rejection


def test_conflict_edge_cases_from_review():
    # bare "kept" past tense must also mark the kept clause (was a false CONFLICTS)
    assert not _conflicts("add a usage add-on", "reverted usage-based, kept a usage add-on")
    # 'stepped away' is a reversal the arc recognizes — the conflict gate must too (was a false ALLOW)
    assert _conflicts("let's adopt Kubernetes again", "we stepped away from Kubernetes for now")
    # a rejected alternative named AFTER the keep cue must not be misfiled as kept (was a false ALLOW)
    assert _conflicts(
        "let's migrate to CockroachDB",
        "we are staying on Postgres for now, though we dropped CockroachDB",
    )
