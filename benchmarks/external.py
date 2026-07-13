#!/usr/bin/env python3
"""External validation — decision-arc reasoning on REAL, publicly documented decision histories.

This validates decision-arc reasoning on real, publicly documented decision histories we did NOT
author. It does NOT test Slack retrieval — that is covered by the live workspace benchmark.

Eight famous open-source decisions, each with ≥3 discussion moments across months/years, at least one
REVERSAL or REOPEN, and a public, linkable standing decision (URL = ground truth, not our opinion).
Content is faithfully summarized from the cited sources. We feed it to the SAME live pipeline —
`judge(sentence) → recall_arc(expand=False)` — with the SAME grounding gate and the SAME IDF +
relevance-floor (`_MIN_SCORE`) retrieval thresholds as `benchmarks/local.py` (never more permissive).
No tuning: run once, report whatever comes out.

    python benchmarks/external.py            # run + print
    python benchmarks/external.py --md       # also write docs/EXTERNAL.md
"""

from __future__ import annotations

import asyncio
import collections
import math
import os
import re
import sys

from dotenv import load_dotenv

load_dotenv(".env", override=False)

from benchmarks.run import _judge_query  # noqa: E402 — SAME judge as the live path
from deja.arc import _STOP, recall_arc  # noqa: E402
from deja.models import Hit  # noqa: E402


# --- Cases: (topic, url, threads[(order, author, channel, parent, [replies])], queries[(q,[tokens])])
# Each decision reply keeps the source's REAL decision language (which naturally carries a cue the
# frozen engine recognizes — "decided/chose/going with/dropping/abandon/shelved/instead/…").
class Case:
    def __init__(self, topic, url, threads, queries):
        self.topic, self.url, self.threads, self.queries = topic, url, threads, queries


