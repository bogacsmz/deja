"""The Déjà memory card — Block Kit.

Compact, vertical, scannable: header + what-was-searched + the found message (channel/author/date
+ quote) + 'what happened next' (the thread's decision) + actions + a privacy line. Pure builder,
no I/O, so it's easy to validate and unit-test.
"""

from __future__ import annotations

import json
import re

from deja.arc import DecisionArc
from deja.conflict import ConflictWarning
from deja.models import Hit

# Privacy + AI-transparency footer (Slack agent-design: label AI-generated content).
_FOOTER = ":robot_face: AI-generated summary · :lock: only channels this app can access · powered by Legibright"

# ONE consistent icon language for the decision state machine (used by the card + App Home).
_STATE_ICON = {"proposed": "💡", "adopted": "✅", "reversed": "↩️", "revived": "🔁"}


def _open_accessory(url: str, action_id: str) -> dict | None:
    """A native URL button — the ONLY reliably clickable way to link a Slack row to a thread. Inline
    `<url|↗>` mrkdwn links silently break on the `&` in Slack permalinks; a button's `url` does not.
    `action_id` must be UNIQUE within the card — Slack rejects a whole view with duplicate ids."""
    if not (url or "").startswith("http"):
        return None
    return {
        "type": "button",
        "action_id": action_id,
        "text": {"type": "plain_text", "text": "Open ↗", "emoji": True},
        "url": url,
    }


def _epoch(ts: str) -> int:
    try:
        return int(float(ts))
    except (TypeError, ValueError):
        return 0


def _author(display: str, user_id: str) -> str:
    return f"<@{user_id}>" if user_id.startswith("U") else f"*{display}*"


def _quote(text: str, limit: int = 300) -> str:
    text = text.strip().replace("\n", " ")
    if len(text) > limit:
        text = text[:limit] + "…"
    return "> " + text


def build_memory_card(
    query: str, hit: Hit, decision: tuple[str, str] | None
) -> tuple[list[dict], str]:
    """Return (blocks, fallback_text) for a recalled thread."""
    when = (
        f"<!date^{_epoch(hit.ts)}^{{date_short_pretty}}|earlier>"
        if _epoch(hit.ts)
        else "earlier"
    )

    blocks: list[dict] = [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": "⏳ Déjà vu — your team already discussed this",
                "emoji": True,
            },
        },
        {
            "type": "context",
            "elements": [{"type": "mrkdwn", "text": f":mag: searched  _{query}_"}],
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*#{hit.channel}* · {_author(hit.author, hit.author_id)} · {when}\n"
                f"{_quote(hit.snippet)}",
            },
        },
    ]

    if decision:
        d_text, d_user = decision
        by = f"  — {_author('', d_user)}" if d_user.startswith("U") else ""
        blocks.append(
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f":thread: *What happened next{by}:*\n{_quote(d_text)}",
                },
            }
        )

    blocks.append(
        {
            "type": "actions",
            "elements": [
                {
                    "type": "button",
                    "action_id": "deja_open_thread",
                    "style": "primary",
                    "text": {
                        "type": "plain_text",
                        "text": "🔗 Open source thread",
                        "emoji": True,
                    },
                    "url": hit.permalink,
                },
                {
                    "type": "button",
                    "action_id": "deja_not_relevant",
                    "text": {
                        "type": "plain_text",
                        "text": "🙅 Not relevant",
                        "emoji": True,
                    },
                    "value": hit.permalink,
                },
            ],
        }
    )
    blocks.append(
        {
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": ":lock: Only searches channels this app can access · powered by Legibright",
                }
            ],
        }
    )

    fallback = (
        f"Déjà vu — your team already discussed “{query}”. Source: {hit.permalink}"
    )
    return blocks, fallback


def _save_value(query: str, arc: DecisionArc) -> str:
    """Compact payload the '💾 Save decision' button hands to its action handler (< 2000 chars)."""
    standing = next(
        (
            e
            for e in reversed(arc.timeline)
            if e.state in ("adopted", "reversed") and e.permalink
        ),
        None,
    )
    return json.dumps(
        {
            "q": query[:120],
            "topic": arc.topic[:120],
            "decision": arc.standing_decision[:400],
            "owner": arc.owner[:80],
            "at": arc.decided_at[:24],
            "channel": (standing.channel if standing else "")[:80],
            "icon": _STATE_ICON.get(standing.state if standing else "adopted", "✅"),
            "n": arc.times_discussed,
            "url": arc.sources[-1] if arc.sources else "",
        },
        ensure_ascii=False,
    )


def _ask_value(arc: DecisionArc, owner_uid: str) -> str:
    """Payload the 'Ask the decision owner' button hands to its handler."""
    return json.dumps(
        {
            "uid": owner_uid,
            "owner": arc.owner[:80],
            "at": arc.decided_at[:24],
            "n": arc.times_discussed,
            "dec": _short(arc.standing_decision, 150),
        },
        ensure_ascii=False,
    )


