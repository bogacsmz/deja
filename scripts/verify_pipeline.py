#!/usr/bin/env python3
"""End-to-end Phase 3 proof: judge -> recall -> reply, with no Slack event needed.

Uses the real RTS user token (SLACK_USER_TOKEN) + the Max subscription LLM (Claude Agent SDK).
A triggering message must resurface the seeded thread's permalink; small talk must stay silent.

Prereqs: seeded workspace (scripts/seed_deja.py), SLACK_USER_TOKEN in .env, Max-authed claude.
Run:  python scripts/verify_pipeline.py
"""

from __future__ import annotations

import asyncio
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(".env", override=False)

from deja.respond import recall_reply  # noqa: E402

# (message, should_a_reply_be_produced)
CASES = [
    ("Should we finally migrate our job queue to Temporal?", True),
    ("anyone up for lunch at 12?", False),
]


async def main() -> int:
    ok = True
    for message, expect_reply in CASES:
        reply = await recall_reply(message)
        got_reply = reply is not None
        has_link = bool(reply and "http" in reply)
        passed = (got_reply == expect_reply) and (not expect_reply or has_link)
        ok = ok and passed
        print(f"[{'✓' if passed else '✗'}] {message!r}")
        print(f"      -> {reply if reply else '(silent)'}\n")
    print(f"PIPELINE (judge->recall->reply): {'PASS ✅' if ok else 'FAIL ❌'}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