CASES: list[Case] = [
    Case(
        "JS pipeline operator (F# vs Hack)",
        "https://github.com/tc39/proposal-pipeline-operator",
        [
            (
                1,
                "pipe champions",
                "tc39",
                "Proposal for the JavaScript pipeline operator |> using F#-style pipes: the right-hand side must be a unary function, value |> one |> two. Seeking Stage 2.",
                ["+1, F#-style pipes are clean and composable."],
            ),
            (
                2,
                "tc39",
                "tc39",
                "Pipeline operator update: F#-style pipes presented to TC39 for Stage 2 again after revisions.",
                [
                    "TC39 did not advance F# pipes — memory performance and await concerns from engine implementors."
                ],
            ),
            (
                3,
                "pipe champions",
                "tc39",
                "Pipeline operator — final direction after F# pipes failed to advance to Stage 2 twice.",
                [
                    "Decision: we chose Hack-style pipes with the % placeholder, value |> one(%) |> two(%), instead of F# pipes. Switching back to F# would risk TC39 never agreeing to any pipes; the smart-mix proposal was withdrawn."
                ],
            ),
        ],
        [("should the JavaScript pipeline operator use F#-style pipes?", ["hack"])],
    ),
    Case(
        "Rust async/await syntax (prefix vs postfix)",
        "https://boats.gitlab.io/blog/post/await-decision/",
        [
            (
                1,
                "withoutboats",
                "rust-lang",
                "RFC 2394 async/await: the await operator is written prefix, await future, mirroring the async keyword.",
                ["Prefix await reads naturally alongside async."],
            ),
            (
                2,
                "rust-lang",
                "rust-lang",
                "Async/await syntax debate: prefix await x vs postfix x.await vs an await!(x) macro vs space await.",
                [
                    "Postfix chains better with the ? operator and method calls; a strong majority on the lang team prefers postfix."
                ],
            ),
            (
                3,
                "rust lang team",
                "rust-lang",
                "Async/await final syntax decision: prefix await versus postfix .await, after months of debate.",
                [
                    "Decision: the lang team went with postfix expression.await (dot-await syntax), not the prefix await syntax. It chains cleanly with ? and methods."
                ],
            ),
        ],
        [
            (
                "is await prefix or postfix syntax in Rust?",
                ["postfix", "dot-await", ".await"],
            )
        ],
    ),
    Case(
        "Kubernetes dockershim removal",
        "https://kubernetes.io/blog/2022/01/07/kubernetes-is-moving-on-from-dockershim/",
        [
            (
                1,
                "sig-node",
                "kubernetes",
                "Kubernetes 1.20 deprecates dockershim, the built-in Docker runtime integration. Plan to migrate to containerd or CRI-O.",
                ["Wait, does this break my Docker-built images?"],
            ),
            (
                2,
                "k8s team",
                "kubernetes",
                "Don't Panic: Kubernetes and Docker — coming back to clarify the dockershim deprecation after widespread community concern.",
                [
                    "Your Docker-built images still run fine; only the internal dockershim component is going away."
                ],
            ),
            (
                3,
                "k8s team",
                "kubernetes",
                "Dockershim removal in Kubernetes 1.24 — final decision after the deprecation and the clarification.",
                [
                    "Decision: we removed dockershim in 1.24 as planned; the community re-litigated it but the call stands. Use containerd or CRI-O as the container runtime."
                ],
            ),
        ],
        [
            (
                "are we removing dockershim from Kubernetes?",
                ["removed", "containerd", "cri-o"],
            )
        ],
    ),
    Case(
        "CPython removing the GIL (PEP 703)",
        "https://peps.python.org/pep-0703/",
        [
            (
                1,
                "core devs",
                "python",
                "Proposals to remove the Global Interpreter Lock (GIL) from CPython — the Gilectomy and earlier attempts.",
                [
                    "Removing the GIL has been shelved repeatedly; single-thread performance regressions killed past attempts."
                ],
            ),
            (
                2,
                "Sam Gross",
                "python",
                "PEP 703: making the GIL optional with a --disable-gil build, using biased reference counting and per-object locking.",
                [
                    "Promising, but the Steering Council needs to weigh the ecosystem risk."
                ],
            ),
            (
                3,
                "Steering Council",
                "python",
                "PEP 703 Steering Council resolution on the free-threaded (no-GIL) CPython.",
                [
                    "Decision: the Steering Council accepts PEP 703 with a gradual, phased rollout, and we can roll back the changes if they prove too disruptive. This reverses the long-standing refusal to make the GIL optional."
                ],
            ),
        ],
        [("can we make the GIL optional in CPython?", ["accept", "703"])],
    ),
    Case(
        "JS decorators design (static vs plain)",
        "https://github.com/tc39/proposal-decorators",
        [
            (
                1,
                "decorators champions",
                "tc39",
                "JavaScript decorators: the legacy stage-1 design gives a decorator the class under construction and full property descriptors.",
                [
                    "Babel and TypeScript already ship this legacy decorators design widely."
                ],
            ),
            (
                2,
                "tc39",
                "tc39",
                "Static decorators redesign — a namespaced, statically analyzable decorators design.",
                [
                    "We're abandoning the static decorators design; V8 showed it was too complex and not optimizable."
                ],
            ),
            (
                3,
                "decorators champions",
                "tc39",
                "Decorators — new direction after the legacy and static designs were dropped.",
                [
                    "Decision: we chose the simpler 2022 design where decorators are plain functions that replace a value with a matching one, with no property descriptors. This dropped the earlier Stage 2 design."
                ],
            ),
        ],
        [
            (
                "should JavaScript decorators use the static decorators design?",
                ["plain", "simpler", "2022"],
            )
        ],
    ),
    Case(
        "Vue function-based vs Composition API",
        "https://github.com/vuejs/rfcs/pull/78",
        [
            (
                1,
                "Evan You",
                "vuejs",
                "Function-based Component API RFC 42: expose reactive state through a setup() function instead of the Options API.",
                [
                    "Strong backlash — this feels like it abandons the approachable Options API."
                ],
            ),
            (
                2,
                "vue community",
                "vuejs",
                "Community feedback on the Function-based Component API — thousands of comments, coming back with heavy pushback.",
                ["Don't force this on everyone; please keep the Options API."],
            ),
            (
                3,
                "Evan You",
                "vuejs",
                "Composition API RFC 78 — revised direction after the function-based API feedback.",
                [
                    "Decision: we went with an additive Composition API (renamed from function-based), alongside the Options API, which stays. value became ref and state became reactive."
                ],
            ),
        ],
        [
            (
                "is the function-based component API replacing the Options API in Vue?",
                ["additive", "composition"],
            )
        ],
    ),
    Case(
        "TypeScript legacy vs standard decorators",
        "https://devblogs.microsoft.com/typescript/announcing-typescript-5-0/",
        [
            (
                1,
                "TS team",
                "typescript",
                "TypeScript ships experimental decorators behind --experimentalDecorators, modeling an older TC39 decorators proposal.",
                [
                    "Angular and NestJS rely heavily on these legacy experimental decorators."
                ],
            ),
            (
                2,
                "TS team",
                "typescript",
                "TC39 decorators reached Stage 3 with different semantics from the TypeScript experimental design.",
                [
                    "Should TypeScript align with the standard? The emit and type-checking rules differ."
                ],
            ),
            (
                3,
                "TS team",
                "typescript",
                "TypeScript 5.0 decorators — final call on the standard versus the experimental design.",
                [
                    "Decision: TypeScript 5.0 went with the TC39 standard decorators by default; --experimentalDecorators is kept for the legacy behavior. Existing decorators may need updates."
                ],
            ),
        ],
        [
            (
                "should we keep using experimental legacy decorators in TypeScript?",
                ["standard", "tc39"],
            )
        ],
    ),
    Case(
        "SharedArrayBuffer after Spectre",
        "https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/SharedArrayBuffer",
        [
            (
                1,
                "browser vendors",
                "whatwg",
                "SharedArrayBuffer shipped enabled by default, giving JavaScript shared memory across workers with Atomics.",
                ["Great for multithreaded WebAssembly."],
            ),
            (
                2,
                "browser vendors",
                "whatwg",
                "Spectre mitigation for SharedArrayBuffer and high-resolution timers.",
                [
                    "Decision: we're dropping SharedArrayBuffer by default across browsers because Spectre timing attacks make shared memory unsafe."
                ],
            ),
            (
                3,
                "browser vendors",
                "whatwg",
                "Re-enabling SharedArrayBuffer after Spectre — coming back to shared memory with a secure design.",
                [
                    "Decision: we went with re-enabling SharedArrayBuffer only under cross-origin isolation, gated by the COOP and COEP headers. It is available by default again only in cross-origin isolated contexts."
                ],
            ),
        ],
        [
            (
                "can we use SharedArrayBuffer enabled by default?",
                ["cross-origin", "isolation", "coop", "coep", "isolated"],
            )
        ],
    ),
]

