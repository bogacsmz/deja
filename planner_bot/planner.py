#!/usr/bin/env python3
"""Planner Bot — a tiny demo agent for Déjà's "Agents on trial" demo.

It does what a real AI agent does in a workspace: it posts action proposals to a Slack channel. It
has NO awareness of Déjà — that is the whole point. Déjà (running separately) watches the channel and
brakes the proposals that conflict with a standing decision. Governance WITHOUT the agent's
cooperation (Mode B).

This is a separate Slack app with its OWN bot token (never Déjà's), so in Slack the two are clearly
different actors: the Planner Bot proposes, Déjà judges.

Setup (see planner_bot/README.md): create a Slack app with the `chat:write` scope, install it, invite
it to the demo channel, and export its bot token as PLANNER_BOT_TOKEN.

Run:
    PLANNER_BOT_TOKEN=xoxb-…  python planner_bot/planner.py --channel C0123456789 --all
    python planner_bot/planner.py --channel C0123456789 --scene 2
"""

from __future__ import annotations

import argparse
import os
import sys
import time

from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

# The three demo proposals and the verdict each should draw from Déjà:
#   1 → ALLOW        (consistent with the standing decision — Déjà stays silent)
#   2 → CONFLICTS    (re-opens the Temporal migration the team rolled back)
#   3 → INCONCLUSIVE (discussed but never decided — Déjà won't invent a verdict)
SCENES: dict[int, str] = {
    1: "Proposing we add a usage add-on for heavy accounts.",
    2: "Opening a PR to migrate the job queue to Temporal.",
    3: "Should we adopt an RFC process for big decisions?",
}


def _resolve_channel(client: WebClient, name: str) -> str:
    """Accept a channel ID as-is; otherwise look up the ID by name (needs channels:read)."""
    if name[:1] in ("C", "G") and name[1:].isalnum():
        return name
    cursor = None
    team_id = os.environ.get("DEJA_TEAM_ID")  # Enterprise Grid scoping, optional
    while True:
        kw = dict(types="public_channel,private_channel", limit=200, cursor=cursor)
        if team_id:
            kw["team_id"] = team_id
        resp = client.conversations_list(**kw)
        for ch in resp["channels"]:
            if ch.get("name") == name.lstrip("#"):
                return ch["id"]
        cursor = (resp.get("response_metadata") or {}).get("next_cursor")
        if not cursor:
            break
    sys.exit(
        f"channel '{name}' not found — pass the channel ID, or add channels:read + invite the bot"
    )


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="Planner Bot — post demo proposals for Déjà to judge."
    )
    ap.add_argument(
        "--channel", required=True, help="channel ID (recommended) or #name"
    )
    ap.add_argument("--scene", type=int, choices=[1, 2, 3], help="post one scene")
    ap.add_argument(
        "--all", action="store_true", help="post all three, paced for the demo"
    )
    ap.add_argument(
        "--delay", type=float, default=12.0, help="seconds between scenes with --all"
    )
    args = ap.parse_args(argv)

    token = os.environ.get("PLANNER_BOT_TOKEN")
    if not token:
        sys.exit(
            "set PLANNER_BOT_TOKEN (xoxb-…) — the Planner Bot's OWN Slack app token, not Déjà's"
        )

    scenes = [args.scene] if args.scene else ([1, 2, 3] if args.all else [])
    if not scenes:
        sys.exit("pass --scene N (1|2|3) or --all")

    client = WebClient(token=token)
    channel = _resolve_channel(client, args.channel)

    for i, s in enumerate(scenes):
        try:
            client.chat_postMessage(channel=channel, text=SCENES[s])
        except SlackApiError as e:
            sys.exit(
                f"post failed: {e.response.data.get('error')} — is the Planner Bot invited to the "
                "channel and does it have chat:write?"
            )
        print(f"[planner] scene {s}: {SCENES[s]}")
        if i < len(scenes) - 1:
            time.sleep(args.delay)
    return 0


if __name__ == "__main__":
    sys.exit(main())
