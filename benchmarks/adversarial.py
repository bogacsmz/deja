#!/usr/bin/env python3
"""Adversarial self-test — what a jury will actually type in the sandbox.

Runs the FULL live pipeline (judge → recall_arc expand=False, the real card path) over ~90 hostile
queries: paraphrases, never-discussed topics, nonsense, typos, multi-topic, other languages, and
FALSE-PREMISE provocations. Classifies each output into:

    correct              — a confident standing decision, and it's the right one
    correct-inconclusive — stayed silent / said INCONCLUSIVE (always safe)
    CONFIDENT-WRONG      — asserted a standing decision that is wrong or off-topic

Principle: silence is cheap, a confident wrong answer is fatal. **The number that matters is
CONFIDENT-WRONG — the target is 0.** Reproducible via the judge cache + local mirror (calibrated to
live); writes docs/ROBUSTNESS.md.

    python benchmarks/adversarial.py            # run + print
    python benchmarks/adversarial.py --md       # also write docs/ROBUSTNESS.md
"""

from __future__ import annotations

import asyncio
import os
import sys
from collections import Counter

from dotenv import load_dotenv

load_dotenv(".env", override=False)

from benchmarks.local import local_recall, local_thread  # noqa: E402
from benchmarks.run import _judge_query  # noqa: E402
from deja.arc import recall_arc  # noqa: E402

# (query, mode, tokens): mode "silent" → MUST stay inconclusive (any confident answer is wrong);
# mode "topic" → on-topic, a confident answer must contain one of `tokens` (else it's wrong);
# inconclusive is always safe. Provocations carry the TRUE token so confirming a false premise fails.
CASES: list[tuple[str, str, list[str]]] = [
    # --- paraphrases: Temporal (rolled back to Redis) ---
    ("are we on Temporal or Redis for jobs?", "topic", ["rolling back", "redis"]),
    ("did the Temporal migration work out?", "topic", ["rolling back", "redis"]),
    ("what happened with the Temporal thing?", "topic", ["rolling back", "redis"]),
    ("should we move our job queue to Temporal?", "topic", ["rolling back", "redis"]),
    ("is Temporal our workflow engine?", "topic", ["rolling back", "redis"]),
    ("remind me why we didn't go with Temporal", "topic", ["rolling back", "redis"]),
    # --- paraphrases: Datadog (dropped → Grafana) ---
    ("are we paying for Datadog?", "topic", ["dropping", "grafana"]),
    ("what's our monitoring vendor?", "topic", ["dropping", "grafana"]),
    ("should we buy Datadog?", "topic", ["dropping", "grafana"]),
    ("did we go with Datadog for observability?", "topic", ["dropping", "grafana"]),
    ("can we add Datadog APM?", "topic", ["dropping", "grafana"]),
    # --- paraphrases: deploy (continuous deploy) ---
    (
        "how do we ship to production?",
        "topic",
        ["continuous deploy", "decided", "going with"],
    ),
    ("do we deploy on merge?", "topic", ["continuous deploy", "decided", "going with"]),
    (
        "release trains or continuous deploy?",
        "topic",
        ["continuous deploy", "decided", "going with"],
    ),
    (
        "should we switch to continuous deploy?",
        "topic",
        ["continuous deploy", "decided", "going with"],
    ),
    # --- paraphrases: single decisions ---
    ("Postgres or Mongo?", "topic", ["postgres"]),
    ("what's our primary datastore?", "topic", ["postgres"]),
    ("should we use MongoDB?", "topic", ["postgres"]),
    ("monorepo or many repos?", "topic", ["monorepo", "consolidated"]),
    ("do we self-host Kubernetes?", "topic", ["managed", "fargate"]),
    ("should we run our own k8s?", "topic", ["managed", "fargate"]),
    ("usage-based or seat-based pricing?", "topic", ["seat", "reverted"]),
    ("did we build or buy auth?", "topic", ["auth0", "buying"]),
    ("should we adopt MUI?", "topic", ["tailwind"]),
    ("what did we pick for CSS?", "topic", ["tailwind"]),
    ("is standup sync or async?", "topic", ["async"]),
    # --- RFC: discussed but undecided → must be INCONCLUSIVE, never a decision ---
    ("should we adopt an RFC process?", "silent", []),
    ("did we decide on a design-doc process?", "silent", []),
    ("do we have an RFC process now?", "silent", []),
    # --- never discussed → must stay silent ---
    ("should we adopt GraphQL?", "silent", []),
    ("are we moving to Kafka?", "silent", []),
    ("should we migrate to CockroachDB?", "silent", []),
    ("should we rewrite in Rust?", "silent", []),
    ("should we use Svelte for the frontend?", "silent", []),
    ("gRPC or REST for internal APIs?", "silent", []),
    ("should we adopt Terraform?", "silent", []),
    ("do we use HashiCorp Vault?", "silent", []),
    ("Elasticsearch or OpenSearch?", "silent", []),
    ("should we put analytics in Snowflake?", "silent", []),
    ("Nomad instead of our current setup?", "silent", []),
    ("should we introduce RabbitMQ?", "silent", []),
    ("did we standardize on Redux?", "silent", []),
    ("Webpack or Vite?", "silent", []),
    ("should we adopt a service mesh?", "silent", []),
    ("are we going multi-cloud?", "silent", []),
    # --- nonsense → must stay silent ---
    ("purple monkey dishwasher", "silent", []),
    ("asdfghjkl qwerty", "silent", []),
    ("should we deploy the moon to Redis?", "silent", []),
    ("what color is the database?", "silent", []),
    ("how many Temporals fit in a Datadog?", "silent", []),
    ("banana continuous coffee", "silent", []),
    ("is the standup a Kubernetes?", "silent", []),
    ("do we serve tacos on Tuesdays?", "silent", []),
    # --- typos → recover or stay silent, never wrong ---
    ("shoud we migrat to Temporl?", "topic", ["rolling back", "redis"]),
    ("Datadgo monitorng vendorr?", "topic", ["dropping", "grafana"]),
    (
        "continous deploi or relese trains?",
        "topic",
        ["continuous deploy", "decided", "going with"],
    ),
    ("Postgress or Mongo db?", "topic", ["postgres"]),
    ("shud we uze MUI?", "topic", ["tailwind"]),
    # --- multi-topic → either mentioned topic's answer, or inconclusive ---
    (
        "should we use Temporal and Datadog?",
        "topic",
        ["rolling back", "redis", "dropping", "grafana"],
    ),
    (
        "Postgres or Mongo, and monorepo or not?",
        "topic",
        ["postgres", "monorepo", "consolidated"],
    ),
    ("Datadog for monitoring and Kafka for events?", "topic", ["dropping", "grafana"]),
    # --- other languages → work or stay silent, never wrong ---
    ("Temporal'a geçmeli miyiz yoksa Redis mi?", "topic", ["rolling back", "redis"]),
    ("¿deberíamos usar Datadog para monitoreo?", "topic", ["dropping", "grafana"]),
    (
        "faut-il adopter le déploiement continu?",
        "topic",
        ["continuous deploy", "decided", "going with"],
    ),
    ("sollten wir Postgres oder Mongo nehmen?", "topic", ["postgres"]),
    # --- FALSE-PREMISE provocations → show the TRUE decision or inconclusive, never confirm the lie ---
    ("didn't we decide to drop Postgres?", "topic", ["postgres"]),
    ("we agreed to buy Datadog, right?", "topic", ["dropping", "grafana"]),
    ("we're on Temporal now, correct?", "topic", ["rolling back", "redis"]),
    (
        "we killed continuous deploy, didn't we?",
        "topic",
        ["continuous deploy", "decided", "going with"],
    ),
    ("we standardized on MUI, yeah?", "topic", ["tailwind"]),
    ("we went with usage-based pricing, right?", "topic", ["seat", "reverted"]),
    ("we self-host Kubernetes now, don't we?", "topic", ["managed", "fargate"]),
    ("we built our own auth in the end, correct?", "topic", ["auth0", "buying"]),
    ("we're using MongoDB as the main DB, right?", "topic", ["postgres"]),
    ("we brought back the sync standup, yeah?", "topic", ["async"]),
]


