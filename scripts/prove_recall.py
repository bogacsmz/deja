#!/usr/bin/env python3
"""Gate 2 proof harness — Phase 2.

Runs the planned "forgotten decision" query through `recall()` three times and asserts the
seeded Temporal-rollback thread lands in the top-K every time (3/3), permalink included. This
is the engine behind the "you already tried this" shock moment — it must be reliable + repeatable.

Prereqs: SLACK_USER_TOKEN in .env, and `python scripts/seed_deja.py` has been run (allow RTS a
short indexing delay). Then:  python scripts/prove_recall.py
"""
from __future__ import annotations

import pathlib
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))  # repo root -> import deja

from dotenv import load_dotenv  # noqa: E402

load_dotenv(".env", override=False)

from deja import recall  # noqa: E402  (after load_dotenv so the token is present)

QUERY = "should we migrate our job queue to Temporal"
TOP_K = 5
RUNS = 3


def _is_forgotten_thread(h) -> bool:
    """True if this hit is the seeded Temporal-migration thread (its permalink opens the thread
    where the rollback reply lives). RTS represents a thread by its best-matching message — here
    the parent — so we identify the thread by content + a present permalink, not the reply text."""
    s = h.snippet.lower()
    return bool(h.permalink) and "temporal" in s and any(w in s for w in ("migrat", "queue", "redis"))


def _anchor_rank(hits) -> int | None:
    for i, h in enumerate(hits, start=1):
        if _is_forgotten_thread(h):
            return i
    return None


def main() -> int:
    print(f'Query: "{QUERY}"   (anchor: the seeded Temporal-migration thread, permalink present)\n')
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
