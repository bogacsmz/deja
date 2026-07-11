"""Hermetic tests for the decision-arc synthesis (deja.arc.build_arc) — pure, no Slack."""

from deja.arc import build_arc


def _m(ts, decision="", source="proposal", author="alex", channel="eng"):
    return {
        "ts": ts,
        "what_happened_next": decision,
        "source_message": source,
        "author": author,
        "channel": channel,
        "permalink": f"https://x.slack.com/p{ts}",
    }


def test_empty_is_none():
    assert build_arc("temporal", []) is None


def test_multi_thread_arc_uses_latest_decision():
    memories = [
        _m("3000", decision="rolled back to Redis", author="maya"),
        _m("1000", source="proposing Temporal", author="alex"),  # no decision
        _m("2000", decision="migration started", author="sam"),
    ]
    arc = build_arc("temporal", memories)
    assert arc.times_discussed == 3
    assert arc.is_recurring
    assert arc.confidence == "high"
    # standing decision = the most recent decision, not the earliest
    assert "rolled back" in arc.standing_decision.lower()
    assert arc.owner == "maya"
    # timeline is chronological
    assert [e.ts for e in arc.timeline] == ["1000", "2000", "3000"]
    assert len(arc.sources) == 3


def test_honesty_inconclusive_when_no_decision():
    memories = [_m("1", source="should we use X?"), _m("2", source="still debating X")]
    arc = build_arc("x", memories)
    assert arc.inconclusive
    assert arc.confidence == "inconclusive"
    assert arc.standing_decision == "" and arc.owner == ""
    assert (
        arc.times_discussed == 2
    )  # the discussion is still surfaced, just not a fake decision


def test_single_thread_degrades_cleanly():
    arc = build_arc("auth", [_m("5", decision="decided: buy Auth0", author="maya")])
    assert arc.times_discussed == 1
    assert not arc.is_recurring
    assert "auth0" in arc.standing_decision.lower()
    assert arc.confidence == "high"
