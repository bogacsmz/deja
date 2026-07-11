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
    """Explicit trigger: @Déjà <something> -> surface the past thread as a memory card."""
    thread_ts = event.get("thread_ts") or event["ts"]
    text = _MENTION.sub("", event.get("text", "")).strip()
    try:
        card = await recall_card(text, client, exclude_ts=event.get("ts")) if text else None
        if card:
            await say(blocks=card["blocks"], text=card["text"], thread_ts=thread_ts)
        else:
            await say(
                text=":hourglass_flowing_sand: I couldn't find an earlier thread on that yet.",
                thread_ts=thread_ts,
            )
    except Exception as e:
        logger.exception(f"Failed to handle app mention: {e}")
        await say(text=f":warning: Something went wrong! ({e})", thread_ts=thread_ts)
