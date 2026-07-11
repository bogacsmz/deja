def build_app_home_view(install_url: str | None = None, is_connected: bool = False) -> dict:
    """Build Déjà's App Home tab — what it is, how it works, and the privacy promise.

    (Args kept for compatibility with the scaffold's app_home_opened handler; unused here.)
    """
    blocks = [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": "⏳ Déjà — your team's memory", "emoji": True},
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
            "elements": [{
                "type": "mrkdwn",
                "text": "Add me to a channel and I start listening. Mention me (`@Déjà …`) to ask directly.",
            }],
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
