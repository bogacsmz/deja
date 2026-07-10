import re
from logging import Logger

from slack_bolt.context.async_context import AsyncBoltContext
from slack_bolt.context.say.async_say import AsyncSay

from deja.respond import recall_reply

_MENTION = re.compile(r"<@[A-Z0-9]+>")


async def handle_app_mentioned(
    context: AsyncBoltContext,
    event: dict,
    logger: Logger,
    say: AsyncSay,
):
    """Explicit trigger: @Déjà <something> -> judge it, surface the past thread if there is one."""
    thread_ts = event.get("thread_ts") or event["ts"]
    text = _MENTION.sub("", event.get("text", "")).strip()
    try:
        reply = await recall_reply(text) if text else None
        await say(
            text=reply or ":hourglass_flowing_sand: I couldn't find an earlier thread on that yet.",
            thread_ts=thread_ts,
        )
    except Exception as e:
        logger.exception(f"Failed to handle app mention: {e}")
        await say(text=f":warning: Something went wrong! ({e})", thread_ts=thread_ts)
