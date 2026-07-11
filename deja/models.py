from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Hit:
    """One retrieval result from `recall()`.

    RTS (`assistant.search.context`) does not return a relevance score, so `score` is
    computed by Déjà (query-term overlap) to give a deterministic, explainable ranking.
    """

    permalink: str    # deep link to the message — the "here's the thread" payload
    channel: str      # channel name (falls back to channel id)
    channel_id: str   # channel id — needed to fetch the thread's replies (the decision)
    author: str       # author display name (falls back to user id)
    author_id: str    # author user id — for a clean <@mention> in the card
    ts: str           # message timestamp (Slack "ts") — also the thread_ts for a parent
    snippet: str      # message text
    score: float      # Déjà's deterministic query-overlap score in [0, 1]
    reply_count: int  # replies on the message — a discussed thread beats a lone line
