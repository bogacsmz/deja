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
                    summary=_short(decision or _strip_date(source)),
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


async def recall_arc(
    query: str, *, limit: int = 8, exclude_ts: str | None = None
) -> DecisionArc | None:
    """Gather the topic's threads via recall_memories and synthesize the arc."""
    from deja.memory import recall_memories

    result = await recall_memories(query, limit=limit)
    memories = result.get("memories", [])
    if exclude_ts:
        memories = [m for m in memories if m.get("ts") != exclude_ts]
    return build_arc(query, memories)
