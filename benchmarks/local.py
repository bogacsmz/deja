"""Local, RTS-free retrieval over the seeded workspace — for a reproducible benchmark.

Slack's RTS endpoint (assistant.search.context) is rate-limited to roughly one call every few
minutes, which cannot support a 100+-query benchmark. The workspace content is fully defined in the
seed modules, so we rebuild the threads from those and provide local recall + thread-fetch
primitives that MIRROR RTS's behavior — score a thread by its PARENT text (RTS matches parents, not
replies) and return the top-K. Injected into the real `recall_memories` / `recall_arc`, the
benchmark exercises the ACTUAL synthesis engine; only the retrieval *source* differs from production.
"""

from __future__ import annotations

import collections
import math
import re

from deja.arc import _STOP
from deja.models import Hit
from scripts.seed_arcs import ARCS, NOISE, OBSOLETE_MARKERS
from scripts.seed_data import SEEDS

_WORD = re.compile(r"[a-z0-9]{3,}")
_MARKER = re.compile(r"\s*‹deja-[^›]*›")


def _clean(t: str) -> str:
    return _MARKER.sub("", t or "").strip()


def _build_threads() -> list[dict]:
    """The live workspace: the multi-author arcs + noise, plus the still-live single decisions
    (the obsolete Phase-5 singles that were deleted from Slack are excluded)."""
    threads: list[dict] = []
    ts = 1_000_000.0
    for t in [th for arc in ARCS.values() for th in arc] + list(NOISE):
        ts += 1
        threads.append(
            {
                "channel": t.channel,
                "ts": f"{ts:.6f}",
                "permalink": f"local://{t.marker}",
                "parent_text": _clean(t.parent.text),
                "parent_author": t.parent.author,
                "replies": [(r.author, r.text) for r in t.replies],
            }
        )
    for s in SEEDS:
        if s.marker in OBSOLETE_MARKERS:
            continue  # deleted from the live workspace (replaced by the multi-author arc)
        ts += 1
        threads.append(
            {
                "channel": s.channel,
                "ts": f"{ts:.6f}",
                "permalink": f"local://{s.marker}",
                "parent_text": _clean(s.parent),
                "parent_author": "teammate",
                "replies": [("teammate", r) for r in s.replies],
            }
        )
    return threads


_THREADS = _build_threads()
_BY_TS = {t["ts"]: t for t in _THREADS}

# Document frequency over the parent texts, for IDF weighting — mirrors how a relevance search ranks
# by salient (rare) terms, not common ones. Without it a query would match any thread sharing a
# filler word ("migrate", "should"), which RTS does not do.
_N = len(_THREADS)
_DF: collections.Counter = collections.Counter()
for _t in _THREADS:
    for _w in set(_WORD.findall(_t["parent_text"].lower())) - _STOP:
        _DF[_w] += 1


def _idf(w: str) -> float:
    return math.log((_N + 1) / (_DF.get(w, 0) + 0.5))


def _content(text: str) -> set[str]:
    return {w for w in _WORD.findall((text or "").lower())} - _STOP


# Relevance floor (fraction of the query's IDF weight the thread must cover) — approximates RTS's
# selectivity. Without it, a lexical mirror over-matches on an incidental filler word ("time" in
# "focus time", "call" in "final call") and would fake a decision on a non-decision question.
_MIN_SCORE = 0.4


def local_recall(
    query, *, token=None, limit=5, channel_types=None, exclude_ts=None
) -> list[Hit]:
    """RTS mirror: rank threads by IDF-weighted overlap of their PARENT text with the query, and —
    like RTS — return nothing when the query's most salient term isn't in the workspace at all (so a
    never-discussed topic surfaces no thread, rather than matching on a filler word)."""
    qwords = _content(query)
    in_corpus = [w for w in qwords if _DF.get(w, 0) > 0]
    if not in_corpus:
        return []  # nothing the query is about exists here — RTS would return nothing
    salient = max(
        in_corpus, key=_idf
    )  # the query's most distinctive term that DOES occur

    denom = sum(_idf(w) for w in qwords) or 1.0
    scored: list[tuple[float, dict]] = []
    for t in _THREADS:
        if t["ts"] == exclude_ts:
            continue
        tw = _content(t["parent_text"])
        if salient not in tw:
            continue  # a thread must share the salient term to be relevant
        score = round(sum(_idf(w) for w in qwords & tw) / denom, 4)
        if score >= _MIN_SCORE:
            scored.append((score, t))
    scored.sort(key=lambda x: (-x[0], -len(x[1]["replies"])))
    return [
        Hit(
            reply_count=len(t["replies"]),
            permalink=t["permalink"],
            channel=t["channel"],
            channel_id=t["channel"],
            author=t["parent_author"],
            author_id=t["parent_author"],
            ts=t["ts"],
            snippet=t["parent_text"],
            score=sc,
        )
        for sc, t in scored[:limit]
    ]


async def local_thread(client, channel_id, ts) -> list[dict]:
    """Mirror conversations.replies over the snapshot: parent + replies as message dicts."""
    t = _BY_TS.get(ts)
    if not t:
        return []
    msgs = [{"ts": ts, "text": t["parent_text"], "username": t["parent_author"]}]
    for author, text in t["replies"]:
        msgs.append({"text": text, "username": author, "subtype": "bot_message"})
    return msgs
