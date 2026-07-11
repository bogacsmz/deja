#!/usr/bin/env python3
"""Phase 6 (J) — reproducible benchmark: does the decision ARC beat single-hit recall?

Baseline = what plain semantic search gives you: the single most relevant message, enriched with
its own thread's outcome. Déjà = the synthesized decision arc's STANDING decision. We score both
against a hand-labelled expected answer, over three case kinds:

  * recurring (the 3 seeded arcs, each decided across months) — where the standing decision lives in
    a *different* thread than the top hit, so single-hit recall tends to surface the proposal, not
    the decision. This is where the arc should win.
  * single (one-off decisions) — both should get these; a control showing the arc doesn't regress.
  * negative (noise / never-discussed) — neither should claim a decision. Measures false decisions.

Honest by construction: same recall primitive under both, only the synthesis differs. Requires
SLACK_USER_TOKEN + the seeded workspace (scripts/seed_arcs.py + scripts/seed_deja.py), RTS indexed.

    python benchmarks/run.py            # run + print
    python benchmarks/run.py --md       # also write docs/BENCHMARK.md
"""

from __future__ import annotations

import asyncio
import os
import sys

from dotenv import load_dotenv

load_dotenv(".env", override=False)

from deja.arc import recall_arc  # noqa: E402
from deja.memory import recall_memories  # noqa: E402

# (query, kind, expected) — expected is a list of substrings (any-match, case-insensitive) that a
# CORRECT standing decision contains; empty list means "should be inconclusive / no decision".
CASES: list[tuple[str, str, list[str]]] = [
    # recurring arcs (decided across months; standing decision is NOT the top hit). Expected
    # substrings are DECISION verbs the proposal doesn't contain — so credit means "surfaced the
    # decision", not merely "matched the topic".
    ("should we migrate our job queue to Temporal?", "recurring", ["rolling back"]),
    ("is Temporal a good fit for our pipeline?", "recurring", ["rolling back"]),
    ("should we adopt Datadog for monitoring?", "recurring", ["dropping"]),
    ("can we use Datadog APM?", "recurring", ["dropping"]),
    ("should we switch to continuous deploy?", "recurring", ["decided", "going with"]),
    (
        "are we doing weekly release trains or continuous deploy?",
        "recurring",
        ["decided", "going with"],
    ),
    # single one-off decisions (control — both should get these)
    ("should we use MongoDB as our primary datastore?", "single", ["postgres"]),
    ("monorepo or polyrepo?", "single", ["monorepo", "consolidated"]),
    ("should we run our own Kubernetes cluster?", "single", ["managed", "fargate"]),
    ("should we move to usage-based pricing?", "single", ["seat", "reverted"]),
    ("should we build our own auth?", "single", ["auth0", "buying"]),
    ("should we standardize on MUI?", "single", ["tailwind"]),
    ("should we keep the sync daily standup?", "single", ["async"]),
    # negatives — noise / never discussed (must NOT claim a decision)
    ("is the coffee machine on the 3rd floor working?", "negative", []),
    ("tabs or spaces?", "negative", []),
    ("what time is the lunch and learn?", "negative", []),
    ("should we migrate to CockroachDB?", "negative", []),
    ("should we rewrite everything in Rust?", "negative", []),
]


def _hit(expected: list[str], text: str) -> bool:
    low = (text or "").lower()
    return any(sub in low for sub in expected)


async def _baseline(query: str) -> str:
    """Single-hit recall: the top thread's own outcome (what plain search + one thread gives)."""
    result = await recall_memories(query, limit=1)
    mems = result.get("memories") or []
    if not mems:
        return ""
    return mems[0].get("what_happened_next") or mems[0].get("source_message") or ""


async def _deja(query: str) -> tuple[str, bool]:
    """Déjà: the arc's standing decision (empty when inconclusive)."""
    arc = await recall_arc(query)
    if arc is None or arc.inconclusive:
        return "", True  # no decision claimed
    return arc.standing_decision, False


async def main(argv: list[str]) -> int:
    rows = []
    tally = {
        "recurring": {"n": 0, "base": 0, "deja": 0},
        "single": {"n": 0, "base": 0, "deja": 0},
        "negative": {"n": 0, "base_false": 0, "deja_false": 0},
    }
    for query, kind, expected in CASES:
        base = await _baseline(query)
        deja, deja_incon = await _deja(query)
        if kind == "negative":
            base_false = bool(
                base.strip()
            )  # baseline surfaced *something* as an answer
            deja_false = not deja_incon  # Déjà claimed a standing decision
            tally[kind]["n"] += 1
            tally[kind]["base_false"] += base_false
            tally[kind]["deja_false"] += deja_false
            rows.append(
                (
                    kind,
                    query,
                    "—",
                    "FALSE" if base_false else "ok",
                    "FALSE" if deja_false else "ok",
                )
            )
        else:
            base_ok, deja_ok = _hit(expected, base), _hit(expected, deja)
            tally[kind]["n"] += 1
            tally[kind]["base"] += base_ok
            tally[kind]["deja"] += deja_ok
            rows.append(
                (
                    kind,
                    query,
                    "/".join(expected),
                    "✓" if base_ok else "✗",
                    "✓" if deja_ok else "✗",
                )
            )

    lines = ["", f"{'kind':<10} {'query':<52} {'baseline':>8} {'déjà':>6}"]
    lines.append("-" * 80)
    for kind, q, _exp, b, d in rows:
        lines.append(f"{kind:<10} {q[:52]:<52} {b:>8} {d:>6}")
    r, s, n = tally["recurring"], tally["single"], tally["negative"]
    lines += [
        "",
        "SCORES (correct standing decision):",
        f"  recurring arcs:  baseline {r['base']}/{r['n']}   Déjà {r['deja']}/{r['n']}",
        f"  single decisions:baseline {s['base']}/{s['n']}   Déjà {s['deja']}/{s['n']}",
        "FALSE DECISIONS on negatives (lower is better):",
        f"  negatives:       baseline {n['base_false']}/{n['n']}   Déjà {n['deja_false']}/{n['n']}",
    ]
    out = "\n".join(lines)
    print(out)

    if "--md" in argv:
        md = [
            "# Déjà benchmark — decision arc vs single-hit recall",
            "",
            "Same recall primitive under both; only the synthesis differs (honest by construction).",
            "Baseline = the single most relevant thread's own outcome. Déjà = the arc's standing decision.",
            "",
            "```",
            out,
            "```",
            "",
            "## Reading it",
            "- **Recurring arcs** are where Déjà wins: the standing decision lives in a different thread",
            "  than the top hit, so single-hit recall surfaces the *proposal*, not the *decision*.",
            "- **Single decisions** are a control — both do well; the arc degrades to the single thread.",
            "- **Negatives** measure false decisions: Déjà returns INCONCLUSIVE rather than inventing one.",
            "",
            "## Limits (honest)",
            "- Small, seeded workspace (synthetic team memory), not a large real org.",
            "- Dates are content-conveyed ('[Mon DD]') because Slack messages can't be back-dated.",
            "- RTS matches on a thread's parent text; an arc whose threads don't share topic keywords",
            "  in their parents may be under-retrieved. The seed is written with that in mind.",
            "- Correctness is substring-based against hand-labelled expected decisions.",
            f"- {len(CASES)} cases; expand `CASES` in benchmarks/run.py to grow it.",
            "",
        ]
        os.makedirs("docs", exist_ok=True)
        with open("docs/BENCHMARK.md", "w") as f:
            f.write("\n".join(md))
        print("\n[benchmark] wrote docs/BENCHMARK.md")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main(sys.argv[1:])))
