import asyncio
from logging import Logger

from slack_bolt.context.async_context import AsyncBoltContext
from slack_bolt.context.say.async_say import AsyncSay
from slack_sdk.web.async_client import AsyncWebClient

from deja.recall import _addressed_to_deja, _is_deja_card
from deja.respond import recall_card

_MIN_LEN = (
    12  # cheap guard: skip trivially short messages before spending an LLM judgment
)

# In-process idempotency: thread_ts Déjà has intervened in THIS session. Claimed atomically under the
# lock BEFORE posting, so two messages racing in the same thread can't both post (the TOCTOU that a
# live conversations_replies read alone can't prevent). This is the PRIMARY loop/ping-pong guard.
_answered: set[str] = set()
_answered_lock = asyncio.Lock()


async def _deja_already_in_thread(
    client, channel: str, thread_ts: str, logger: Logger
) -> bool:
    """Cross-session backstop: did Déjà already post in this thread in a PRIOR run? Best-effort — on
    an API error we log and fall back to the in-process claim above (which prevents same-session
    loops), rather than killing the feature by failing closed on a flaky/permission-scoped read."""
    try:
        resp = await client.conversations_replies(
            channel=channel, ts=thread_ts, limit=50
        )
    except Exception as e:  # noqa: BLE001
        logger.warning(
            "Déjà: idempotency read failed for %s/%s (%s) — relying on in-process claim",
            channel,
            thread_ts,
            e,
        )
        return False
    return any(_is_deja_card(m.get("text", "")) for m in resp.get("messages", []))


async def handle_message(
    client: AsyncWebClient,
    context: AsyncBoltContext,
    event: dict,
    logger: Logger,
    say: AsyncSay,
):
    """Ambient governance. Déjà reads every channel message — HUMAN and AGENT — and checks it against
    the team's standing decisions:
      * human → the memory card ("your team already decided this"), silent unless a decision is found;
      * agent (bot message) → a GUARDRAIL — a ⚠️ card ONLY when the proposal CONFLICTS with a standing
        decision; ALLOW stays silent (channel-clean).

    Loop safety (never negotiable): never reacts to Déjà's OWN output, never answers a message
    addressed to Déjà (no ping-pong), and posts at most once per thread (idempotent). The counter /
    timeline filter is elsewhere (memory.py) and unchanged — @Deja mentions and Déjà's cards never
    count toward 'discussed N×'.
    """
    subtype = event.get("subtype")
    # Process real human messages (no subtype) and bot/app messages ("bot_message"); skip Slack's
    # system events (joins, edits, deletes, …).
    if subtype not in (None, "bot_message"):
        return

    # 🔴 Sponsor-safety (never negotiable): Slackbot is the collaborator, not a caught agent. Déjà
    # never brakes Slackbot — a false guardrail on Slack's own bot would misrepresent the sponsor.
    # Skip by its universal user id and by bot-profile name as a safety net.
    if event.get("user") == "USLACKBOT" or (event.get("bot_profile") or {}).get(
        "name"
    ) == "Slackbot":
        return

    text = (event.get("text") or "").strip()

    # Never react to Déjà's own output — by bot id, and by the card fingerprint as a safety net.
    if event.get("bot_id") and event.get("bot_id") == getattr(context, "bot_id", None):
        return
    if _is_deja_card(text):
        return

    if len(text) < _MIN_LEN:
        return

    # @mentions are handled by app_mentioned; anything else addressed to Déjà is a reply to us — the
    # ping-pong guard: don't answer it.
    bot_uid = context.bot_user_id
    if (bot_uid and f"<@{bot_uid}>" in text) or _addressed_to_deja(text):
        return

    # A real third-party agent posts as its own bot user (bot_id set, subtype often None), NOT
    # necessarily with the "bot_message" subtype — so classify by bot_id, not subtype, or Mode B would
    # silently never fire for genuine agents.
    is_agent = bool(event.get("bot_id"))
    thread_ts = event.get("thread_ts") or event["ts"]
    try:
        card = await recall_card(
            text, client, exclude_ts=event.get("ts"), is_agent=is_agent
        )
        # Silent on nothing-found and on rate-limit (an unsolicited 'I'm throttled' on every message
        # would be noise — the @mention path surfaces throttling instead).
        if not card or card.get("rate_limited"):
            return
        # Atomically claim the thread BEFORE posting: at most ONE intervention per thread, no TOCTOU
        # double-post, no ping-pong. The cross-session read is a best-effort backstop inside the lock.
        async with _answered_lock:
            if thread_ts in _answered:
                return
            _answered.add(thread_ts)
            prior = await _deja_already_in_thread(
                client, event["channel"], thread_ts, logger
            )
        if prior:
            return
        await say(blocks=card["blocks"], text=card["text"], thread_ts=thread_ts)
    except Exception as e:  # noqa: BLE001
        logger.exception(f"Déjà ambient governance failed: {e}")
