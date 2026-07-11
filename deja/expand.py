"""LLM query expansion — close the semantic gap that lexical RTS retrieval can't.

RTS matches a thread's *parent text*, so a question phrased differently from how the team wrote it
("observability stack" vs "Datadog monitoring verdict") never retrieves the decision. Before giving
up, we ask the LLM (Claude Max subscription — same auth as `trigger`) for the SPECIFIC named
technologies/products the question is about, including the likely vendor names the team may have
used, then run those as extra RTS queries and cluster the results.

Two rails keep the honesty invariant intact (a noise / never-discussed query must never gain a fake
decision):
  * the LLM returns [] when the question isn't about a decision (chit-chat, status, a task), and
  * a deterministic denylist strips generic connector words ("queue", "CI", "API", …) that would
    otherwise drift a query into an unrelated topic's decision.
The caller adds a third rail (a subject guard in `recall_arc`) so a specific product name in the
query can't be answered with a *different* product's decision.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import pathlib
import re

from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    ClaudeSDKClient,
    TextBlock,
)

_log = logging.getLogger(__name__)

# The LLM runs as a spawned subprocess; a hung one must not freeze Déjà (ambient trigger) or the
# benchmark. Bound every call and fail safe to no-expansion on timeout/error.
_TIMEOUT_S = float(os.environ.get("DEJA_EXPAND_TIMEOUT", "30"))

# Optional on-disk cache (DEJA_EXPAND_CACHE=<path>): expand each unique query once, so batch runs
# (the benchmark) don't spawn an LLM subprocess per case in a tight loop, and reruns are instant.
_CACHE_PATH = (
    pathlib.Path(os.environ["DEJA_EXPAND_CACHE"])
    if os.environ.get("DEJA_EXPAND_CACHE")
    else None
)


def _load_cache() -> dict[str, list[str]]:
    if _CACHE_PATH and _CACHE_PATH.exists():
        try:
            return json.loads(_CACHE_PATH.read_text())
        except (ValueError, OSError):
            return {}
    return {}


_CACHE: dict[str, list[str]] = _load_cache()

# Generic technical connectors that appear across many unrelated decisions — expanding on any of
# these would pull a different topic's decision into the answer. Dropped deterministically.
_GENERIC = frozenset(
    "queue queues job jobs event events api apis ci cd cicd system systems service services data "
    "pipeline pipelines infra infrastructure platform platforms stack stacks app apps code tool "
    "tools framework frameworks library libraries thing stuff feature features".split()
)

_SYSTEM = """You expand a question so a keyword search can find a software team's past DECISION on
its topic, in their Slack history.

Return ONLY a JSON object: {"terms": ["term", ...]}

Rules:
- terms = the SPECIFIC named technologies, products, vendors, or named processes the question is
  about, PLUS the likely vendor/product names a team may have used for THIS SAME need even if the
  question doesn't name them. Examples:
    "observability stack" -> ["Datadog","Grafana","Prometheus","monitoring","observability"]
    "background job system" -> ["Temporal","Redis","Celery","Sidekiq"]
    "authentication" -> ["Auth0","Okta","authentication","SSO"]
    "how we ship to prod" -> ["continuous deploy","release train"]
- Do NOT list competing alternatives the question is asking whether to ADOPT INSTEAD. If the
  question names one specific product (e.g. "should we adopt CockroachDB / Kafka / GraphQL?"),
  expand only that product and its direct synonyms — never its competitors.
- Do NOT include generic connector words shared by many topics (queue, events, API, CI, service,
  system, data, pipeline, stack, platform) unless it is literally the named subject.
- If the question is NOT about a decision the team may have made — small talk, a status check, a
  task/assignment, logistics — return {"terms": []}.
Return at most 6 short terms."""


def _parse(text: str) -> list[str]:
    try:
        m = re.search(r"\{.*\}", text, re.S)
        data = json.loads(m.group(0)) if m else {}
    except (ValueError, json.JSONDecodeError):
        _log.warning("expand: model output was not valid JSON; no expansion")
        return []
    terms = data.get("terms") if isinstance(data, dict) else None
    if not isinstance(terms, list):
        return []
    return [str(t).strip() for t in terms if str(t).strip()]


def keep_specific(terms: list[str]) -> list[str]:
    """Drop generic single-word connectors and dedupe (case-insensitive, order-preserving)."""
    seen: set[str] = set()
    out: list[str] = []
    for t in terms:
        low = t.lower().strip()
        if not low or (len(low.split()) == 1 and low in _GENERIC):
            continue  # a lone generic connector would drift topics; multi-word phrases are specific
        if low not in seen:
            seen.add(low)
            out.append(t)
    return out


async def _call_llm(query: str) -> str:
    options = ClaudeAgentOptions(
        system_prompt=_SYSTEM, permission_mode="bypassPermissions", allowed_tools=[]
    )
    text = ""
    async with ClaudeSDKClient(options) as client:
        await client.query(query)
        async for msg in client.receive_response():
            if isinstance(msg, AssistantMessage):
                for block in msg.content:
                    if isinstance(block, TextBlock):
                        text += block.text
    return text


async def expand_query(query: str) -> list[str]:
    """Specific topic entities to also search for; [] on failure, timeout, or a non-decision question.

    Bounded by DEJA_EXPAND_TIMEOUT (default 30s): a hung LLM subprocess fails safe to no expansion
    rather than freezing the caller. Results are memoized (and optionally persisted to disk)."""
    if query in _CACHE:
        return _CACHE[query]
    try:
        text = await asyncio.wait_for(_call_llm(query), timeout=_TIMEOUT_S)
    except (asyncio.TimeoutError, Exception) as e:  # noqa: BLE001 — fail safe to no-expansion
        _log.warning("expand: unavailable (%s); no expansion", type(e).__name__)
        return []
    terms = keep_specific(_parse(text))
    _CACHE[query] = terms
    if _CACHE_PATH:
        try:
            _CACHE_PATH.write_text(json.dumps(_CACHE, indent=1))
        except OSError:
            pass
    return terms
