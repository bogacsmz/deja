from logging import Logger

from slack_bolt import Ack
from slack_sdk.web.async_client import AsyncWebClient


async def handle_open_thread(ack: Ack):
    """'🔗 Open source thread' is a URL button — Slack opens the permalink itself; we just ack
    so Slack doesn't show an 'app didn't respond' warning."""
    await ack()


async def handle_not_relevant(
    ack: Ack, body: dict, client: AsyncWebClient, logger: Logger
):
    """'🙅 Not relevant' — collapse the card to a dismissed note and log it (a precision signal
    we can learn from later)."""
    await ack()
    try:
        channel = body["channel"]["id"]
        ts = body["message"]["ts"]
        source = (body.get("actions") or [{}])[0].get("value", "")
        user = (body.get("user") or {}).get("id", "")
        await client.chat_update(
            channel=channel,
            ts=ts,
            text="Déjà — dismissed",
            blocks=[
                {
                    "type": "context",
                    "elements": [
                        {
                            "type": "mrkdwn",
                            "text": ":wave: Dismissed — I'll stay quiet on this one. "
                            "_(noted to improve what I surface)_",
                        }
                    ],
                }
            ],
        )
        logger.info(
            f"deja_not_relevant: dismissed by {user} in {channel} (source={source})"
        )
    except Exception as e:
        logger.exception(f"Failed to handle 'not relevant': {e}")
