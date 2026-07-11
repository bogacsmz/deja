#!/usr/bin/env python3
"""Seed a realistic demo workspace for Déjà — Phase 6.

Posts a small but believable set of *forgotten decision* threads (see `seed_data.SEEDS`) across
the channels a real product team would use (#eng, #ops, #product, #design, #general). Later,
`recall_memory("should we migrate the job queue to Temporal?")`, `"postgres or mongo?"`,
`"usage-based pricing?"`, etc. each resurface the concrete past thread.

Idempotent per thread: each thread carries a hidden marker in its parent message. Re-runs detect
already-seeded threads and skip them, so the seed is repeatable and additive — new threads get
posted, existing ones are left alone.

Missing channels are skipped with a warning (not a hard failure), so a partially-created
workspace still gets everything it can.

Auth: uses the USER token (SLACK_USER_TOKEN, xoxp-…) so messages appear from you (a human) and no
bot channel-invite is needed. You must already be a member of each target channel.

Usage:
    python scripts/seed_deja.py            # post missing threads
    python scripts/seed_deja.py --dry-run  # show the plan, post nothing (no Slack writes)

Prereqs: create the channels in the Deja workspace and join them first.
"""
from __future__ import annotations

import os
import sys

from dotenv import load_dotenv
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

try:  # works when run as `python scripts/seed_deja.py` (scripts/ is on sys.path[0])
    from seed_data import SEEDS, SeedThread
except ModuleNotFoundError:  # works when imported as scripts.seed_data (e.g. from repo root)
    from scripts.seed_data import SEEDS, SeedThread

load_dotenv(".env", override=False)

# Enterprise Grid: org-level user tokens must scope conversations.list to a workspace (team).
TEAM_ID = os.environ.get("DEJA_TEAM_ID", "T0BGF1BJYUT")  # Deja workspace


def resolve_channel_ids(client: WebClient, team_id: str = TEAM_ID) -> dict[str, str]:
    """Map channel name -> id for every channel visible to the user token (one paginated pass)."""
    ids: dict[str, str] = {}
    cursor = None
    while True:
        resp = client.conversations_list(
            types="public_channel,private_channel", limit=200, cursor=cursor, team_id=team_id
        )
        for ch in resp["channels"]:
            name = ch.get("name")
            if name and name not in ids:
                ids[name] = ch["id"]
        cursor = (resp.get("response_metadata") or {}).get("next_cursor")
        if not cursor:
            return ids


def _already_seeded(client: WebClient, channel_id: str, marker: str) -> bool:
    resp = client.conversations_history(channel=channel_id, limit=200)
    return any(marker in (m.get("text") or "") for m in resp["messages"])


def post_thread(client: WebClient, channel_id: str, thread: SeedThread) -> str:
    """Post a thread's parent (with marker) + replies. Returns the parent permalink."""
    parent = client.chat_postMessage(
        channel=channel_id, text=f"{thread.parent} {thread.marker}"
    )
    thread_ts = parent["ts"]
    for reply in thread.replies:
        client.chat_postMessage(channel=channel_id, text=reply, thread_ts=thread_ts)
    return client.chat_getPermalink(channel=channel_id, message_ts=thread_ts)["permalink"]


def seed_workspace(
    client: WebClient,
    seeds: tuple[SeedThread, ...] = SEEDS,
    *,
    dry_run: bool = False,
    team_id: str = TEAM_ID,
) -> list[tuple[str, SeedThread, str | None]]:
    """Seed all threads idempotently.

    Returns a list of (status, thread, permalink) where status is one of:
    'posted' | 'would-post' | 'skipped' (already seeded) | 'missing' (channel not found).
    Pure orchestration — all Slack I/O goes through the injected client, so tests can mock it.
    """
    channel_ids = resolve_channel_ids(client, team_id)
    results: list[tuple[str, SeedThread, str | None]] = []

    for thread in seeds:
        channel_id = channel_ids.get(thread.channel)
        if channel_id is None:
            results.append(("missing", thread, None))
            continue
        if _already_seeded(client, channel_id, thread.marker):
            results.append(("skipped", thread, None))
            continue
        if dry_run:
            results.append(("would-post", thread, None))
            continue
        permalink = post_thread(client, channel_id, thread)
        results.append(("posted", thread, permalink))

    return results


_ICON = {"posted": "✅", "would-post": "📝", "skipped": "⏭️ ", "missing": "⚠️ "}


def _print_summary(results: list[tuple[str, SeedThread, str | None]], dry_run: bool) -> None:
    header = "[seed] DRY RUN — nothing was posted" if dry_run else "[seed] done"
    print(header)
    counts: dict[str, int] = {}
    for status, thread, permalink in results:
        counts[status] = counts.get(status, 0) + 1
        line = f"  {_ICON.get(status, '  ')} {status:<10} #{thread.channel:<8} {thread.topic}"
        if permalink:
            line += f"\n       → {permalink}"
        print(line)
    tally = ", ".join(f"{n} {s}" for s, n in sorted(counts.items()))
    print(f"[seed] {tally}")
    if any(s == "missing" for s, _, _ in results):
        print("[seed] note: 'missing' channels don't exist / you're not a member — create+join "
              "them in Deja, then re-run (idempotent).")
    if any(s == "posted" for s, _, _ in results):
        print("[seed] note: RTS may take a short while to index new messages before recall finds "
              "them.")


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    dry_run = "--dry-run" in argv or os.environ.get("DEJA_SEED_DRY_RUN") == "1"

    token = os.environ.get("SLACK_USER_TOKEN")
    if not token:
        print("ERROR: set SLACK_USER_TOKEN (xoxp-…) in .env first.", file=sys.stderr)
        return 1
    client = WebClient(token=token)

    try:
        results = seed_workspace(client, dry_run=dry_run)
    except SlackApiError as e:
        print(f"ERROR: {e.response.data.get('error')} — check the user token has chat:write + "
              "channels:read + channels:history and that you're a member of the channels.",
              file=sys.stderr)
        return 1

    _print_summary(results, dry_run)
    return 0


if __name__ == "__main__":
    sys.exit(main())
