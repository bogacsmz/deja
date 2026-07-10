from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Hit:
    """One retrieval result from `recall()`.

    RTS (`assistant.search.context`) does not return a relevance score, so `score` is
    computed by Déjà (query-term overlap) to give a deterministic, explainable ranking.
    """

    permalink: str   # deep link to the message — the "here's the thread" payload
    channel: str     # channel name (falls back to channel id)
    author: str      # author display name (falls back to user id)
    ts: str          # message timestamp (Slack "ts")
    snippet: str     # message text
    score: float     # Déjà's deterministic query-overlap score in [0, 1]
