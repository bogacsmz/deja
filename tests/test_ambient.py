"""Hermetic loop-safety tests for the ambient governance handler (Mode B).

Drives handle_message with fake Slack client/context/say (no network). Verifies the non-negotiable
guards: Déjà never reacts to its own output, never answers a message addressed to it, and posts at
most once per thread even under concurrency."""

import asyncio

import listeners.events.message as m


class _Ctx:
    bot_id = "B_DEJA"
    bot_user_id = "U_DEJA"


class _Say:
    def __init__(self):
        self.calls = []

    async def __call__(self, **kw):
        self.calls.append(kw)


class _Client:
    def __init__(self, replies=None):
        self._r = replies or []

    async def conversations_replies(self, channel, ts, limit):
        return {"messages": self._r}


class _Log:
    def warning(self, *a, **k):
        pass

    def exception(self, *a, **k):
        pass


def _event(text, *, bot_id=None, subtype=None, ts="1.0", channel="C1"):
    e = {"text": text, "ts": ts, "channel": channel}
    if bot_id:
        e["bot_id"] = bot_id
    if subtype:
        e["subtype"] = subtype
    return e


def _drive(event, say, monkeypatch, card=None):
    async def _rc(text, client, **kw):
        # expose the is_agent classification the handler computed
        _rc.is_agent = kw.get("is_agent")
        return card

    monkeypatch.setattr(m, "recall_card", _rc)
    m._answered.clear()
    asyncio.run(m.handle_message(_Client(), _Ctx(), event, _Log(), say))
    return _rc


A_CARD = {"blocks": [{"type": "section"}], "text": "Déjà — standing decision"}


def test_never_reacts_to_own_message(monkeypatch):
    say = _Say()
    _drive(_event("Opening a PR to migrate to Temporal", bot_id="B_DEJA"), say, monkeypatch, card=A_CARD)
    assert say.calls == []  # our own bot_id → skipped before any work


def test_never_reacts_to_own_card_fingerprint(monkeypatch):
    say = _Say()
    _drive(_event("⏳ Déjà vu — your team already decided this"), say, monkeypatch, card=A_CARD)
    assert say.calls == []


def test_skips_message_addressed_to_deja(monkeypatch):
    say = _Say()
    _drive(_event("<@U_DEJA> should we migrate to Temporal?"), say, monkeypatch, card=A_CARD)
    assert say.calls == []  # @mention → app_mentioned handles it, not ambient


def test_never_brakes_slackbot(monkeypatch):
    # Sponsor-safety: Slackbot is the collaborator, never a caught agent. Even a Slackbot message that
    # would otherwise conflict must NOT be braked (a false guardrail on Slack's own bot = disqualifying).
    say = _Say()
    ev = _event("Opening a PR to migrate to Temporal", bot_id="B_SLACKBOT", ts="8.0")
    ev["user"] = "USLACKBOT"
    _drive(ev, say, monkeypatch, card=A_CARD)
    assert say.calls == []


def test_agent_message_classified_by_bot_id(monkeypatch):
    say = _Say()
    rc = _drive(_event("Opening a PR to migrate to Temporal", bot_id="B_OTHER"), say, monkeypatch, card=A_CARD)
    assert rc.is_agent is True and len(say.calls) == 1  # a real agent → Mode B, posts once


def test_human_message_is_not_agent(monkeypatch):
    say = _Say()
    rc = _drive(_event("should we migrate the job queue to Temporal?"), say, monkeypatch, card=A_CARD)
    assert rc.is_agent is False


def test_one_intervention_per_thread_no_double_post(monkeypatch):
    say = _Say()

    async def _rc(text, client, **kw):
        return A_CARD

    monkeypatch.setattr(m, "recall_card", _rc)
    m._answered.clear()
    ev = _event("Opening a PR to migrate to Temporal", bot_id="B_OTHER", ts="7.0")

    async def _both():
        await asyncio.gather(
            m.handle_message(_Client(), _Ctx(), ev, _Log(), say),
            m.handle_message(_Client(), _Ctx(), ev, _Log(), say),
        )

    asyncio.run(_both())
    assert len(say.calls) == 1  # atomic claim → exactly one card despite the race


def test_silent_when_no_card(monkeypatch):
    say = _Say()
    _drive(_event("just some chit chat here"), say, monkeypatch, card=None)
    assert say.calls == []
