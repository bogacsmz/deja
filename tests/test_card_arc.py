"""Hermetic tests for the decision-arc Block Kit card (deja.card.build_arc_card)."""

import json

from deja.arc import build_arc
from deja.card import build_arc_card
from deja.conflict import detect_conflict


def _m(ts, decision="", source="proposal", author="alex"):
    return {
        "ts": ts,
        "what_happened_next": decision,
        "source_message": f"[Mar {ts}] {source}",
        "author": author,
        "channel": "eng",
        "permalink": f"https://x/p{ts}",
    }


def _types(blocks):
    return [b["type"] for b in blocks]


def _rollback_arc():
    return build_arc(
        "temporal",
        [
            _m("1", source="proposing Temporal", author="Maya Chen"),
            _m("2", decision="rolling back to Redis", author="Maya Chen"),
        ],
    )


def test_settled_card_has_standing_decision_timeline_and_save():
    arc = _rollback_arc()
    blocks, fallback = build_arc_card("temporal", arc)
    assert "header" in _types(blocks) and "actions" in _types(blocks)
    flat = json.dumps(blocks)
    assert "Standing decision" in flat and "rolling back" in flat.lower()
    assert "Timeline" in flat and "Maya Chen" in flat
    assert "deja_save_decision" in flat  # save button present when settled
    assert "AI-generated" in flat  # honesty/AI label
    assert "standing decision" in fallback.lower()


def test_inconclusive_card_has_no_save_button_and_says_inconclusive():
    arc = build_arc(
        "x", [_m("1", source="should we use X?"), _m("2", source="still unsure")]
    )
    blocks, fallback = build_arc_card("x", arc)
    flat = json.dumps(blocks)
    assert "Inconclusive" in flat and "won't invent" in flat.lower()
    assert "deja_save_decision" not in flat  # never offer to save a non-decision
    assert "inconclusive" in fallback.lower()


def test_card_renders_conflict_warning():
    arc = _rollback_arc()
    warning = detect_conflict("should we migrate to Temporal for the new service?", arc)
    assert warning is not None
    blocks, _ = build_arc_card("temporal", arc, warning)
    assert warning.text in json.dumps(blocks, ensure_ascii=False)
