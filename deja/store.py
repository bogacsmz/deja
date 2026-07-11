"""Canonical saved-decision store — the flywheel behind the 💾 Save button.

When someone saves a decision from a Déjà card, it lands here: a small JSON log of the decisions a
team has explicitly confirmed. It feeds the App Home digest and the Slack Canvas, and future recalls
can surface a saved decision first. One record per topic (re-saving updates it + bumps a counter).

File-backed and dependency-free (JSON) so it's trivial to test and to reset. Path: DEJA_STORE env,
default `deja_decisions.json` in the working dir (git-ignored).
"""

from __future__ import annotations

import json
import os
import pathlib
import time


def _path() -> pathlib.Path:
    return pathlib.Path(os.environ.get("DEJA_STORE", "deja_decisions.json"))


def _load() -> dict:
    p = _path()
    if p.exists():
        try:
            return json.loads(p.read_text())
        except (ValueError, OSError):
            return {"decisions": {}, "meta": {}}
    return {"decisions": {}, "meta": {}}


def _write(data: dict) -> None:
    _path().write_text(json.dumps(data, ensure_ascii=False, indent=1))


def _key(topic: str) -> str:
    return " ".join((topic or "").lower().split())


def save_decision(record: dict, saved_by: str = "") -> dict:
    """Persist a decision (keyed by topic — re-saving updates it and bumps `times_saved`).

    `record` carries {topic, decision, owner, at, n, url}. Returns the stored entry."""
    data = _load()
    key = _key(record.get("topic") or record.get("q") or "")
    existing = data["decisions"].get(key, {})
    entry = {
        "topic": record.get("topic") or record.get("q") or "",
        "decision": record.get("decision", ""),
        "owner": record.get("owner", ""),
        "at": record.get("at", ""),
        "times_discussed": record.get("n", 0),
        "url": record.get("url", ""),
        "saved_by": saved_by,
        "saved_at": time.time(),
        "times_saved": existing.get("times_saved", 0) + 1,
    }
    data["decisions"][key] = entry
    _write(data)
    return entry


def list_decisions() -> list[dict]:
    """All saved decisions, most-recently-saved first."""
    return sorted(
        _load()["decisions"].values(), key=lambda d: d.get("saved_at", 0), reverse=True
    )


def count_saved_since(days: float = 7) -> int:
    """How many decisions were saved (or re-saved) in the last `days` — the 'circled back' signal."""
    cutoff = time.time() - days * 86400
    return sum(
        1 for d in _load()["decisions"].values() if d.get("saved_at", 0) >= cutoff
    )


def get_meta(key: str, default=None):
    return _load()["meta"].get(key, default)


def set_meta(key: str, value) -> None:
    data = _load()
    data["meta"][key] = value
    _write(data)
