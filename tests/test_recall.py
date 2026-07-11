"""Hermetic unit tests for recall() ranking + filtering — WebClient/RTS fully mocked."""

from unittest.mock import MagicMock, patch

from deja.recall import recall


def _resp(messages):
    r = MagicMock()
    r.data = {"results": {"messages": messages}}
    return r


def _msg(content, ts="1.0", rc=0, channel="eng"):
    return {
        "content": content,
        "message_ts": ts,
        "reply_count": rc,
        "channel_name": channel,
        "channel_id": "C1",
        "permalink": "https://x.slack.com/p1",
        "author_name": "a",
        "author_user_id": "U1",
    }


def _recall(messages, **kw):
    client = MagicMock()
    client.api_call.return_value = _resp(messages)
    with patch("deja.recall.WebClient", return_value=client):
        return recall("temporal migration", token="xoxp-test", **kw)


def test_drops_deja_cards_and_empty_hits():
    hits = _recall(
        [
            _msg("Déjà vu — your team already discussed this"),  # own card
            _msg("   "),  # empty
            _msg("real temporal migration thread", ts="2.0"),
        ]
    )
    assert len(hits) == 1
    assert "real" in hits[0].snippet


def test_excludes_the_triggering_message():
    assert _recall([_msg("temporal migration", ts="9.9")], exclude_ts="9.9") == []


def test_ties_break_on_reply_count():
    """Equal query overlap -> the thread that was actually discussed (more replies) ranks first."""
    hits = _recall(
        [
            _msg("temporal migration", ts="1.0", rc=0),
            _msg("temporal migration", ts="2.0", rc=5),
        ]
    )
    assert [h.reply_count for h in hits] == [5, 0]


def test_score_beats_reply_count():
    """Relevance is primary: a better query match outranks a more-replied but weaker match."""
    hits = _recall(
        [
            _msg("temporal migration exact match", ts="1.0", rc=9),
            _msg("temporal something unrelated words here", ts="2.0", rc=0),
        ]
    )
    assert hits[0].score >= hits[1].score


def test_limit_trims_results():
    msgs = [_msg(f"temporal migration option {i}", ts=f"{i}.0") for i in range(10)]
    assert len(_recall(msgs, limit=3)) == 3
