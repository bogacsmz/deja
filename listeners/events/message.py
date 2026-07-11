from logging import Logger

from slack_bolt.context.async_context import AsyncBoltContext
from slack_bolt.context.say.async_say import AsyncSay
from slack_sdk.web.async_client import AsyncWebClient

from deja.respond import recall_card

_MIN_LEN = (
    12  # cheap guard: skip trivially short messages before spending an LLM judgment
)


async def handle_message(
    client: AsyncWebClient,
    context: AsyncBoltContext,
    event: dict,
    logger: Logger,
    say: AsyncSay,
):
    """Auto-trigger: on a normal channel/DM message, silently judge whether the team already
    discussed this and, only if a past thread is found, drop a memory card in-thread.
    Non-disruptive by design — Déjà stays silent unless it has a real 'you already tried this'.

    (The bot must be a member of the channel to receive these events.)
    """
    if event.get("subtype") or event.get("bot_id"):
        return

    text = (event.get("text") or "").strip()
    if len(text) < _MIN_LEN:
        return

    # @mentions are handled by app_mentioned — skip here to avoid a double reply.
    bot_uid = context.bot_user_id
    if bot_uid and f"<@{bot_uid}>" in text:
        return

    thread_ts = event.get("thread_ts") or event["ts"]
    try:
        card = await recall_card(text, client, exclude_ts=event.get("ts"))
        if card:
            await say(blocks=card["blocks"], text=card["text"], thread_ts=thread_ts)
    except Exception as e:
        logger.exception(f"Déjà auto-trigger failed: {e}")