def build_arc_card(
    query: str,
    arc: DecisionArc,
    warning: ConflictWarning | None = None,
    owner_uid: str = "",
    agent_conflict: bool = False,
) -> tuple[list[dict], str]:
    """Block Kit card for a synthesized decision ARC. Visual hierarchy: the standing decision is the
    HERO (top, bold), the timeline is secondary (each row a clickable link to its thread), and the
    meta/privacy footer is the quietest. Honest INCONCLUSIVE state when there's no decision.

    `agent_conflict=True` reframes the header for Mode B — an agent proposal caught against a standing
    decision reads as a GUARDRAIL ("Conflicts with a standing decision"), not a memory jog."""
    settled = not arc.inconclusive
    if settled and agent_conflict:
        header = "⚠️ Conflicts with a standing decision"
    elif settled:
        header = "⏳ Déjà vu — your team already decided this"
    else:
        header = "⏳ Déjà vu — you've been here before"
    blocks: list[dict] = [
        {"type": "header", "text": {"type": "plain_text", "text": header, "emoji": True}}
    ]

    if warning:
        blocks.append(
            {"type": "section", "text": {"type": "mrkdwn", "text": warning.text}}
        )

    # HERO — the standing decision, the single most prominent thing on the card.
    if settled:
        standing = next(
            (
                e
                for e in reversed(arc.timeline)
                if e.state in ("adopted", "reversed") and e.permalink
            ),
            None,
        )
        hero_icon = _STATE_ICON.get(standing.state if standing else "adopted", "✅")
        blocks.append(
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"{hero_icon}  *{_short(arc.standing_decision, 260)}*",
                },
                "accessory": _open_accessory(
                    arc.sources[-1] if arc.sources else "", "deja_open_hero"
                ),
            }
        )
        meta = "  ·  ".join(
            x
            for x in (
                f"_{arc.owner}_" if arc.owner else "",
                arc.decided_at,
                f":repeat: discussed *{arc.times_discussed}×*"
                if arc.is_recurring
                else "",
                f":mag: _{query}_",
            )
            if x
        )
        blocks.append(
            {"type": "context", "elements": [{"type": "mrkdwn", "text": meta}]}
        )
    else:
        blocks.append(
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f":thinking_face:  *No decision on record* — discussed *{arc.times_discussed}×*, "
                    "but the team never landed it. I won't invent one.",
                },
            }
        )
        blocks.append(
            {
                "type": "context",
                "elements": [{"type": "mrkdwn", "text": f":mag: _{query}_"}],
            }
        )

    # TIMELINE — secondary. One section per event so each row carries its OWN clickable thread button.
    blocks.append({"type": "divider"})
    blocks.append(
        {
            "type": "context",
            "elements": [{"type": "mrkdwn", "text": ":clock3: *How it unfolded*"}],
        }
    )
    for i, e in enumerate(arc.timeline[:5]):
        icon = _STATE_ICON.get(e.state, "•")
        date = f"`{e.date}`  " if e.date else ""
        row = {
            "type": "section",
            "block_id": f"deja_tl_{i}",
            "text": {
                "type": "mrkdwn",
                "text": f"{icon}  {date}*#{e.channel}* · _{e.author}_\n{_short(e.summary, 180)}",
            },
        }
        acc = _open_accessory(e.permalink, f"deja_open_tl_{i}")
        if acc:
            row["accessory"] = acc
        blocks.append(row)

    # ACTIONS — Save (settled only) · Open source · Not relevant. Consistent order + alignment.
    blocks.append({"type": "divider"})
    actions: list[dict] = []
    if settled:
        actions.append(
            {
                "type": "button",
                "action_id": "deja_save_decision",
                "style": "primary",
                "text": {
                    "type": "plain_text",
                    "text": "💾 Save decision",
                    "emoji": True,
                },
                "value": _save_value(query, arc),
            }
        )
    # Coordination: ping the person who made the call — but only if we resolved them to a real user
    # (owner_uid empty → hide the button, never a fake @-mention).
    if settled and owner_uid:
        actions.append(
            {
                "type": "button",
                "action_id": "deja_ask_owner",
                "text": {
                    "type": "plain_text",
                    "text": "🗣️ Ask the decision owner",
                    "emoji": True,
                },
                "value": _ask_value(arc, owner_uid),
            }
        )
    if arc.sources:
        actions.append(
            {
                "type": "button",
                "action_id": "deja_open_src",
                "text": {
                    "type": "plain_text",
                    "text": "🔗 Open source thread",
                    "emoji": True,
                },
                "url": arc.sources[-1],
            }
        )
    actions.append(
        {
            "type": "button",
            "action_id": "deja_not_relevant",
            "text": {"type": "plain_text", "text": "🙅 Not relevant", "emoji": True},
            "value": arc.sources[-1] if arc.sources else query,
        }
    )
    blocks.append({"type": "actions", "elements": actions})
    blocks.append(
        {"type": "context", "elements": [{"type": "mrkdwn", "text": _FOOTER}]}
    )

    fallback = (
        f"Déjà — standing decision on “{query}”: {arc.standing_decision}"
        if settled
        else f"Déjà — “{query}” was discussed {arc.times_discussed}× but is inconclusive."
    )
    return blocks, fallback


def _short(text: str, n: int = 160) -> str:
    """Trim to ≤ n chars, ending on a SENTENCE boundary when there's one past the halfway mark
    (no ellipsis then — it already ends in . ! ?); otherwise on a WORD boundary with an ellipsis.
    Never cuts mid-word."""
    text = " ".join((text or "").split())
    if len(text) <= n:
        return text
    window = text[:n]
    ends = list(re.finditer(r"[.!?](?=\s|$)", window))
    if ends and ends[-1].end() >= n * 0.5:
        return window[: ends[-1].end()].strip()
    return window.rsplit(" ", 1)[0].rstrip(" ,;—-") + "…"
