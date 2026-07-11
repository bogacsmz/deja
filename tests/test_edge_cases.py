"""Hermetic edge-case tests for the memory tool: channel filter, decision-first ordering, unicode."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from deja import memory
from deja.models import Hit


def _hit(**kw) -> Hit:
    base = dict(
        permalink="https://x.slack.com/archives/C1/p1",
        channel="general",
        channel_id="C1",
        author="alice",
        author_id="U1",
        ts="1.0",
        snippet="a decision about something",
        score=0.9,
        reply_count=2,
    )
    base.update(kw)
    return Hit(**base)


def test_channel_filter_restricts_results(monkeypatch):
    monkeypatch.setenv("SLACK_USER_TOKEN", "xoxp-test")
    client = MagicMock()
    client.conversations_replies = AsyncMock(
        return_value={"messages": [{"ts": "1.0", "text": "parent", "user": "U1"}]}
    )
    hits = [_hit(channel="eng"), _hit(channel="ops")]
    with (
        patch.object(memory, "recall", return_value=hits),
        patch.object(memory, "AsyncWebClient", return_value=client),
    ):
        r = asyncio.run(memory.recall_memories("q", channel="eng"))
    assert r["memories"] and all(m["channel"] == "eng" for m in r["memories"])


def test_decision_bearing_memory_ranks_first(monkeypatch):
    monkeypatch.setenv("SLACK_USER_TOKEN", "xoxp-test")
    no_decision = {"messages": [{"ts": "1.0", "text": "parent A", "user": "U1"}]}
    with_decision = {
        "messages": [
            {"ts": "2.0", "text": "parent B", "user": "U1"},
            {
                "ts": "2.1",
                "thread_ts": "2.0",
                "text": "we decided to buy Auth0",
                "user": "U2",
            },
        ]
    }
    client = MagicMock()
    client.conversations_replies = AsyncMock(side_effect=[no_decision, with_decision])
    hits = [_hit(ts="1.0", channel="a"), _hit(ts="2.0", channel="b")]
    with (
        patch.object(memory, "recall", return_value=hits),
        patch.object(memory, "AsyncWebClient", return_value=client),
    ):
        r = asyncio.run(memory.recall_memories("q"))
    assert r["memories"][0]["what_happened_next"]  # the one WITH a decision leads
    assert "buy" in r["memories"][0]["what_happened_next"].lower()


def test_unicode_query_is_preserved(monkeypatch):
    monkeypatch.setenv("SLACK_USER_TOKEN", "xoxp-test")
    q = "déjà café → naïve façade "
    with patch.object(memory, "recall", return_value=[]) as rc:
        r = asyncio.run(memory.recall_memories(q))
    assert r["searched"] == q.strip()
    rc.assert_called_once()
