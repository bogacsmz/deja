#!/usr/bin/env python3
"""Seed a minimal, reproducible demo workspace for Déjà — Phase 2.

Posts ONE concrete "forgotten decision" thread into a channel (default #eng): the team tried
migrating the job queue to Temporal months ago and rolled it back for a specific reason. Later,
`recall("should we migrate the job queue to Temporal")` must resurface it.

Idempotent: a hidden marker in the parent message means re-runs detect the existing seed and
skip, so the demo is repeatable. Minimal on purpose — a fuller, realistic workspace is Phase 6.

Auth: uses the USER token (SLACK_USER_TOKEN, xoxp-…) so messages appear from you (a human) and
no bot channel-invite is needed. You must already be a member of the target channel.

Prereqs: create the channel (default #eng) in Deja, then:  python scripts/seed_deja.py
"""
from __future__ import annotations

import os
import sys

from dotenv import load_dotenv
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

load_dotenv(".env", override=False)

CHANNEL_NAME = os.environ.get("DEJA_SEED_CHANNEL", "eng").lstrip("#")
# Enterprise Grid: org-level user tokens must scope conversations.list to a workspace (team).
TEAM_ID = os.environ.get("DEJA_TEAM_ID", "T0BGF1BJYUT")  # Deja workspace
MARKER = "‹deja-seed:eng-temporal-v1›"  # ‹deja-seed:eng-temporal-v1›

PARENT = (
    "Kicking off the migration from our Redis-based job queue to Temporal next sprint — the "
    "durability + retries story is much nicer. Any objections? " + MARKER
)
REPLIES = [
    "+1, the Temporal UI for debugging stuck workflows alone is worth it.",
    "Update after 3 weeks: we're ROLLING BACK the Temporal migration. Two blockers — (1) duplicate "
    "task execution under a network partition, and (2) the operational overhead of running the "
    "Temporal cluster isn't worth it at our scale. Sticking with Redis + a thin idempotency wrapper.",
    "Noted. Documenting the decision so nobody relitigates the Temporal move in six months.",
]


def _channel_id(client: WebClient, name: str) -> str | None:
    cursor = None
    while True:
        resp = client.conversations_list(
            types="public_channel,private_channel", limit=200, cursor=cursor, team_id=TEAM_ID
        )
        for ch in resp["channels"]:
            if ch.get("name") == name:
                return ch["id"]
        cursor = (resp.get("response_metadata") or {}).get("next_cursor")
        if not cursor:
            return None


def _already_seeded(client: WebClient, channel_id: str) -> bool:
    resp = client.conversations_history(channel=channel_id, limit=200)
    return any(MARKER in (m.get("text") or "") for m in resp["messages"])


def main() -> int:
    token = os.environ.get("SLACK_USER_TOKEN")
    if not token:
        print("ERROR: set SLACK_USER_TOKEN (xoxp-…) in .env first.", file=sys.stderr)
        return 1
    client = WebClient(token=token)

    try:
        channel_id = _channel_id(client, CHANNEL_NAME)
        if not channel_id:
            print(f"ERROR: channel #{CHANNEL_NAME} not found. Create it in Deja and join it, "
                  f"or set DEJA_SEED_CHANNEL.", file=sys.stderr)
            return 1

        if _already_seeded(client, channel_id):
            print(f"[seed] #{CHANNEL_NAME} already seeded (marker present) — skipping. Idempotent ✓")
            return 0

        parent = client.chat_postMessage(channel=channel_id, text=PARENT)
        thread_ts = parent["ts"]
        for reply in REPLIES:
            client.chat_postMessage(channel=channel_id, text=reply, thread_ts=thread_ts)

        link = client.chat_getPermalink(channel=channel_id, message_ts=thread_ts)["permalink"]
        print(f"[seed] posted the forgotten Temporal thread → #{CHANNEL_NAME}")
        print(f"[seed] thread permalink: {link}")
        print("[seed] note: RTS may take a short while to index new messages before recall finds them.")
        return 0
    except SlackApiError as e:
        print(f"ERROR: {e.response.data.get('error')} — "
              "check the user token has chat:write + channels:read + channels:history "
              "and that you're a member of the channel.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
