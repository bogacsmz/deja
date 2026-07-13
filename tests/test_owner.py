"""Hermetic tests for decision-owner resolution + the ask-owner coordination copy."""

import asyncio

import deja.owner as owner
from deja.owner import resolve_owner_id
from listeners.actions.deja_card import _ordinal


class _FakeClient:
    def __init__(self, members):
        self._m = members

    async def users_list(self, limit=200, cursor=None):
        return {"members": self._m, "response_metadata": {"next_cursor": ""}}


def test_ordinal_reads_naturally():
    assert [_ordinal(n) for n in (1, 2, 3, 4, 5)] == ["1st", "2nd", "3rd", "4th", "5th"]
    assert _ordinal(11) == "11th" and _ordinal(21) == "21st" and _ordinal(13) == "13th"


def test_resolve_matches_display_name_else_empty(monkeypatch):
    monkeypatch.delenv("DEJA_OWNER_FALLBACK", raising=False)
    c = _FakeClient([{"id": "U1", "profile": {"display_name": "Maya Chen"}}])
    owner._NAME_MAP = None
    assert asyncio.run(resolve_owner_id(c, "Maya Chen")) == "U1"
    owner._NAME_MAP = None
    assert (
        asyncio.run(resolve_owner_id(c, "Nobody Here")) == ""
    )  # unresolved → button hidden


def test_resolve_falls_back_for_demo(monkeypatch):
    monkeypatch.setenv("DEJA_OWNER_FALLBACK", "UDEMO")
    owner._NAME_MAP = None
    assert asyncio.run(resolve_owner_id(_FakeClient([]), "Maya Chen")) == "UDEMO"


def test_resolve_passthrough_uid_and_no_client(monkeypatch):
    monkeypatch.delenv("DEJA_OWNER_FALLBACK", raising=False)
    owner._NAME_MAP = None
    assert asyncio.run(resolve_owner_id(_FakeClient([]), "U0ABC123")) == "U0ABC123"
    assert asyncio.run(resolve_owner_id(None, "Maya Chen")) == ""  # no client → empty
