"""Robustness — a jury will type anything into the sandbox for three weeks, and every failure mode
here must degrade to SILENCE or INCONCLUSIVE, never to a traceback or a 500.

Hermetic: no Slack, no LLM, no network. Each test drives a real entry point (check_decision,
recall_memories, the /mcp ASGI app) with the input a judge could plausibly produce.
"""

import asyncio
import time

import pytest
from slack_sdk.signature import SignatureVerifier
from starlette.testclient import TestClient

import deja.memory as memory
import deja.trigger as trigger
from deja.arc import build_arc, recall_arc
from deja.govern import ALLOW, INCONCLUSIVE, check_decision
import deja.mcp_http as mcp_http
from deja.recall import RateLimitedError
from deja.trigger import TriggerDecision

SECRET = "test-signing-secret"


def _stub_judge(monkeypatch, *, should_recall=True, query="Temporal job queue"):
    async def _judge(_msg):
        return TriggerDecision(should_recall, query, "")

    monkeypatch.setattr(trigger, "judge", _judge)


def _retrieval(monkeypatch, recall_impl, thread_impl=None):
    async def _empty_thread(_client, _cid, _ts):
        return []

    monkeypatch.setattr(memory, "recall", recall_impl)
    monkeypatch.setattr(memory, "fetch_thread_messages", thread_impl or _empty_thread)
    monkeypatch.setenv("SLACK_USER_TOKEN", "xoxp-test-not-a-real-token")
    # Point the canonical store at nothing: these tests are about the RETRIEVAL failure modes, and a
    # developer's real deja_decisions.json sitting in the cwd would otherwise answer for them.
    monkeypatch.setenv("DEJA_STORE", "/nonexistent/deja_decisions.json")


# ── retrieval failure modes ────────────────────────────────────────────────────────────────────


def test_rts_returns_nothing_is_allow_not_an_exception(monkeypatch):
    """Empty search results must produce a verdict, not a traceback."""
    _stub_judge(monkeypatch)
    _retrieval(monkeypatch, lambda *a, **k: [])
    v = asyncio.run(check_decision("let's migrate the job queue to Temporal"))
    assert v["verdict"] == ALLOW  # nothing on record to conflict with
    assert v["sources"] == []


def test_rts_rate_limited_surfaces_cleanly_and_does_not_crash_the_caller(monkeypatch):
    """RTS 429 must reach the caller as RateLimitedError (so the card can say 'try again in a
    minute') — a silent empty result would be a lie, and a crash would kill the container."""

    def _throttled(*_a, **_k):
        raise RateLimitedError("RTS is rate-limiting the search")

    _retrieval(monkeypatch, _throttled)
    with pytest.raises(RateLimitedError):
        asyncio.run(memory.recall_memories("Temporal job queue"))


def test_rts_transport_error_degrades_to_an_empty_result(monkeypatch):
    """Any other retrieval failure becomes a clean summary + no memories — never an exception."""

    def _boom(*_a, **_k):
        raise RuntimeError("connection reset")

    _retrieval(monkeypatch, _boom)
    r = asyncio.run(memory.recall_memories("Temporal job queue"))
    assert r["memories"] == []
    assert "failed" in r["summary"].lower()


def test_thread_enrichment_failure_does_not_lose_the_memory(monkeypatch):
    """conversations.replies blowing up (e.g. users.info/scope error) must not drop the hit or
    crash — we fall back to the search snippet."""
    from deja.models import Hit

    hit = Hit(
        reply_count=1,
        permalink="https://slack.com/x",
        channel="eng",
        channel_id="C1",
        author="maya",
        author_id="U1",
        ts="1.0",
        snippet="we are rolling back the Temporal migration",
        score=1.0,
    )

    async def _broken_thread(_client, _cid, _ts):
        raise RuntimeError("users.info failed")

    _retrieval(monkeypatch, lambda *a, **k: [hit], _broken_thread)
    r = asyncio.run(memory.recall_memories("Temporal"))
    assert len(r["memories"]) == 1
    assert r["memories"][0]["permalink"] == "https://slack.com/x"


