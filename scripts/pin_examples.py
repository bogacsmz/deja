#!/usr/bin/env python3
"""Onboarding — post (and try to pin) a 'Try these' message in #general.

So a jury dropping into the sandbox knows what to type. Idempotent (a hidden marker); best-effort
pin (the bot may lack pins:write — the message still posts, pin it by hand if so). App Home carries
the same list as the always-visible primary onboarding.

    python scripts/pin_examples.py
"""

from __future__ import annotations

import os

from dotenv import load_dotenv
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

load_dotenv(".env", override=False)
TEAM_ID = os.environ.get("DEJA_TEAM_ID", "T0BGF1BJYUT")
MARKER = "‹deja-trythese›"

TEXT = (
    ":hourglass_flowing_sand: *Meet Déjà — your team's memory.* Mention me and I'll surface the past "
    "thread + the standing decision your team already reached. Try:\n"
    "• `@Déjà should we migrate our job queue to Temporal?`\n"
    "• `@Déjà should we adopt Datadog for monitoring?`\n"
    "• `@Déjà should we switch to continuous deploy?`\n"
    "• `@Déjà should we adopt an RFC / design-doc process?`  _(I'll say INCONCLUSIVE — no fake decision)_\n"
    "• `@Déjà let's migrate to Temporal for the new pipeline`  _(watch the contradiction warning)_\n"
    ":lock: I only search channels you can already access."
)


def main() -> int:
    user = WebClient(token=os.environ["SLACK_USER_TOKEN"])
    bot = WebClient(token=os.environ["SLACK_BOT_TOKEN"])
    channels = {
        ch["name"]: ch["id"]
        for ch in user.conversations_list(
            types="public_channel", limit=200, team_id=TEAM_ID
        )["channels"]
    }
    cid = channels.get("general")
    if not cid:
        print("no #general found")
        return 1

    for m in user.conversations_history(channel=cid, limit=100)["messages"]:
        if MARKER in (m.get("text") or ""):
            print("already posted — skipping (idempotent)")
            return 0

    resp = bot.chat_postMessage(
        channel=cid, text=f"{TEXT} {MARKER}", unfurl_links=False
    )
    print("posted the 'Try these' message to #general")
    try:
        user.pins_add(channel=cid, timestamp=resp["ts"])
        print("pinned it ✓")
    except SlackApiError as e:
        print(
            f"could not pin ({e.response.data.get('error')}) — pin it by hand from Slack if you like"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
