"""Decision-arc synthesis — turn N threads on the same topic into one decision record.

`recall` surfaces individual threads. When a topic was discussed repeatedly across months, this
stitches those threads into a chronological **arc**: a timeline (channel · author · date), the
**standing decision** (the most recent one), its **owner**, how many times it has come up, and —
the honesty invariant — **INCONCLUSIVE** when there is discussion but no clear decision. Every line
is sourced (permalink). Degrades cleanly to a single event when a topic was discussed only once.

Pure/data only — no Slack calls — so it is fully hermetic to test. `recall_arc()` is the async
convenience that feeds it from `recall_memories`.
"""

from __future__ import annotations

import datetime as dt
import re
from dataclasses import dataclass

_MONTHS = {
    m: i
    for i, m in enumerate(
        [
            "jan",
            "feb",
            "mar",
            "apr",
            "may",
            "jun",
            "jul",
            "aug",
            "sep",
            "oct",
            "nov",
            "dec",
        ],
        start=1,
    )
}
# Seeded threads carry the intended date as a leading "[Mon DD]" because Slack messages can't be
# back-dated; the timeline orders + displays by that content date rather than the (all-recent) ts.
_DATE_RE = re.compile(r"\[\s*([A-Za-z]{3,9})\s+(\d{1,2})\s*\]")


@dataclass(frozen=True)
class ArcEvent:
    ts: str
    date: str  # human date, e.g. "Apr 23"
    channel: str
    author: str
    summary: str  # one short line (the decision if there is one, else the proposal)
    permalink: str
    is_decision: bool


@dataclass(frozen=True)
class DecisionArc:
    topic: str
    timeline: tuple[ArcEvent, ...]
    standing_decision: str  # "" when inconclusive
    owner: str  # author of the standing decision ("" when inconclusive)
    decided_at: str  # date of the standing decision ("" when inconclusive)
    times_discussed: int  # distinct threads on the topic
    sources: tuple[str, ...]  # permalinks, chronological
    confidence: str  # "high" | "inconclusive"

    @property
    def inconclusive(self) -> bool:
        return self.confidence == "inconclusive"

    @property
    def is_recurring(self) -> bool:
        return self.times_discussed >= 2


def _fmt_date(ts: str) -> str:
    try:
        return dt.datetime.fromtimestamp(float(ts)).strftime("%b %d").replace(" 0", " ")
    except (TypeError, ValueError):
        return ""


def _short(text: str, n: int = 90) -> str:
    t = " ".join((text or "").split())
    return t if len(t) <= n else t[:n].rstrip() + "…"


def _ts_float(ts: str) -> float:
    try:
        return float(ts)
    except (TypeError, ValueError):
        return 0.0


def _content_date(text: str) -> tuple[tuple[int, int], str] | None:
    """Parse a leading '[Mon DD]' → ((month, day), 'Mon DD'). None if absent/unrecognized."""
    m = _DATE_RE.search(text or "")
    if not m:
        return None
    mon = _MONTHS.get(m.group(1)[:3].lower())
    if not mon:
        return None
    return (mon, int(m.group(2))), f"{m.group(1)[:3].title()} {int(m.group(2))}"


def _strip_date(text: str) -> str:
    return _DATE_RE.sub("", text or "", count=1).strip()


def build_arc(topic: str, memories: list[dict]) -> DecisionArc | None:
    """Synthesize a decision arc from recall memories (each memory is one thread). None if empty.

    Honesty invariant: if threads exist but none carries a clear decision (`what_happened_next`),
    the arc is returned with confidence='inconclusive' and no standing decision — never a fake one.
    """
    if not memories:
        return None

    scored: list[tuple[tuple, ArcEvent]] = []
    for m in memories:
        decision = (m.get("what_happened_next") or "").strip()
        source = m.get("source_message", "")
        ts = str(m.get("ts", ""))
        cd = _content_date(source)
        if cd:  # dated arc thread: order + show by its content date
            sort_key, date = (0, *cd[0]), cd[1]
        else:  # undated (legacy single / noise): fall back to post time
            sort_key, date = (1, _ts_float(ts)), _fmt_date(ts)
        scored.append(
            (
                sort_key,
                ArcEvent(
                    ts=ts,
                    date=date,
                    channel=m.get("channel", ""),
                    author=m.get("author", ""),
                    summary=_short(decision or _strip_date(source), 220),
                    permalink=m.get("permalink", ""),
                    is_decision=bool(decision),
                ),
            )
        )
    scored.sort(key=lambda x: x[0])  # chronological by content date (ts fallback)
    events = [e for _, e in scored]

    decisions = [e for e in events if e.is_decision]
    if decisions:
        standing = decisions[-1]  # the most recent decision is the one in force
        confidence, standing_decision = "high", standing.summary
        owner, decided_at = standing.author, standing.date
    else:
        confidence, standing_decision, owner, decided_at = "inconclusive", "", "", ""

    return DecisionArc(
        topic=topic,
        timeline=tuple(events),
        standing_decision=standing_decision,
        owner=owner,
        decided_at=decided_at,
        times_discussed=len(events),
        sources=tuple(e.permalink for e in events if e.permalink),
        confidence=confidence,
    )


