import re
from logging import Logger

from slack_bolt.context.async_context import AsyncBoltContext
from slack_bolt.context.say.async_say import AsyncSay
from slack_sdk.web.async_client import AsyncWebClient

from deja.respond import recall_card

_MENTION = re.compile(r"<@[A-Z0-9]+>")


async def handle_app_mentioned(
    client: AsyncWebClient,
    context: AsyncBoltContext,
    event: dict,
    logger: Logger,
    say: AsyncSay,
):
    """Explicit trigger: @Déjà <something> -> surface the past thread as a memory card.

    Follows Slack's agent-design guidance: a live status message ('Searching your workspace…' ->
    'Found N threads…' -> 'Reconstructing the decision…') that is then replaced in place by the
    result — so the work is visible and the user is never left staring at nothing."""
    thread_ts = event.get("thread_ts") or event["ts"]
    text = _MENTION.sub("", event.get("text", "")).strip()
    if not text:
        await say(
            text=":hourglass_flowing_sand: Ask me about a decision and I'll check.",
            thread_ts=thread_ts,
        )
        return

    status = await say(text=":mag: _Searching your workspace…_", thread_ts=thread_ts)
    ch, ts = status["channel"], status["ts"]

    async def on_status(msg: str) -> None:
        # Update the status line in place — no artificial sleep; the instant "Searching…" above is
        # already visible during the (real) judge + search wait, and the card follows as soon as it's
        # ready. Padding this path with sleeps just made the jury wait longer.
        await client.chat_update(channel=ch, ts=ts, text=msg)

    try:
        card = await recall_card(
            text, client, exclude_ts=event.get("ts"), on_status=on_status
        )
        if card and card.get("rate_limited"):
            await client.chat_update(
                channel=ch,
                ts=ts,
                text=":hourglass_flowing_sand: Slack search is rate-limiting me right now — ask again in a minute.",
            )
        elif card:
            await client.chat_update(
                channel=ch, ts=ts, blocks=card["blocks"], text=card["text"]
            )
        else:
            await client.chat_update(
                channel=ch,
                ts=ts,
                text=":hourglass_flowing_sand: I couldn't find an earlier thread on that yet.",
            )
    except Exception as e:
        logger.exception(f"Failed to handle app mention: {e}")
        await client.chat_update(
            channel=ch, ts=ts, text=f":warning: Something went wrong! ({e})"
        )
