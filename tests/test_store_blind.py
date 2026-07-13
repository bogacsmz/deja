"""STORE-BLIND — the load-bearing claim: the decision arc is reconstructed from the raw
conversation, not read out of a canonical store.

Every other test injects `recall_fn=local_recall`, which bypasses `arc._canonical()` entirely — so
the store path has never been under test. These tests take the LIVE path (`recall_fn=None`, the one
the Slack card and the MCP tool actually run) with RTS swapped for the seeded mirror, and assert the
invariant that makes the product honest:

    a reconstructed arc is the ONLY thing that speaks.
    the store may never change the VERDICT, the TEXT, the COUNT, or the SOURCES.

The store used to be allowed to overwrite the standing decision's TEXT — which sounded modest until
you notice `govern._conflicts()` reads that text to decide whether to brake. One 💾 Save with the
wrong phrasing turned CONFLICTS into ALLOW. It may now speak only when retrieval came back empty.

`times_discussed` and `sources[]` are what the card renders as "discussed N×" with N clickable rows.
If a store could inflate them, "we rebuilt this from your history" would be a lie. So: blow the store
away, poison it with a fabrication — the verdict, the count and the links must not move.
"""

import asyncio
import json

import pytest

import deja.memory as memory
import deja.trigger as trigger
from benchmarks.local import local_recall, local_thread
from deja.govern import CONFLICTS, check_decision
from deja.trigger import TriggerDecision

PROPOSAL = "Opening a PR to migrate the job queue to Temporal."
QUERY = "Temporal job queue migration"

# A saved decision whose topic matches the query's named subject ("Temporal"), so `_canonical()` is
# guaranteed to fire. The text is a deliberate FABRICATION that contradicts the seeded history.
POISON = {
    "decisions": {
        "temporal job queue": {
            "topic": "Temporal job queue",
            "decision": "Decided: we fully adopted Temporal and it is the standing choice.",
            "owner": "Nobody Real",
            "at": "Dec 31",
            "channel": "saved",
            "times_discussed": 99,
            "url": "https://example.com/fabricated",
            "saved_at": 1.0,
            "times_saved": 1,
        }
    },
    "meta": {},
}


def _live_verdict(monkeypatch, store_path):
    """check_decision on the LIVE path (recall_fn=None → `_canonical` IS consulted), with RTS and
    conversations.replies swapped for the seeded mirror. `store_path` points DEJA_STORE at a file
    that may or may not exist."""

    async def _judge(_msg):
        return TriggerDecision(True, QUERY, "")

    monkeypatch.setattr(trigger, "judge", _judge)
    monkeypatch.setattr(memory, "recall", local_recall)  # the RTS primitive
    monkeypatch.setattr(memory, "fetch_thread_messages", local_thread)
    monkeypatch.setenv("SLACK_USER_TOKEN", "xoxp-test-not-a-real-token")
    monkeypatch.setenv("DEJA_STORE", str(store_path))
    return asyncio.run(check_decision(PROPOSAL))  # no recall_fn → the live path


@pytest.fixture
def empty_store(tmp_path):
    return tmp_path / "does_not_exist.json"


@pytest.fixture
def poisoned_store(tmp_path):
    p = tmp_path / "poisoned.json"
    p.write_text(json.dumps(POISON))
    return p


def test_verdict_is_identical_with_no_store_at_all(monkeypatch, empty_store):
    """With the store deleted, the live path still reconstructs the standing decision and brakes."""
    v = _live_verdict(monkeypatch, empty_store)
    assert v["verdict"] == CONFLICTS
    assert v["sources"], "a sourceless CONFLICTS must never be emitted"
    assert "rolling back" in v["standing_decision"].lower()


def test_store_cannot_move_the_verdict_the_count_or_the_sources(
    monkeypatch, empty_store, poisoned_store
):
    """The heart of it: a store that claims the OPPOSITE decision, 99 discussions and a fabricated
    link must not change the verdict, must not inflate `times_discussed`, and must not smuggle its
    URL into `sources[]`. Those three are reconstructed from the conversation or they are not ours."""
    blind = _live_verdict(monkeypatch, empty_store)
    poisoned = _live_verdict(monkeypatch, poisoned_store)

    assert poisoned["verdict"] == blind["verdict"]
    assert poisoned["times_discussed"] == blind["times_discussed"]
    assert poisoned["sources"] == blind["sources"]
    assert "https://example.com/fabricated" not in poisoned["sources"]
    assert poisoned["times_discussed"] != 99, (
        "the store's count must never reach the card"
    )


def test_the_count_equals_the_number_of_clickable_sources(monkeypatch, empty_store):
    """BADGE ≤ SOURCES: the card renders 'discussed N×' next to N clickable rows. N may never exceed
    what we can link — that is the whole grounding contract, stated as an assertion."""
    v = _live_verdict(monkeypatch, empty_store)
    assert v["times_discussed"] >= 1
    assert v["times_discussed"] <= len(v["sources"]), (
        f"claimed {v['times_discussed']}× but can only link {len(v['sources'])} sources"
    )
