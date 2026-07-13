#!/usr/bin/env python3
"""Post the Déjà memory card live, to validate it renders (Slack rejects invalid Block Kit).

Builds the card for the seeded Temporal thread (judge -> recall -> decision -> card) and posts it
to the demo channel with the user token, then prints the permalink + a structural check. Gives a
live card to screenshot for Gate 4.

Prereqs: seeded workspace, SLACK_USER_TOKEN in .env, Max-authed claude. Run:  python scripts/preview_card.py
"""

from __future__ import annotations

import asyncio
import os
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(".env", override=False)

from slack_sdk.web.async_client import AsyncWebClient  # noqa: E402

from deja.respond import recall_card  # noqa: E402

TEAM_ID = os.environ.get("DEJA_TEAM_ID", "T0BGF1BJYUT")
CHANNEL = os.environ.get("DEJA_SEED_CHANNEL", "general").lstrip("#")


async def _channel_id(client: AsyncWebClient, name: str) -> str | None:
    cursor = None
    while True:
        r = await client.conversations_list(
            types="public_channel,private_channel",
            limit=200,
            cursor=cursor,
            team_id=TEAM_ID,
        )
        for ch in r["channels"]:
            if ch.get("name") == name:
                return ch["id"]
        cursor = (r.get("response_metadata") or {}).get("next_cursor")
        if not cursor:
            return None


async def main() -> int:
    client = AsyncWebClient(token=os.environ["SLACK_USER_TOKEN"])
    card = await recall_card("Should we migrate our job queue to Temporal?", client)
    if not card:
        print("no card produced (judge/recall returned nothing)")
        return 1

    cid = await _channel_id(client, CHANNEL)
    if not cid:
        print(f"channel #{CHANNEL} not found")
        return 1

    resp = await client.chat_postMessage(
        channel=cid, blocks=card["blocks"], text=card["text"]
    )
    link = (await client.chat_getPermalink(channel=cid, message_ts=resp["ts"]))[
        "permalink"
    ]

    blob = str(card["blocks"])
    print("card posted OK ✓  (Slack accepted the Block Kit)")
    print("  block types:", [b["type"] for b in card["blocks"]])
    print("  has 'what happened next':", "What happened next" in blob)
    print("  has privacy line:", "channels this app can access" in blob)
    print("  card permalink:", link)
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
