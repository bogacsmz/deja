from logging import Logger

from slack_bolt.context.async_context import AsyncBoltContext
from slack_bolt.context.say.async_say import AsyncSay
from slack_sdk.web.async_client import AsyncWebClient  # noqa: F401  (kept for Phase 2 tool access)

# --- Phase 1 is a skeleton: prove the round-trip only. ---
# No LLM / RTS API / MCP tool / Block Kit yet — those land in Phase 2+. Every message to
# Déjà gets this same static reply so "it's alive" is provable without an ANTHROPIC_API_KEY.
ALIVE_MESSAGE = (
    ":sparkles: *Déjà çevrimiçi* — Phase 1 skeleton is alive and can post back into the thread. "
    "Recall (surfacing the concrete past thread your team already had on this) lands in Phase 2."
)


async def handle_app_mentioned(
    context: AsyncBoltContext,
    event: dict,
    logger: Logger,
    say: AsyncSay,
):
    """Reply to an @mention with a static 'alive' message — round-trip proof, no LLM."""
    thread_ts = event.get("thread_ts") or event["ts"]
    try:
        await say(text=ALIVE_MESSAGE, thread_ts=thread_ts)
    except Exception as e:
        logger.exception(f"Failed to handle app mention: {e}")
        await say(text=f":warning: Something went wrong! ({e})", thread_ts=thread_ts)
