"""Hermetic regression tests for the Gate-6 live fixes (subject filter, truncation, self-pollution,
name resolution) — over the local mirror + pure functions, no live Slack."""

import asyncio
import sys

import pytest

import deja.recall  # noqa: F401 — ensures the module is registered in sys.modules
from benchmarks.local import local_recall, local_thread, loose_recall
from deja.arc import _grounded, recall_arc
from deja.memory import _resolve_name

# `deja.recall` the attribute is the re-exported recall() function, so reach the MODULE via sys.
recall_mod = sys.modules["deja.recall"]


def _arc(q):
    return asyncio.run(recall_arc(q, recall_fn=local_recall, thread_fn=local_thread))


def _loose(q):
    """Worst-case (permissive) retrieval — surfaces off-topic arcs so the grounding gate is tested."""
    return asyncio.run(
        recall_arc(q, recall_fn=loose_recall, thread_fn=local_thread, expand=False)
    )


@pytest.mark.parametrize(
    "query",
    [
        "did we decide to buy a boat",  # buy ↔ 'BUYING auth (Auth0)' — the live confident-wrong
        "did we drop the ball on the launch",  # drop/launch ↔ DROPPING Datadog / launch arc
        "are we migrating to Mars",  # migrate ↔ Temporal migration
        "did we roll back the party",  # roll back ↔ ROLLING BACK Temporal
        "should we stay in bed",  # stay ↔ STAYING IN private beta
    ],
)
def test_lexical_trap_stays_silent(query):
    """One word overlaps a real decision, but the SUBJECT is unrelated → must find nothing.
    Permissive retrieval deliberately surfaces the off-topic arc; the gate must reject it."""
    assert _loose(query) is None


def test_real_query_grounds_under_loose_recall():
    """The gate must NOT over-reject: a genuinely on-topic query still resolves under loose recall."""
    arc = _loose("did we build or buy auth")
    assert arc and not arc.inconclusive
    dec = arc.standing_decision.lower()
    assert "auth0" in dec or "buying" in dec


def test_grounded_needs_distinctive_subject_not_generic_verb():
    mem = [
        {
            "source_message": "Do we build our own auth or buy a provider?",
            "what_happened_next": "Decision: we're BUYING auth (Auth0).",
        }
    ]
    assert not _grounded(
        "buy a boat", mem
    )  # only 'boat' is distinctive, and it's absent
    assert _grounded("build or buy auth", mem)  # 'auth' is distinctive and present


def test_subject_filter_keeps_arc_on_topic():
    # 'migration' would pull the monorepo decision; the 'Temporal' subject must filter it out.
    arc = _arc("Temporal pipeline migration")
    assert arc and not arc.inconclusive
    assert "rolling back" in arc.standing_decision.lower()
    assert "monorepo" not in arc.standing_decision.lower()
    assert arc.owner == "Maya Chen"  # real name, not a raw user id


def test_standing_decision_not_over_truncated():
    arc = _arc("Temporal pipeline migration")
    assert len(arc.standing_decision) > 120  # full sentence, not the old 90-char cut


def test_addressed_to_deja_is_filtered(monkeypatch):
    monkeypatch.setattr(recall_mod, "_BOT_UID", "U0BOT")
    assert recall_mod._addressed_to_deja("<@U0BOT> should we migrate to Temporal?")
    assert not recall_mod._addressed_to_deja("should we migrate to Temporal?")
    # The literal "@Deja" handle (RTS's rendered form / a copied 'Try these' example) must also be
    # caught — this is the form that leaked into the timeline + counter.
    assert recall_mod._addressed_to_deja(
        "`@Deja should we adopt Datadog for monitoring?`"
    )
    assert recall_mod._addressed_to_deja("@Déjà are we launching GA?")
    assert not recall_mod._addressed_to_deja(
        "we should adopt Datadog"
    )  # no handle → real discussion


def test_deja_mentions_and_cards_never_counted(monkeypatch):
    """Ask the SAME thing 5×: @Deja questions (real <@UID> mention AND literal '@Deja' text) and
    Déjà's own cards must never become memories, so 'discussed N×' stays put (acceptance criterion)."""
    from deja.memory import recall_memories
    from deja.models import Hit

    monkeypatch.setattr(recall_mod, "_BOT_UID", "U0BOT")

    def _mk(ts, snippet):
        return Hit(
            reply_count=1,
            permalink=f"l://{ts}",
            channel="eng",
            channel_id="C1",
            author="tester",
            author_id="tester",
            ts=ts,
            snippet=snippet,
            score=1.0,
        )

    hits = [
        _mk(
            "100", "Starting a Datadog trial for observability/monitoring"
        ),  # real thread
        _mk("200", "<@U0BOT> should we adopt Datadog for monitoring?"),  # real mention
        _mk(
            "300", "`@Deja should we adopt Datadog for monitoring?`"
        ),  # literal example
        _mk("400", "⏳ Déjà vu — your team already discussed this"),  # Déjà's own card
    ]
    threads = {
        "100": [
            {
                "text": "Starting a Datadog trial for observability/monitoring",
                "ts": "100",
            },
            {
                "text": "Decision: we're DROPPING Datadog for monitoring, going with Grafana.",
                "username": "Priya",
                "subtype": "bot_message",
            },
        ],
        "200": [
            {"text": "<@U0BOT> should we adopt Datadog for monitoring?", "ts": "200"}
        ],
        "300": [
            {"text": "`@Deja should we adopt Datadog for monitoring?`", "ts": "300"}
        ],
        "400": [{"text": "⏳ Déjà vu — your team already discussed this", "ts": "400"}],
    }

    def _recall(q, **k):
        return hits

    async def _thread(client, cid, ts):
        return threads[ts]

    counts = []
    for _ in range(5):
        res = asyncio.run(
            recall_memories(
                "should we adopt Datadog for monitoring?",
                recall_fn=_recall,
                thread_fn=_thread,
            )
        )
        counts.append(len(res["memories"]))
        blob = " ".join(m["source_message"].lower() for m in res["memories"])
        assert (
            "@deja" not in blob and "déjà vu" not in blob
        )  # nothing addressed-to-Déjà leaked
    assert counts == [1, 1, 1, 1, 1]  # only the real thread, stable across repeats


def test_resolve_name_passthrough_without_client():
    assert (
        asyncio.run(_resolve_name(None, "Maya Chen")) == "Maya Chen"
    )  # username as-is
    assert (
        asyncio.run(_resolve_name(None, "U0ABC123")) == "U0ABC123"
    )  # no client -> id kept


def test_rate_limit_propagates_not_swallowed():
    import pytest

    from deja.memory import recall_memories
    from deja.recall import RateLimitedError

    def _boom(*a, **k):
        raise RateLimitedError("throttled")

    with pytest.raises(
        RateLimitedError
    ):  # must surface so the caller can say 'try again'
        asyncio.run(recall_memories("anything", recall_fn=_boom))