# ── hostile / degenerate input ─────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "proposal",
    [
        "",
        "   ",
        "🎉🎉🎉",
        "```python\nprint('hi')\n```",
        "x" * 5000,
        "Temporal'a geçmeli miyiz yoksa Redis mi kullanmalıyız?",
        "咖啡时间到了吗",
        "\n\n\t\n",
        "<@U123> <#C456|general> <https://x.y>",
    ],
)
def test_degenerate_input_never_raises(monkeypatch, proposal):
    """Empty, emoji-only, code blocks, 5000 chars, Turkish, Chinese, whitespace, Slack markup —
    every one must return a verdict dict. Non-English may stay silent; it may not explode."""
    _stub_judge(monkeypatch, should_recall=False, query="")
    _retrieval(monkeypatch, lambda *a, **k: [])
    v = asyncio.run(check_decision(proposal))
    assert v["verdict"] in (ALLOW, INCONCLUSIVE)
    assert isinstance(v["sources"], list)


def test_empty_proposal_is_inconclusive_not_a_500():
    """No judge, no retrieval — the guard must short-circuit before anything can throw."""
    v = asyncio.run(check_decision("   "))
    assert v["verdict"] == INCONCLUSIVE


def test_empty_channel_history_is_graceful(monkeypatch):
    """A workspace with nothing in it: recall_arc must return None, not raise."""
    _retrieval(monkeypatch, lambda *a, **k: [])
    assert asyncio.run(recall_arc("anything at all", expand=False)) is None


def test_build_arc_on_no_memories_is_none():
    assert build_arc("topic", []) is None


# ── the /mcp endpoint, fail-closed ─────────────────────────────────────────────────────────────


@pytest.fixture
def client():
    # NO lifespan (no `with`): FastMCP's session manager may only be entered once per process, and
    # tests/test_mcp_http.py already owns it. Nothing here needs it — the signature middleware and the
    # route table both sit in front of the MCP app, which is exactly the surface under test.
    return TestClient(mcp_http.app)


def _sign(body: bytes, ts: str) -> dict:
    sig = SignatureVerifier(signing_secret=SECRET).generate_signature(
        timestamp=ts, body=body
    )
    return {"X-Slack-Request-Timestamp": ts, "X-Slack-Signature": sig}


def test_replayed_request_is_rejected(client, monkeypatch):
    """A correctly-signed request from 10 minutes ago is a REPLAY. slack_sdk enforces the 5-minute
    window; this pins it, because 'signature-verified, fail-closed' is a claim we publish."""
    monkeypatch.setenv("SLACK_SIGNING_SECRET", SECRET)
    body = b'{"jsonrpc":"2.0","method":"tools/list","id":1}'
    r = client.post(
        "/mcp", content=body, headers=_sign(body, str(int(time.time()) - 600))
    )
    assert r.status_code == 401


@pytest.mark.parametrize("ts", ["not-a-number", "", "1e9999", "-", "0x10", "9" * 400])
def test_malformed_timestamp_header_is_401_not_500(client, monkeypatch, ts):
    """A junk X-Slack-Request-Timestamp must fail CLOSED (401). slack_sdk calls int() on it with no
    guard, so unhandled this is an unauthenticated 500 on a public URL."""
    monkeypatch.setenv("SLACK_SIGNING_SECRET", SECRET)
    r = client.post(
        "/mcp",
        content=b"{}",
        headers={"X-Slack-Request-Timestamp": ts, "X-Slack-Signature": "v0=deadbeef"},
    )
    assert r.status_code == 401


def test_no_other_route_is_exposed(client):
    """/mcp and /healthz are the whole public surface."""
    assert client.get("/").status_code == 404
    assert client.get("/.env").status_code == 404
    assert client.get("/mcp").status_code == 405  # POST-only
