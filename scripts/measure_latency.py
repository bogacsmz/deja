#!/usr/bin/env python3
"""Break the live @Déjà latency into stages and print per-stage ms. No optimization here — just the
measurement the tuning is driven by. Wraps the RTS primitive + thread-fetch to COUNT and TIME every
Slack API call, so we see where the wall-clock actually goes.

    python scripts/measure_latency.py "should we adopt Datadog for monitoring?"
"""

from __future__ import annotations

import asyncio
import sys
import time

from dotenv import load_dotenv

load_dotenv(".env", override=False)

import deja.arc as arc_mod  # noqa: E402
import deja.memory as memory_mod  # noqa: E402
from deja.card import build_arc_card  # noqa: E402
from deja.conflict import detect_conflict  # noqa: E402
from deja.trigger import judge  # noqa: E402

_calls: list[tuple[str, float]] = []


def _wrap_recall(orig):
    def timed(*a, **k):
        t = time.perf_counter()
        try:
            return orig(*a, **k)
        finally:
            _calls.append(("RTS recall", (time.perf_counter() - t) * 1000))

    return timed


def _wrap_thread(orig):
    async def timed(*a, **k):
        t = time.perf_counter()
        try:
            return await orig(*a, **k)
        finally:
            _calls.append(("conversations.replies", (time.perf_counter() - t) * 1000))

    return timed


async def main() -> int:
    q = sys.argv[1] if len(sys.argv) > 1 else "should we adopt Datadog for monitoring?"
    # Instrument the primitives the engine calls (default live ones). deja/__init__ re-exports the
    # recall() function, so reach the MODULE via sys.modules.
    import sys as _sys

    recall_mod = _sys.modules["deja.recall"]
    memory_mod.recall = _wrap_recall(recall_mod.recall)
    memory_mod.fetch_thread_messages = _wrap_thread(memory_mod.fetch_thread_messages)

    print(f"\nQuery: {q!r}\n" + "-" * 60)

    t0 = time.perf_counter()
    decision = await judge(q)
    judge_ms = (time.perf_counter() - t0) * 1000
    print(f"  judge (LLM)            {judge_ms:8.0f} ms   -> {decision.query!r}")
    if not decision.should_recall:
        print("  judge said no-recall; stop.")
        return 0

    _calls.clear()
    t1 = time.perf_counter()
    arc = await arc_mod.recall_arc(decision.query, expand=False)
    arc_ms = (time.perf_counter() - t1) * 1000
    rts = [ms for n, ms in _calls if n == "RTS recall"]
    thr = [ms for n, ms in _calls if n == "conversations.replies"]
    print(
        f"  recall_arc (total)     {arc_ms:8.0f} ms   "
        f"[{len(rts)} RTS calls = {sum(rts):.0f}ms, {len(thr)} thread-fetch = {sum(thr):.0f}ms]"
    )
    for n, ms in _calls:
        print(f"      · {n:<24} {ms:7.0f} ms")

    t2 = time.perf_counter()
    if arc:
        warning = detect_conflict(q, arc)
        build_arc_card(decision.query, arc, warning)
    card_ms = (time.perf_counter() - t2) * 1000
    print(f"  card build (Block Kit) {card_ms:8.0f} ms")

    total = judge_ms + arc_ms + card_ms
    print("-" * 60)
    print(f"  TOTAL (serverside)     {total:8.0f} ms   (+ status-msg sleeps + Slack round-trips)")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