def as_record(arc: DecisionArc | None) -> dict:
    """The decision record as a plain dict — the structured contract an external agent consumes."""
    if arc is None:
        return {
            "found": False,
            "confidence": "none",
            "times_discussed": 0,
            "timeline": [],
        }
    return {
        "found": True,
        "topic": arc.topic,
        "standing_decision": arc.standing_decision,
        "owner": arc.owner,
        "decided_at": arc.decided_at,
        "times_discussed": arc.times_discussed,
        "confidence": arc.confidence,
        "inconclusive": arc.inconclusive,
        "timeline": [
            {
                "date": e.date,
                "channel": e.channel,
                "author": e.author,
                "summary": e.summary,
                "permalink": e.permalink,
                "is_decision": e.is_decision,
            }
            for e in arc.timeline
        ],
        "sources": list(arc.sources),
    }


def render_record(arc: DecisionArc | None) -> str:
    """Human/LLM-readable rendering of the decision record — leads with the standing decision (or
    INCONCLUSIVE), then the sourced timeline. This is what the Slackbot's LLM relays."""
    if arc is None:
        return "No prior discussion found."
    lines: list[str] = []
    if arc.inconclusive:
        lines.append(
            f"⚠️ INCONCLUSIVE — this was discussed {arc.times_discussed}× but no clear decision "
            "was recorded, so I won't claim one."
        )
    else:
        who = f" (owner: {arc.owner}, {arc.decided_at})" if arc.owner else ""
        lines.append(f"Standing decision{who}: {arc.standing_decision}")
        if arc.is_recurring:
            lines.append(f"This has come up {arc.times_discussed}× before.")
    lines.append("")
    lines.append("Timeline:")
    for e in arc.timeline:
        lead = "→ DECISION: " if e.is_decision else "• "
        date = f"{e.date} " if e.date else ""
        lines.append(f"  {date}#{e.channel} ({e.author}) {lead}{e.summary}")
        if e.permalink:
            lines.append(f"    {e.permalink}")
    return "\n".join(lines)


_STOP = frozenset(
    "the a an and or of to for in on our we you they it is are was were be been do does did "
    "should would could can will may might must have has had this that these those with without "
    "about into from as at by new good fit use using just get got keep back go going switch move "
    "moving what when where why how which who vs versus still".split()
)
_ANCHOR_WORD = re.compile(
    r"[A-Za-z][A-Za-z0-9]{2,}"
)  # content words, ≥3 chars (keeps "RFC")


def _topic_anchors(query: str, memories: list[dict], k: int = 2) -> list[str]:
    """Topic terms shared between the query and the recalled threads — the words to expand on.

    General: the user's own content words that actually show up in what came back. No case-specific
    keywords. Longer terms first (a light distinctiveness proxy: 'temporal' over 'pipeline' ties, but
    both are kept and merged, so the decision-bearing sibling gets pulled in either way)."""
    qwords = {w.lower() for w in _ANCHOR_WORD.findall(query)} - _STOP
    text = " ".join(
        f"{m.get('source_message', '')} {m.get('what_happened_next') or ''}"
        for m in memories
    ).lower()
    twords = set(_ANCHOR_WORD.findall(text))
    shared = sorted(qwords & twords, key=lambda w: (-len(w), w))
    return shared[:k]


def _lexical_anchors(query: str, memories: list[dict], k: int = 3) -> list[str]:
    """RTS-only expansion terms: the query's own distinctive words (longest first), preferring those
    that also appear in what came back. This is what makes retrieval robust to the judge's phrasing —
    a full phrase RTS misses ('continuous deployment') still resolves via its distinctive word
    ('continuous' → the whole deploy arc)."""
    shared = set(_topic_anchors(query, memories, k=k))
    qwords = sorted(
        {w for w in _ANCHOR_WORD.findall(query.lower())} - _STOP,
        key=lambda w: (-len(w), w),
    )
    ordered = [w for w in qwords if w in shared] + [
        w for w in qwords if w not in shared
    ]
    return ordered[:k]


