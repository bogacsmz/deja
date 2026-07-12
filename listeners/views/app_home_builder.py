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


def _short_topic(t: str, n: int = 26) -> str:
    t = " ".join((t or "Decision").split())
    return t if len(t) <= n else t[: n - 1].rstrip() + "…"


def _metrics_blocks() -> list[dict]:
    """The hero: how often the team re-opens settled decisions — Déjà as an organizational-health
    signal, not just a memory. Real numbers from the store; honest empty state when there's too
    little history to claim a pattern."""
    from deja.store import relitigation_stats

    s = relitigation_stats()
    if s["count"] < 1:
        return [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "🔁  *No decisions have come back up yet.*\nI'll surface the re-litigation pattern here as your team revisits settled calls.",
                },
            }
        ]
    top = s["top"][0]
    # Only the `header` block renders large in Block Kit — put the NUMBER there so it's the hero,
    # with the supporting stats quiet underneath.
    blocks: list[dict] = [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": f"🔁 {s['count']} decisions keep coming back",
                "emoji": True,
            },
        },
        {
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": f"*{s['total']}×* raised  ·  *{s['channels']}* channels  ·  "
                    f"most-repeated: *{top.get('topic', '')}* ({top.get('times_discussed', 0)}×)",
                }
            ],
        },
    ]
    btns = []
    for i, d in enumerate(s["top"]):
        b: dict = {
            "type": "button",
            "action_id": f"deja_open_metric_{i}",  # must be unique within the view
            "text": {
                "type": "plain_text",
                "text": f"🔁 {_short_topic(d.get('topic', ''))} · {d.get('times_discussed', 0)}×",
                "emoji": True,
            },
        }
        if (d.get("url") or "").startswith("http"):
            b["url"] = d["url"]
        btns.append(b)
    if btns:
        blocks.append({"type": "actions", "elements": btns})
    return blocks


def _recent_decisions_blocks() -> list[dict]:
    """The heart of Home: the decisions the team has on record, each row linking to its source thread.
    Reads the canonical store (seeded from the team's arcs + grown by the 💾 Save button)."""
    from deja.store import decision_headline, decision_rationale, list_decisions

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

    for i, d in enumerate(decisions[:5]):
        icon = d.get("icon") or "✅"
        headline = d.get("headline") or decision_headline(d.get("decision", ""))
        n = d.get("times_discussed", 0)
        # line 2: attribution + how often it's come up (no "1×" for a one-off)
        meta = "  ·  ".join(
            x
            for x in (
                d.get("owner", ""),
                d.get("at", ""),
                f"#{d['channel']}" if d.get("channel") else "",
                f"_discussed {n}×_" if n >= 2 else "",
            )
            if x
        )
        # line 3: the RATIONALE — the 'why', not a restatement of the headline
        rationale = decision_rationale(d.get("decision", ""))
        text = f"{icon}  *{headline}*"
        if meta:
            text += f"\n{meta}"
        if rationale:
            text += f"\n_“{rationale}”_"
        row: dict = {"type": "section", "text": {"type": "mrkdwn", "text": text}}
        if (d.get("url") or "").startswith("http"):
            row["accessory"] = {
                "type": "button",
                "action_id": f"deja_open_dec_{i}",  # must be unique within the view
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
