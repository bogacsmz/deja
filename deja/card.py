"""The Déjà memory card — Block Kit.

Compact, vertical, scannable: header + what-was-searched + the found message (channel/author/date
+ quote) + 'what happened next' (the thread's decision) + actions + a privacy line. Pure builder,
no I/O, so it's easy to validate and unit-test.
"""

from __future__ import annotations

import json

from deja.arc import DecisionArc
from deja.conflict import ConflictWarning
from deja.models import Hit

# Privacy + AI-transparency footer (Slack agent-design: label AI-generated content).
_FOOTER = ":robot_face: AI-generated summary · :lock: only channels you can access · powered by Legibright"

# Decision-state-machine icons for the timeline.
_STATE_ICON = {"proposed": "💡", "adopted": "✅", "reversed": "↩️", "revived": "🔄"}


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
                    "text": ":lock: Only searches channels you can access · powered by Legibright",
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
    return json.dumps(
        {
            "q": query[:120],
            "topic": arc.topic[:120],
            "decision": arc.standing_decision[:400],
            "owner": arc.owner[:80],
            "at": arc.decided_at[:24],
            "n": arc.times_discussed,
            "url": arc.sources[-1] if arc.sources else "",
        },
        ensure_ascii=False,
    )


def build_arc_card(
    query: str, arc: DecisionArc, warning: ConflictWarning | None = None
) -> tuple[list[dict], str]:
    """Block Kit card for a synthesized decision ARC: standing decision + owner + times-discussed +
    a sourced timeline, or an honest INCONCLUSIVE state, plus an optional contradiction warning."""
    settled = not arc.inconclusive
    header = (
        "⏳ Déjà vu — your team already decided this"
        if settled
        else "⏳ Déjà vu — your team has been here before"
    )
    blocks: list[dict] = [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": header, "emoji": True},
        },
        {
            "type": "context",
            "elements": [{"type": "mrkdwn", "text": f":mag: searched  _{query}_"}],
        },
    ]

    if warning:
        blocks.append(
            {"type": "section", "text": {"type": "mrkdwn", "text": warning.text}}
        )

    if settled:
        who = f" · _{arc.owner}_" if arc.owner else ""
        when = f" · {arc.decided_at}" if arc.decided_at else ""
        blocks.append(
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f":white_check_mark: *Standing decision*{who}{when}\n{_quote(arc.standing_decision)}",
                },
            }
        )
        if arc.is_recurring:
            blocks.append(
                {
                    "type": "context",
                    "elements": [
                        {
                            "type": "mrkdwn",
                            "text": f":repeat: This has come up *{arc.times_discussed}×* before",
                        }
                    ],
                }
            )
    else:
        blocks.append(
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f":thinking_face: *Inconclusive* — discussed *{arc.times_discussed}×*, "
                    "but no clear decision was recorded. I won't invent one.",
                },
            }
        )

    blocks.append({"type": "divider"})
    lines = []
    for e in arc.timeline[:7]:
        icon = _STATE_ICON.get(e.state, "")
        mark = f"{icon} " if icon else ""
        date = f"`{e.date}` " if e.date else ""
        link = f"  <{e.permalink}|↗>" if e.permalink else ""
        lines.append(
            f"{date}*#{e.channel}* · _{e.author}_ — {mark}{_short(e.summary)}{link}"
        )
    blocks.append(
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": ":clock3: *Timeline*\n" + "\n".join(lines),
            },
        }
    )

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
    if arc.sources:
        actions.append(
            {
                "type": "button",
                "action_id": "deja_open_thread",
                "text": {"type": "plain_text", "text": "🔗 Open thread", "emoji": True},
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
    text = " ".join((text or "").split())
    return text if len(text) <= n else text[:n].rstrip() + "…"
