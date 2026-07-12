"""Déjà's App Home — the jury's first click, so it's a real product surface, not a doc page:
a header, the team's *recent decisions* (each a clickable link to its thread), a copy-paste
*Try these*, and a quiet footer. A reserved metrics slot sits up top for the Part-2 "circles" block
so adding it later won't mean rewriting Home."""

from __future__ import annotations

# Example prompts the jury can paste straight into a channel (no @mention needed — Déjà is ambient).
_TRY_THESE = (
    "should we move to usage-based pricing?",
    "did we build or buy auth?",
    "what's our observability stack?",
    "should we write an RFC for the new API?",
    "let's migrate to Temporal for the new pipeline",
)


def _metrics_blocks() -> list[dict]:
    """Reserved for Part 2 (the 'decisions circled back' metric). Empty for now — kept as its own
    function and slot so adding the block later doesn't touch the rest of Home."""
    return []


def _recent_decisions_blocks() -> list[dict]:
    """The heart of Home: the decisions the team has on record, each row linking to its source thread.
    Reads the canonical store (seeded from the team's arcs + grown by the 💾 Save button)."""
    from deja.store import decision_headline, list_decisions

    decisions = list_decisions()
    blocks: list[dict] = [
        {"type": "section", "text": {"type": "mrkdwn", "text": "*Recent decisions*"}}
    ]
    if not decisions:
        blocks.append(
            {
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": "No decisions recorded yet — I'll pick them up as your team talks.",
                    }
                ],
            }
        )
        return blocks

    for d in decisions[:5]:
        icon = d.get("icon") or "✅"
        headline = d.get("headline") or decision_headline(d.get("decision", ""))
        meta = "  ·  ".join(
            x
            for x in (
                f"_{d['owner']}_" if d.get("owner") else "",
                d.get("at", ""),
                f"#{d['channel']}" if d.get("channel") else "",
            )
            if x
        )
        quote = _quote(d.get("decision", ""))
        row: dict = {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"{icon}  *{headline}*\n{meta}\n_{quote}_" if meta else f"{icon}  *{headline}*\n_{quote}_",
            },
        }
        if (d.get("url") or "").startswith("http"):
            row["accessory"] = {
                "type": "button",
                "action_id": "deja_open_thread",
                "text": {"type": "plain_text", "text": "Open ↗", "emoji": True},
                "url": d["url"],
            }
        blocks.append(row)
    return blocks


def _try_these_blocks() -> list[dict]:
    """Copy-paste onboarding — the jury starts here."""
    fenced = "```\n" + "\n".join(_TRY_THESE) + "\n```"
    return [
        {"type": "section", "text": {"type": "mrkdwn", "text": "*Try these*"}},
        {"type": "section", "text": {"type": "mrkdwn", "text": fenced}},
        {
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": "Type any of these in a channel I'm in — no need to mention me.",
                }
            ],
        },
    ]


def _footer_blocks() -> list[dict]:
    return [
        {
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": ":lock: Only searches channels you can access   ·   :robot_face: AI-generated summaries   ·   powered by Legibright",
                }
            ],
        }
    ]


def _quote(text: str, n: int = 140) -> str:
    text = " ".join((text or "").split())
    return text if len(text) <= n else text[:n].rstrip() + "…"


def build_app_home_view(
    install_url: str | None = None, is_connected: bool = False
) -> dict:
    """Build Déjà's App Home tab. (install/connected args kept for the scaffold's opened handler.)"""
    blocks = [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": "🕰️ Déjà — your team's decision memory",
                "emoji": True,
            },
        },
        {
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": "I surface decisions your team already made — _before you make them again._",
                }
            ],
        },
        *_metrics_blocks(),
        {"type": "divider"},
        *_recent_decisions_blocks(),
        {"type": "divider"},
        *_try_these_blocks(),
        {"type": "divider"},
        *_footer_blocks(),
    ]
    return {"type": "home", "blocks": blocks}