def _on_topic(m: dict, terms: list[str]) -> bool:
    blob = f"{m.get('source_message', '')} {m.get('what_happened_next') or ''}".lower()
    return any(t.lower() in blob for t in terms)


_SUBJECT_RE = re.compile(
    r"\b([A-Z][A-Za-z0-9]{2,})\b"
)  # capitalized, product-name-ish tokens


def _query_subjects(query: str) -> list[str]:
    """Specific product/proper-noun names in the query (Temporal, Kafka, CockroachDB, Postgres).

    The subject guard: if the question names such a product, the answer must be about THAT product —
    so a query for a never-discussed product ('CockroachDB', 'Kafka') can't be answered with a
    different product's decision after expansion. Descriptive queries ('observability stack') have no
    subject and expand freely."""
    return [t for t in _SUBJECT_RE.findall(query) if t.lower() not in _STOP]


async def _cluster(query, base, terms, limit, recall_fn, thread_fn):
    """Recall each term, merge new threads with `base`, keep on-topic threads, rebuild the arc."""
    from deja.memory import recall_memories

    memories = list(base)
    seen = {m.get("ts") for m in memories}
    for term in terms[:4]:  # bound the extra recall calls
        more = await recall_memories(
            term, limit=limit, recall_fn=recall_fn, thread_fn=thread_fn
        )
        for m in more.get("memories", []):
            if m.get("ts") not in seen:
                memories.append(m)
                seen.add(m.get("ts"))
    memories = [
        m for m in memories if _on_topic(m, terms)
    ]  # stay on the topic, no drift
    return memories, build_arc(query, memories)


async def recall_arc(
    query: str,
    *,
    limit: int = 8,
    exclude_ts: str | None = None,
    recall_fn=None,
    thread_fn=None,
    expand: bool = True,
) -> DecisionArc | None:
    """Gather the topic's threads via recall_memories and synthesize the arc.

    RTS matches a thread's parent text and returns only a few top hits, so a narrow query can pull a
    topic's reopen/proposal thread but miss the sibling that holds the decision. When the first pass
    is inconclusive we expand — in general, not per-case — in two stages:
      1. lexical anchors: the query's own words that appear in what came back (free), then
      2. LLM query expansion: the specific product/vendor names the question is about (closes the
         semantic gap when the team's wording differs from the question's).
    A subject guard keeps a named-product query from being answered with a different product's
    decision, and the honesty invariant (no genuine decision → inconclusive) is untouched.

    `recall_fn`/`thread_fn` inject retrieval + thread-fetch (default: live RTS); the benchmark passes
    local ones to run the same synthesis over a snapshot without the RTS rate limit."""
    from deja.expand import expand_query, keep_specific
    from deja.memory import recall_memories

    base = (
        await recall_memories(
            query, limit=limit, recall_fn=recall_fn, thread_fn=thread_fn
        )
    ).get("memories", [])
    memories, arc = base, build_arc(query, base)

    # Expand when the first pass has no standing decision — it returned a reopen/proposal thread
    # (inconclusive) or nothing (None: the judge's query phrasing shares no full-phrase match).
    if arc is None or arc.inconclusive:
        # Stage 1 — LEXICAL, RTS-only, ALWAYS: re-recall the query's own distinctive words. This is
        # what makes the LIVE path robust to the judge's phrasing (a phrase RTS misses resolves via
        # its distinctive word), without any LLM in the hot path.
        terms = keep_specific(_lexical_anchors(query, base))
        if terms:
            memories, arc = await _cluster(
                query, base, terms, limit, recall_fn, thread_fn
            )
        # Stage 2 — LLM, gated by `expand` (off on the live card path): specific product/vendor
        # entities the question is about, for the semantic gap lexical can't bridge.
        if expand and (arc is None or arc.inconclusive):
            entities = await expand_query(query)
            if entities:
                terms = keep_specific(terms + entities)
                memories, arc = await _cluster(
                    query, base, terms, limit, recall_fn, thread_fn
                )

    # Subject guard: when the query names a specific product, keep ONLY the threads about it and
    # rebuild — so an off-topic thread pulled in by a generic anchor ("migration" → the monorepo
    # decision) can't become the standing decision. If nothing is on the named topic, claim nothing.
    subjects = _query_subjects(query)
    if subjects and arc is not None:
        on_topic = [m for m in memories if _on_topic(m, subjects)]
        memories = on_topic
        arc = build_arc(query, memories) if on_topic else None

    if exclude_ts and arc is not None:
        arc = build_arc(query, [m for m in memories if m.get("ts") != exclude_ts])
    return arc
