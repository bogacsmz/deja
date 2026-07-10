#!/usr/bin/env python3
"""Verify Déjà's trigger judgment runs under the Claude Max subscription (no API key).

Runs `judge()` on a few messages and checks the recall/no-recall call matches expectation.
Proves two things at once: (1) the Claude Agent SDK authenticates via the subscription token,
(2) the trigger gate makes sane decisions.

Auth: set CLAUDE_CODE_OAUTH_TOKEN in .env (from `claude setup-token`), or rely on a logged-in
`claude` CLI. Then:  python scripts/verify_trigger.py
"""
from __future__ import annotations

import asyncio
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))  # repo root -> import deja

from dotenv import load_dotenv  # noqa: E402

load_dotenv(".env", override=False)

from deja import judge  # noqa: E402

# (message, expected should_recall)
CASES = [
    ("Should we migrate our job queue to Temporal?", True),
    ("I think we should switch the analytics DB to Postgres", True),
    ("anyone up for lunch at 12?", False),
    ("thanks, that worked! 🙏", False),
]


async def main() -> int:
    correct = 0
    for message, expected in CASES:
        d = await judge(message)
        ok = d.should_recall == expected
        correct += ok
        print(f"[{'✓' if ok else '✗'}] recall={d.should_recall!s:5} (want {expected!s:5}) "
              f"| query={d.query!r} | {d.reason}")
        print(f"      msg: {message!r}")
    passed = correct == len(CASES)
    print(f"\nTRIGGER JUDGMENT: {correct}/{len(CASES)} correct  ->  "
          f"{'PASS ✅ (LLM works via subscription auth)' if passed else 'FAIL ❌'}")
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
