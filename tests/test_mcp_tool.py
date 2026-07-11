"""Unit tests for the MCP memory tool logic (deja.memory.recall_memories) — fully mocked, hermetic."""
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from deja import memory
from deja.models import Hit


def _hit(**kw) -> Hit:
    base = dict(
        permalink="https://x.slack.com/archives/C1/p1", channel="general", channel_id="C1",
        author="alice", author_id="U1", ts="1.0", snippet="migrate to Temporal?",
        score=0.9, reply_count=2,
    )
    base.update(kw)
    return Hit(**base)


def _client_with(messages) -> MagicMock:
    c = MagicMock()
    c.conversations_replies = AsyncMock(return_value={"messages": messages})
    return c


def test_no_token(monkeypatch):
    monkeypatch.delenv("SLACK_USER_TOKEN", raising=False)
    r = asyncio.run(memory.recall_memories("q"))
    assert r["memories"] == [] and "not configured" in r["summary"].lower()


def test_empty_query(monkeypatch):
    monkeypatch.setenv("SLACK_USER_TOKEN", "xoxp-test")
    r = asyncio.run(memory.recall_memories("   "))
    assert r["memories"] == []


def test_search_error_is_clean(monkeypatch):
    monkeypatch.setenv("SLACK_USER_TOKEN", "xoxp-test")
    with patch.object(memory, "recall", side_effect=RuntimeError("boom")):
        r = asyncio.run(memory.recall_memories("q"))
    assert r["memories"] == [] and "failed" in r["summary"].lower()


def test_no_hits(monkeypatch):
    monkeypatch.setenv("SLACK_USER_TOKEN", "xoxp-test")
    with patch.object(memory, "recall", return_value=[]):
        r = asyncio.run(memory.recall_memories("q"))
    assert r["memories"] == [] and "no prior" in r["summary"].lower()


def test_shape_and_decision(monkeypatch):
    monkeypatch.setenv("SLACK_USER_TOKEN", "xoxp-test")
    client = _client_with([
        {"text": "migrate to Temporal?", "user": "U1"},
        {"text": "we're rolling back the Temporal migration", "user": "U2"},
    ])
    with patch.object(memory, "recall", return_value=[_hit()]), \
         patch.object(memory, "AsyncWebClient", return_value=client):
        r = asyncio.run(memory.recall_memories("temporal", limit=3))

    assert r["searched"] == "temporal"
    assert len(r["memories"]) == 1
    m = r["memories"][0]
    assert m["permalink"].startswith("http")
    assert "rolling back" in m["what_happened_next"].lower()
    assert set(m) == {"source_message", "what_happened_next", "channel", "author", "ts",
                      "permalink", "score"}


def test_reply_hit_resolves_to_thread_root(monkeypatch):
    """A reply-level hit re-fetches from thread_ts so it still enriches with the decision."""
    monkeypatch.setenv("SLACK_USER_TOKEN", "xoxp-test")
    reply_only = {"messages": [
        {"ts": "2.0", "thread_ts": "1.0", "text": "we're rolling back Temporal", "user": "U2"},
    ]}
    full_thread = {"messages": [
        {"ts": "1.0", "text": "migrate to Temporal?", "user": "U1"},
        {"ts": "2.0", "thread_ts": "1.0", "text": "we're rolling back Temporal", "user": "U2"},
    ]}
    client = MagicMock()
    client.conversations_replies = AsyncMock(side_effect=[reply_only, full_thread])
    with patch.object(memory, "recall", return_value=[_hit(ts="2.0")]), \
         patch.object(memory, "AsyncWebClient", return_value=client):
        r = asyncio.run(memory.recall_memories("temporal"))

    assert len(r["memories"]) == 1
    assert "rolling back" in r["memories"][0]["what_happened_next"].lower()
    assert client.conversations_replies.await_count == 2  # reply-ts, then the resolved root


def test_ghost_dropped(monkeypatch):
    """A hit whose parent was deleted (RTS lag) is dropped, not returned."""
    monkeypatch.setenv("SLACK_USER_TOKEN", "xoxp-test")
    client = _client_with([{"subtype": "tombstone", "text": "This message was deleted."}])
    with patch.object(memory, "recall", return_value=[_hit()]), \
         patch.object(memory, "AsyncWebClient", return_value=client):
        r = asyncio.run(memory.recall_memories("temporal"))
    assert r["memories"] == []
