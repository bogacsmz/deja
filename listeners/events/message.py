from logging import Logger

from slack_bolt.context.async_context import AsyncBoltContext
from slack_bolt.context.say.async_say import AsyncSay

from thread_context import session_store
from listeners.events.app_mentioned import ALIVE_MESSAGE


async def handle_message(
    context: AsyncBoltContext,
    event: dict,
    logger: Logger,
    say: AsyncSay,
):
    """Handle DMs / engaged threads. Phase 1: static 'alive' reply, no LLM.

    Scoping is unchanged from the scaffold so the bot stays quiet: it replies to DMs and to
    thread replies where it was already engaged, and leaves top-level channel messages to
    the app_mention handler.
    """
    # Skip message subtypes (edits, deletes, etc.) and bot messages.
    if event.get("subtype") or event.get("bot_id"):
        return

    is_dm = event.get("channel_type") == "im"
    is_thread_reply = event.get("thread_ts") is not None

    if is_dm:
        pass
    elif is_thread_reply:
        # Only chime into a channel thread the bot is already engaged in.
        if session_store.get_session(context.channel_id, event["thread_ts"]) is None:
            return
    else:
        # Top-level channel messages are handled by app_mentioned.
        return

    thread_ts = event.get("thread_ts") or event["ts"]
    try:
        await say(text=ALIVE_MESSAGE, thread_ts=thread_ts)
    except Exception as e:
        logger.exception(f"Failed to handle message: {e}")
        await say(text=f":warning: Something went wrong! ({e})", thread_ts=thread_ts)
