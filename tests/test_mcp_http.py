"""Hermetic tests for the HTTP MCP endpoint (Slackbot MCP Client): signature gate + tool metadata.

Verifies the security layer locally with a self-computed Slack signature — no real secret, ngrok,
or Slackbot needed. The live Slackbot discover/call proof is a human-loop step (see docs/SLACKBOT-MCP.md).
"""

import asyncio
import hashlib
import hmac
import time

import pytest
from starlette.testclient import TestClient

import deja.mcp_http as h

_SECRET = "test-signing-secret"


@pytest.fixture(scope="module")
def client():
    # One client for the module: FastMCP's session manager can only be run once.
    with TestClient(h.app) as c:
        yield c


def _sign(body: bytes, ts: str) -> dict:
    base = f"v0:{ts}:{body.decode()}".encode()
    sig = "v0=" + hmac.new(_SECRET.encode(), base, hashlib.sha256).hexdigest()
    return {
        "X-Slack-Request-Timestamp": ts,
        "X-Slack-Signature": sig,
        "content-type": "application/json",
        "accept": "application/json, text/event-stream",
    }


def test_healthz(client):
    assert client.get("/healthz").json() == {"ok": True}


def test_rejects_unsigned_request(client, monkeypatch):
    monkeypatch.setenv("SLACK_SIGNING_SECRET", _SECRET)
    r = client.post("/mcp", content=b'{"jsonrpc":"2.0","id":1,"method":"tools/list"}')
    assert r.status_code == 401


def test_rejects_when_secret_missing(client, monkeypatch):
    monkeypatch.delenv("SLACK_SIGNING_SECRET", raising=False)
    body = b'{"jsonrpc":"2.0","id":1,"method":"tools/list"}'
    ts = str(int(time.time()))
    r = client.post("/mcp", content=body, headers=_sign(body, ts))
    assert r.status_code == 401  # can't verify without a configured secret


def test_accepts_validly_signed_request(client, monkeypatch):
    monkeypatch.setenv("SLACK_SIGNING_SECRET", _SECRET)
    body = b'{"jsonrpc":"2.0","id":1,"method":"tools/list"}'
    ts = str(int(time.time()))
    r = client.post("/mcp", content=body, headers=_sign(body, ts))
    # The signature gate passed it through to the MCP app (a 401 would mean it was blocked).
    assert r.status_code != 401


def test_recall_memory_tool_is_read_only():
    tools = asyncio.run(h.mcp_server.list_tools())
    tool = next(t for t in tools if t.name == "recall_memory")
    assert tool.annotations is not None
    assert tool.annotations.readOnlyHint is True
