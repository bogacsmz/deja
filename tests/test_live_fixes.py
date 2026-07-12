"""Hermetic regression tests for the Gate-6 live fixes (subject filter, truncation, self-pollution,
name resolution) — over the local mirror + pure functions, no live Slack."""

import asyncio
import sys

import deja.recall  # noqa: F401 — ensures the module is registered in sys.modules
from benchmarks.local import local_recall, local_thread
from deja.arc import recall_arc
from deja.memory import _resolve_name

# `deja.recall` the attribute is the re-exported recall() function, so reach the MODULE via sys.
recall_mod = sys.modules["deja.recall"]


def _arc(q):
    return asyncio.run(recall_arc(q, recall_fn=local_recall, thread_fn=local_thread))


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


def test_resolve_name_passthrough_without_client():
    assert (
        asyncio.run(_resolve_name(None, "Maya Chen")) == "Maya Chen"
    )  # username as-is
    assert (
        asyncio.run(_resolve_name(None, "U0ABC123")) == "U0ABC123"
    )  # no client -> id kept
