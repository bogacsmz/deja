import json
from logging import Logger

from slack_bolt import Ack
from slack_sdk.web.async_client import AsyncWebClient

from deja.canvas import write_canvas
from deja.store import list_decisions, save_decision


def _without_save_button(blocks: list[dict]) -> list[dict]:
    """Return the card blocks with the '💾 Save decision' button removed (so it can't be re-clicked),
    dropping the actions block entirely if it becomes empty."""
    out: list[dict] = []
    for b in blocks:
        if b.get("type") == "actions":
            els = [
                e
                for e in b.get("elements", [])
                if e.get("action_id") != "deja_save_decision"
            ]
            if not els:
                continue
            b = {**b, "elements": els}
        out.append(b)
    return out


async def handle_save_decision(
    ack: Ack, body: dict, client: AsyncWebClient, logger: Logger
):
    """'💾 Save decision' — persist the standing decision to the canonical log (the flywheel:
    future recalls + App Home + the team Canvas all read it). The confirmation is EPHEMERAL (only the
    clicker sees it) so Déjà never leaves clutter in the channel; the card just loses its Save button."""
    await ack()
    try:
        value = (body.get("actions") or [{}])[0].get("value", "")
        record = json.loads(value) if value else {}
        user = (body.get("user") or {}).get("id", "")
        save_decision(record, saved_by=user)
        canvas_id = await write_canvas(client, list_decisions())  # best-effort mirror

        channel, ts = body["channel"]["id"], body["message"]["ts"]
        await client.chat_update(
            channel=channel,
            ts=ts,
            blocks=_without_save_button(list(body["message"]["blocks"])),
            text="Déjà — decision saved",
        )
        canvas_note = " · updated the team Canvas" if canvas_id else ""
        topic = record.get("topic") or record.get("q") or "the decision"
        await client.chat_postEphemeral(
            channel=channel,
            user=user,
            text=f":floppy_disk: Saved *{topic}* to the team decision log{canvas_note} — it's on Déjà's App Home now.",
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
    """'🙅 Not relevant' — remove the card entirely, leaving no trace in the channel. A wrong card the
    user rejects should vanish, not linger as a 'dismissed' note. (Logged as a precision signal.)"""
    await ack()
    try:
        channel = body["channel"]["id"]
        ts = body["message"]["ts"]
        source = (body.get("actions") or [{}])[0].get("value", "")
        user = (body.get("user") or {}).get("id", "")
        await client.chat_delete(channel=channel, ts=ts)
        logger.info(
            f"deja_not_relevant: dismissed by {user} in {channel} (source={source})"
        )
    except Exception as e:
        logger.exception(f"Failed to handle 'not relevant': {e}")