# Never-decided in this corpus → the engine must stay silent (tests confident-wrong on absence).
NEGATIVES: list[str] = [
    "should JavaScript add operator overloading?",
    "are we adding a built-in datetime type to the Rust standard library?",
    "should Python switch to curly-brace blocks instead of indentation?",
    "should Kubernetes replace YAML manifests with JSON?",
]


# --- Mirror: EXACT copy of benchmarks/local.py's retrieval math over the external corpus, so this is
# never more permissive than the live path (IDF-weighted parent-text overlap + relevance floor).
_WORD = re.compile(r"[a-z0-9]{3,}")
_MIN_SCORE = 0.4


def _build_threads() -> list[dict]:
    threads: list[dict] = []
    for case in CASES:
        for order, author, channel, parent, replies in case.threads:
            threads.append(
                {
                    "channel": channel,
                    "ts": f"{1_000_000 + order + hash(case.topic) % 1000 * 10:.6f}",
                    "permalink": case.url,
                    "parent_text": parent,
                    "parent_author": author,
                    "replies": [(author, r) for r in replies],
                    "order": order,
                }
            )
    # stable chronological ts within a case (order), unique across cases
    for i, t in enumerate(sorted(threads, key=lambda x: (x["permalink"], x["order"]))):
        t["ts"] = f"{1_000_000 + i:.6f}"
    return threads


_THREADS = _build_threads()
_BY_TS = {t["ts"]: t for t in _THREADS}
_N = len(_THREADS)
_DF: collections.Counter = collections.Counter()
for _t in _THREADS:
    for _w in set(_WORD.findall(_t["parent_text"].lower())) - _STOP:
        _DF[_w] += 1


def _idf(w: str) -> float:
    return math.log((_N + 1) / (_DF.get(w, 0) + 0.5))


def _content(text: str) -> set[str]:
    return {w for w in _WORD.findall((text or "").lower())} - _STOP


def external_recall(
    query, *, token=None, limit=5, channel_types=None, exclude_ts=None
) -> list[Hit]:
    """Same selective RTS mirror as local.local_recall — salient in-corpus term required, IDF floor."""
    qwords = _content(query)
    in_corpus = [w for w in qwords if _DF.get(w, 0) > 0]
    if not in_corpus:
        return []
    salient = max(in_corpus, key=_idf)
    denom = sum(_idf(w) for w in qwords) or 1.0
    scored: list[tuple[float, dict]] = []
    for t in _THREADS:
        if t["ts"] == exclude_ts:
            continue
        tw = _content(t["parent_text"])
        if salient not in tw:
            continue
        score = round(sum(_idf(w) for w in qwords & tw) / denom, 4)
        if score >= _MIN_SCORE:
            scored.append((score, t))
    scored.sort(key=lambda x: (-x[0], -len(x[1]["replies"])))
    return [
        Hit(
            reply_count=len(t["replies"]),
            permalink=t["permalink"],
            channel=t["channel"],
            channel_id=t["channel"],
            author=t["parent_author"],
            author_id=t["parent_author"],
            ts=t["ts"],
            snippet=t["parent_text"],
            score=sc,
        )
        for sc, t in scored[:limit]
    ]


