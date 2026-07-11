"""Hermetic tests for deja.conflict.detect_conflict — pure, no Slack."""

from deja.arc import build_arc
from deja.conflict import detect_conflict


def _m(ts, decision="", source="proposal", author="alex"):
    return {
        "ts": ts,
        "what_happened_next": decision,
        "source_message": source,
        "author": author,
        "channel": "eng",
        "permalink": f"https://x/p{ts}",
    }


def _rollback_arc():
    return build_arc(
        "temporal",
        [
            _m("1", source="proposing Temporal", author="maya"),
            _m(
                "2",
                decision="we're rolling back to Redis, not worth the ops cost",
                author="maya",
            ),
        ],
    )


def test_contradiction_when_reproposing_rejected_thing():
    arc = _rollback_arc()
    w = detect_conflict("Should we migrate to Temporal for the new pipeline?", arc)
    assert w is not None and w.kind == "contradiction"
    assert "standing decision" in w.text.lower()


def test_staleness_when_recurring_but_not_reproposing_rejection():
    arc = build_arc(
        "deploy",
        [
            _m("1", source="move to continuous deploy?", author="lena"),
            _m(
                "2",
                decision="decided: continuous deploy on merge to main",
                author="lena",
            ),
        ],
    )
    w = detect_conflict("what's our deploy cadence again?", arc)
    assert w is not None and w.kind == "staleness"


def test_no_warning_on_inconclusive():
    arc = build_arc(
        "x", [_m("1", source="should we use X?"), _m("2", source="still unsure")]
    )
    assert detect_conflict("should we use X?", arc) is None


def test_no_warning_without_arc():
    assert detect_conflict("should we migrate to Temporal?", None) is None
