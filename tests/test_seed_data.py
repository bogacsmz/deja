"""Hermetic tests for the Phase-6 realistic seed: dataset integrity + seeder idempotency logic.

No live Slack — the seeder's I/O goes through an injected fake WebClient.
"""
from __future__ import annotations

import sys
from pathlib import Path

# scripts/ isn't an installed package; put it on the path so we can import the demo tooling.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import seed_deja  # noqa: E402
from seed_data import SEEDS, is_decision  # noqa: E402


# --------------------------------------------------------------------------- dataset integrity

def test_markers_are_unique():
    markers = [t.marker for t in SEEDS]
    assert len(markers) == len(set(markers)), "duplicate idempotency marker(s) in SEEDS"


def test_every_thread_records_a_decision():
    missing = [t.topic for t in SEEDS if not t.has_decision()]
    assert not missing, f"threads with no decision/outcome reply: {missing}"


def test_thread_fields_are_populated():
    for t in SEEDS:
        assert t.channel and not t.channel.startswith("#")
        assert t.parent.strip() and t.topic.strip()
        assert len(t.replies) >= 1
        assert t.marker.startswith("‹deja-seed:") and t.marker.endswith("›")


def test_covers_multiple_channels():
    assert len({t.channel for t in SEEDS}) >= 4, "Phase 6 should span several channels"


def test_is_decision_helper():
    assert is_decision("Decision: we're going with Postgres")
    assert is_decision("Update after 3 weeks: rolling back")
    assert not is_decision("what do you all think about this?")


# ------------------------------------------------------------------------------- fake client

class FakeSlack:
    """Minimal stand-in for slack_sdk.WebClient covering only what the seeder calls."""

    def __init__(self, existing_channels, seeded_markers=()):
        # existing_channels: {name: id}; seeded_markers: iterable of markers already in history
        self._channels = existing_channels
        self._seeded = set(seeded_markers)
        self.posted = []  # (channel_id, text, thread_ts)

    def conversations_list(self, *, types, limit, cursor, team_id):
        chans = [{"name": n, "id": i} for n, i in self._channels.items()]
        return {"channels": chans, "response_metadata": {"next_cursor": ""}}

    def conversations_history(self, *, channel, limit):
        # Return any already-seeded markers as history messages (channel-agnostic is fine for tests).
        return {"messages": [{"text": m} for m in self._seeded]}

    def chat_postMessage(self, *, channel, text, thread_ts=None):
        self.posted.append((channel, text, thread_ts))
        return {"ts": f"ts-{len(self.posted)}"}

    def chat_getPermalink(self, *, channel, message_ts):
        return {"permalink": f"https://deja.slack.com/archives/{channel}/p{message_ts}"}


_ALL_CHANNELS = {t.channel: f"C_{t.channel}" for t in SEEDS}


def _status_by_topic(results):
    return {thread.topic: status for status, thread, _ in results}


# ------------------------------------------------------------------------------- seeder logic

def test_dry_run_posts_nothing():
    client = FakeSlack(_ALL_CHANNELS)
    results = seed_deja.seed_workspace(client, dry_run=True)
    assert all(status == "would-post" for status, _, _ in results)
    assert client.posted == [], "dry-run must not write to Slack"


def test_full_seed_posts_every_thread_with_permalink():
    client = FakeSlack(_ALL_CHANNELS)
    results = seed_deja.seed_workspace(client, dry_run=False)
    assert all(status == "posted" for status, _, _ in results)
    assert all(link and link.startswith("http") for _, _, link in results)
    # each thread writes exactly 1 parent + len(replies) reply messages
    expected_msgs = sum(1 + len(t.replies) for t in SEEDS)
    assert len(client.posted) == expected_msgs


def test_idempotent_skip_of_already_seeded():
    already = SEEDS[0].marker
    client = FakeSlack(_ALL_CHANNELS, seeded_markers=[already])
    results = seed_deja.seed_workspace(client, dry_run=False)
    by_topic = _status_by_topic(results)
    assert by_topic[SEEDS[0].topic] == "skipped"
    # nothing from the skipped thread was posted
    assert all(SEEDS[0].marker not in text for _, text, _ in client.posted)


def test_missing_channel_is_warned_not_fatal():
    # Drop #design from the workspace; those threads should be 'missing', the rest still posted.
    channels = {n: i for n, i in _ALL_CHANNELS.items() if n != "design"}
    client = FakeSlack(channels)
    results = seed_deja.seed_workspace(client, dry_run=False)
    for status, thread, _ in results:
        if thread.channel == "design":
            assert status == "missing"
        else:
            assert status == "posted"
