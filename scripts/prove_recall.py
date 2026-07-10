#!/usr/bin/env python3
"""Gate 2 proof harness — Phase 2.

Runs the planned "forgotten decision" query through `recall()` three times and asserts the
seeded Temporal-rollback thread lands in the top-K every time (3/3), permalink included. This
is the engine behind the "you already tried this" shock moment — it must be reliable + repeatable.

Prereqs: SLACK_USER_TOKEN in .env, and `python scripts/seed_deja.py` has been run (allow RTS a
short indexing delay). Then:  python scripts/prove_recall.py
"""
from __future__ import annotations

import sys
import time

from dotenv import load_dotenv

load_dotenv(".env", override=False)

from deja import recall  # noqa: E402  (after load_dotenv so the token is present)

QUERY = "should we migrate our job queue to Temporal"
# The forgotten nugget we must resurface — a substring unique to the rollback message.
ANCHOR = "rolling back"
TOP_K = 5
RUNS = 3


def _anchor_rank(hits) -> int | None:
    for i, h in enumerate(hits, start=1):
        if ANCHOR in h.snippet.lower() and "temporal" in h.snippet.lower():
            return i
    return None


def main() -> int:
    print(f'Query: "{QUERY}"   (anchor: a hit whose snippet contains "{ANCHOR}" + "temporal")\n')
    ranks: list[int | None] = []
    for run in range(1, RUNS + 1):
        hits = recall(QUERY, limit=TOP_K)
        rank = _anchor_rank(hits)
        ranks.append(rank)
        print(f"--- run {run}/{RUNS} — anchor at rank {rank or 'NOT FOUND'} ---")
        for i, h in enumerate(hits, start=1):
            mark = "★" if (rank == i) else " "
            print(f"  {mark}{i}. [{h.score:.2f}] #{h.channel} @{h.author}: {h.snippet[:70]!r}")
            print(f"        {h.permalink}")
        print()
        if run < RUNS:
            time.sleep(1)

    found_in_topk = [r is not None and r <= TOP_K for r in ranks]
    passed = all(found_in_topk)
    print(f"GATE 2: anchor in top-{TOP_K} on runs {found_in_topk}  ->  "
          f"{'PASS ✅ (3/3, repeatable)' if passed else 'FAIL ❌'}")
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
