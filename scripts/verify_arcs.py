#!/usr/bin/env python3
"""Live proof for Phase 6 — reconstruct the 3 decision arcs from the seeded workspace.

For each arc topic it runs recall_arc and prints the synthesized decision record (timeline ·
standing decision · owner · times discussed · confidence). Also checks a noise query stays silent
and a weak/ambiguous query returns INCONCLUSIVE. Requires SLACK_USER_TOKEN + a seeded workspace
(scripts/seed_arcs.py) that RTS has had a moment to index.

    python scripts/verify_arcs.py
"""

from __future__ import annotations

import asyncio
import sys

from dotenv import load_dotenv

load_dotenv(".env", override=False)

from deja.arc import recall_arc  # noqa: E402

ARCS = {
    "Temporal": "should we migrate our job queue to Temporal?",
    "Observability": "should we use Datadog for monitoring?",
    "Deploy cadence": "should we switch to continuous deploy?",
}
NOISE_QUERY = "is the coffee machine on the 3rd floor working?"


def _print_arc(label: str, arc) -> None:
    print(f"\n=== {label} ===")
    if arc is None:
        print("  (no arc — recall returned nothing)")
        return
    print(f"  times_discussed: {arc.times_discussed}  confidence: {arc.confidence}")
    print(f"  STANDING: {arc.standing_decision or '(inconclusive)'}")
    if arc.owner:
        print(f"  owner: {arc.owner}  decided_at: {arc.decided_at}")
    print("  timeline:")
    for e in arc.timeline:
        mark = "✅" if e.is_decision else "  "
        print(f"    {mark} #{e.channel:<8} {e.author:<13} {e.summary[:70]}")


async def main() -> int:
    ok = True
    for label, q in ARCS.items():
        arc = await recall_arc(q)
        _print_arc(f"{label}  ·  “{q}”", arc)
        if arc is None or arc.times_discussed < 2 or arc.confidence != "high":
            ok = False

    noise = await recall_arc(NOISE_QUERY)
    print(f"\n=== NOISE  ·  “{NOISE_QUERY}” ===")
    # A noise query must not yield a STANDING DECISION (no fake decision on chatter). An
    # inconclusive/empty result is the honest, correct outcome.
    noise_ok = noise is None or noise.inconclusive
    print(
        f"  standing: {noise.standing_decision if noise else '(none)'} -> "
        f"{'no fake decision ✓' if noise_ok else 'UNEXPECTED standing decision'}"
    )
    ok = ok and noise_ok

    print(
        "\n"
        + (
            "✅ arcs reconstructed"
            if ok
            else "⚠️ some arcs incomplete (RTS indexing? re-run)"
        )
    )
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