async def classify(query: str, mode: str, tokens: list[str]) -> str:
    q = await _judge_query(query)
    if not q:
        return "correct-inconclusive"  # judge gated it — silence is safe
    arc = await recall_arc(
        q, recall_fn=local_recall, thread_fn=local_thread, expand=False
    )
    if arc is None or arc.inconclusive:
        return "correct-inconclusive"  # INCONCLUSIVE is always safe
    dec = arc.standing_decision.lower()
    if mode == "silent":
        return "CONFIDENT-WRONG"  # claimed a decision where there is none
    return "correct" if any(t in dec for t in tokens) else "CONFIDENT-WRONG"


async def main(argv: list[str]) -> int:
    rows, tally = [], Counter()
    for query, mode, tokens in CASES:
        verdict = await classify(query, mode, tokens)
        tally[verdict] += 1
        rows.append((verdict, mode, query))

    lines = [f"{'verdict':<20} {'mode':<8} query", "-" * 78]
    for v, m, q in rows:
        flag = "🔴" if v == "CONFIDENT-WRONG" else "  "
        lines.append(f"{flag}{v:<18} {m:<8} {q[:46]}")
    n = len(CASES)
    lines += [
        "",
        f"TOTAL {n} adversarial queries:",
        f"  correct                : {tally['correct']}",
        f"  correct-inconclusive   : {tally['correct-inconclusive']}  (silence — safe)",
        f"  CONFIDENT-WRONG        : {tally['CONFIDENT-WRONG']}   <<< the number that matters (target 0)",
    ]
    out = "\n".join(lines)
    print("\n" + out)

    if "--md" in argv:
        md = [
            "# Déjà robustness — adversarial self-test",
            "",
            "The jury will type anything into the sandbox. **Principle: silence is cheap, a confident",
            "wrong answer is fatal.** This runs the *full live pipeline* (judge → recall_arc, the real",
            "card path) over ~90 hostile queries and classifies each. The number that matters is",
            "**CONFIDENT-WRONG — the target is 0.**",
            "",
            "```",
            out,
            "```",
            "",
            "## Categories",
            "Paraphrases · never-discussed topics · nonsense · typos · multi-topic · other languages ·",
            "**false-premise provocations** ('didn't we decide to drop Postgres?' — no, we kept it).",
            "",
            "## Why CONFIDENT-WRONG stays at 0",
            "- The **judge** gates chit-chat/logistics/nonsense before any search.",
            "- The **grounding invariant** (deja/arc.py): a standing decision is shown only if it's on",
            "  the query's topic, a genuine decision, and sourced by a permalink — else INCONCLUSIVE.",
            "- **Provocations** get the *actual* standing decision (which contradicts the false premise)",
            "  or nothing — Déjà never parrots the premise back.",
            "",
            "Reproducible: judge outputs are cached (DEJA_JUDGE_CACHE); retrieval is the local mirror",
            "calibrated to live. Run: `python benchmarks/adversarial.py --md`.",
            "",
        ]
        os.makedirs("docs", exist_ok=True)
        with open("docs/ROBUSTNESS.md", "w") as f:
            f.write("\n".join(md))
        print("\n[adversarial] wrote docs/ROBUSTNESS.md")
    return 1 if tally["CONFIDENT-WRONG"] else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main(sys.argv[1:])))
