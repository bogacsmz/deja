"""Hermetic tests for the Phase-6 realistic seed. All seeded decisions now live in
`scripts/seed_arcs.py` as back-dated, persona-attributed arcs (posted with the bot token +
chat:write.customize), so nothing is ever owned by the raw sandbox account. These tests validate
that dataset's integrity — no live Slack.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

# scripts/ isn't an installed package; put it on the path so we can import the demo tooling.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from seed_arcs import ALL_THREADS, ARCS, AUTHORS  # noqa: E402
from seed_data import is_decision  # noqa: E402

# The RFC arc is discussed repeatedly but NEVER decided — Déjà must surface it as INCONCLUSIVE, so
# it is the one arc that intentionally carries no decision cue.
_INCONCLUSIVE = {"RFC / design-doc process"}
_DATE = re.compile(r"\[[A-Za-z]{3,9}\s+\d{1,2}\]")


def test_markers_are_unique():
    markers = [t.marker for t in ALL_THREADS]
    assert len(markers) == len(set(markers)), "duplicate idempotency marker(s)"


def test_settled_arcs_record_a_decision_inconclusive_does_not():
    for name, threads in ARCS.items():
        has = any(is_decision(r.text) for t in threads for r in t.replies)
        if name in _INCONCLUSIVE:
            assert not has, f"{name} must stay inconclusive (no decision cue anywhere)"
        else:
            assert has, f"settled arc {name!r} has no decision/outcome reply"


def test_arc_threads_are_populated_dated_and_attributed():
    for name, threads in ARCS.items():
        for t in threads:
            assert t.channel and not t.channel.startswith("#")
            assert t.marker.startswith("‹deja-arc:") and t.marker.endswith("›")
            assert t.parent.text.strip()
            assert _DATE.search(t.parent.text), (
                f"{t.marker} parent missing a [Mon DD] date"
            )
            # every author is a real persona (has an avatar), never the raw sandbox user
            for msg in (t.parent, *t.replies):
                assert msg.author in AUTHORS, (
                    f"{t.marker}: unknown author {msg.author!r}"
                )


def test_spans_multiple_channels():
    assert len({t.channel for t in ALL_THREADS}) >= 4, (
        "seed should span several channels"
    )


def test_is_decision_helper():
    assert is_decision("Decision: we're going with Postgres")
    assert is_decision("Update after 3 weeks: rolling back")
    assert not is_decision("what do you all think about this?")
