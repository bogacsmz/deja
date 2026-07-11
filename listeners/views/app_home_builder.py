def _digest_blocks() -> list[dict]:
    """The saved-decision digest: recent decisions + how many were circled back this week."""
    from deja.store import count_saved_since, list_decisions

    decisions = list_decisions()
    this_week = count_saved_since(7)
    blocks: list[dict] = [
        {"type": "divider"},
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": ":card_index_dividers: *Saved decisions*",
            },
        },
    ]
    if not decisions:
        blocks.append(
            {
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": "Nothing saved yet — hit *💾 Save decision* on a Déjà card to build the log.",
                    }
                ],
            }
        )
        return blocks
    blocks.append(
        {
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": f":repeat: *{this_week}* decision(s) circled back this week",
                }
            ],
        }
    )
    for d in decisions[:5]:
        owner = f" · _{d['owner']}_" if d.get("owner") else ""
        when = f" · {d['at']}" if d.get("at") else ""
        link = f"  <{d['url']}|↗>" if d.get("url") else ""
        blocks.append(
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f":white_check_mark: *{d.get('topic', 'Decision')}*{owner}{when}\n{d.get('decision', '')}{link}",
                },
            }
        )
    return blocks


def build_app_home_view(
    install_url: str | None = None, is_connected: bool = False
) -> dict:
    """Build Déjà's App Home tab — what it is, the saved-decision digest, how it works, privacy.

    (install/connected args kept for compatibility with the scaffold's app_home_opened handler.)
    """
    blocks = [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": "⏳ Déjà — your team's memory",
                "emoji": True,
            },
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": (
                    "When a decision, claim, or proposal comes up in a channel, I quietly surface "
                    "the *concrete past thread* your team already had on it — so nobody re-litigates "
                    "what was already discussed and decided."
                ),
            },
        },
        *_digest_blocks(),
        {"type": "divider"},
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": (
                    "*How it works*\n"
                    "1️⃣  You post something like _“should we migrate to Temporal?”_\n"
                    "2️⃣  I search your history and check whether it was discussed before\n"
                    "3️⃣  If it was, I drop a *memory card* in-thread — the message, the decision, "
                    "and a link to the source"
                ),
            },
        },
        {
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": "Add me to a channel and I start listening. Mention me (`@Déjà …`) to ask directly.",
                }
            ],
        },
        {"type": "divider"},
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": (
                    ":lock: *Privacy*\nI only ever search channels *you* can already access — the "
                    "search runs on your behalf, permission-aware. I never widen your reach."
                ),
            },
        },
        {
            "type": "context",
            "elements": [{"type": "mrkdwn", "text": "powered by Legibright"}],
        },
    ]
    return {"type": "home", "blocks": blocks}