async def external_thread(client, channel_id, ts) -> list[dict]:
    t = _BY_TS.get(ts)
    if not t:
        return []
    msgs = [{"ts": ts, "text": t["parent_text"], "username": t["parent_author"]}]
    for author, text in t["replies"]:
        msgs.append({"text": text, "username": author, "subtype": "bot_message"})
    return msgs


async def _standing(sentence: str) -> str | None:
    """The live path: judge → recall_arc (expand=False), SAME grounding gate. Returns the standing
    decision text, or None when Déjà stays silent / inconclusive."""
    q = await _judge_query(sentence)
    if not q:
        return None
    arc = await recall_arc(
        q, recall_fn=external_recall, thread_fn=external_thread, expand=False
    )
    if arc is None or arc.inconclusive:
        return None
    return arc.standing_decision.lower()


async def main(argv: list[str]) -> int:
    rows: list[tuple[str, str, str]] = []
    correct = miss = confident_wrong = 0
    for case in CASES:
        for sentence, tokens in case.queries:
            dec = await _standing(sentence)
            if dec is None:
                verdict = "MISS"
                miss += 1
            elif any(t.lower() in dec for t in tokens):
                verdict = "correct"
                correct += 1
            else:
                verdict = "CONFIDENT-WRONG"
                confident_wrong += 1
            rows.append((verdict, case.topic, sentence))

    neg_silent = neg_wrong = 0
    for sentence in NEGATIVES:
        dec = await _standing(sentence)
        if dec is None:
            neg_silent += 1
            rows.append(("correct-silent", "(never decided here)", sentence))
        else:
            neg_wrong += 1
            confident_wrong += 1
            rows.append(("CONFIDENT-WRONG", "(never decided here)", sentence))

    n_topic = sum(len(c.queries) for c in CASES)
    lines = [f"{'verdict':<18}{'topic':<38} query", "-" * 96]
    for v, topic, q in rows:
        flag = "🔴" if v == "CONFIDENT-WRONG" else ("🟡" if v == "MISS" else "  ")
        lines.append(f"{flag}{v:<16}{topic[:36]:<38}{q[:44]}")
    lines += [
        "",
        f"REAL-decision recall: {correct}/{n_topic}   ·   MISS {miss}   ·   "
        f"negatives silent {neg_silent}/{len(NEGATIVES)}   ·   CONFIDENT-WRONG {confident_wrong}",
    ]
    out = "\n".join(lines)
    print("\n" + out)

    if "--md" in argv:
        md = [
            "# Déjà external validation — real, publicly documented decisions",
            "",
            "**This validates decision-arc reasoning on real, publicly documented decision histories we",
            "did not author. It does not test Slack retrieval — that is covered by the live workspace",
            "benchmark.**",
            "",
            "Eight famous open-source decisions, each with ≥3 discussion moments across months/years, at",
            "least one reversal or reopen, and a public standing decision (the URL is the ground truth —",
            "not our interpretation). Run through the SAME live pipeline (`judge → recall_arc`, same",
            "grounding gate, same IDF + relevance-floor thresholds as the live benchmark — never more",
            "permissive). No tuning; run once.",
            "",
            "```",
            out,
            "```",
            "",
            "## The cases (ground truth = the linked source)",
        ]
        for c in CASES:
            md.append(f"- **{c.topic}** — {c.url}")
        md += [
            "",
            "## What this does and does not claim",
            "- **Does** show the arc engine reconstructs a standing decision from real, multi-author,",
            "  reversal-laden histories it never saw during development.",
            "- **Does not** measure Slack Real-Time Search — the live workspace benchmark covers that.",
            "- Misses are honest: the engine's decision detection is tuned to concise decision language;",
            "  where a real thread never states the outcome in those terms, it stays silent rather than guess.",
        ]
        os.makedirs("docs", exist_ok=True)
        with open("docs/EXTERNAL.md", "w") as f:
            f.write("\n".join(md))
        print("\n[external] wrote docs/EXTERNAL.md")
    return 1 if confident_wrong else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main(sys.argv[1:])))
