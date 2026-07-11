import json
from logging import Logger

from slack_bolt import Ack
from slack_sdk.web.async_client import AsyncWebClient

from deja.canvas import write_canvas
from deja.store import list_decisions, save_decision


async def handle_save_decision(
    ack: Ack, body: dict, client: AsyncWebClient, logger: Logger
):
    """'💾 Save decision' — persist the standing decision to the canonical log (the flywheel:
    future recalls + App Home + the team Canvas all read it), then confirm on the card."""
    await ack()
    try:
        value = (body.get("actions") or [{}])[0].get("value", "")
        record = json.loads(value) if value else {}
        user = (body.get("user") or {}).get("id", "")
        save_decision(record, saved_by=user)
        canvas_id = await write_canvas(client, list_decisions())  # best-effort mirror

        channel, ts = body["channel"]["id"], body["message"]["ts"]
        blocks = list(body["message"]["blocks"])
        canvas_note = " · updated the team Canvas" if canvas_id else ""
        blocks.append(
            {
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": f":floppy_disk: Saved to the team decision log by <@{user}>{canvas_note}",
                    }
                ],
            }
        )
        await client.chat_update(
            channel=channel, ts=ts, blocks=blocks, text="Déjà — decision saved"
        )
        logger.info(f"deja_save_decision: {record.get('topic')!r} saved by {user}")
    except Exception as e:
        logger.exception(f"Failed to save decision: {e}")


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
