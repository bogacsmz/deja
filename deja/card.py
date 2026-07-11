"""The Déjà memory card — Block Kit.

Compact, vertical, scannable: header + what-was-searched + the found message (channel/author/date
+ quote) + 'what happened next' (the thread's decision) + actions + a privacy line. Pure builder,
no I/O, so it's easy to validate and unit-test.
"""
from __future__ import annotations

from deja.models import Hit


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
    when = f"<!date^{_epoch(hit.ts)}^{{date_short_pretty}}|earlier>" if _epoch(hit.ts) else "earlier"

    blocks: list[dict] = [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": "⏳ Déjà vu — your team already discussed this",
                     "emoji": True},
        },
        {
            "type": "context",
            "elements": [{"type": "mrkdwn", "text": f":mag: searched  _{query}_"}],
        },
        {
            "type": "section",
            "text": {"type": "mrkdwn",
                     "text": f"*#{hit.channel}* · {_author(hit.author, hit.author_id)} · {when}\n"
                             f"{_quote(hit.snippet)}"},
        },
    ]

    if decision:
        d_text, d_user = decision
        by = f"  — {_author('', d_user)}" if d_user.startswith("U") else ""
        blocks.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": f":thread: *What happened next{by}:*\n{_quote(d_text)}"},
        })

    blocks.append({
        "type": "actions",
        "elements": [
            {"type": "button", "action_id": "deja_open_thread", "style": "primary",
             "text": {"type": "plain_text", "text": "🔗 Open source thread", "emoji": True},
             "url": hit.permalink},
            {"type": "button", "action_id": "deja_not_relevant",
             "text": {"type": "plain_text", "text": "🙅 Not relevant", "emoji": True},
             "value": hit.permalink},
        ],
    })
    blocks.append({
        "type": "context",
        "elements": [{"type": "mrkdwn",
                      "text": ":lock: Only searches channels you can access · powered by Legibright"}],
    })

    fallback = f"Déjà vu — your team already discussed “{query}”. Source: {hit.permalink}"
    return blocks, fallback
