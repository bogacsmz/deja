"""Déjà retrieval primitive — Phase 2.

`recall(query)` surfaces the concrete past thread a team already had on `query`, using
Slack's Real-Time Search API (`assistant.search.context`).

Token requirement (verified against the RTS docs):
  * RTS from OUTSIDE the Slack client (which is what this standalone primitive does)
    requires a **user token (xoxp-…)** with `search:read.public` (+ `.private/.im/.mpim`
    for full coverage). A bot token does NOT work here — it would need an `action_token`
    that only exists inside a live Slack event. Set `SLACK_USER_TOKEN` in `.env`.

Determinism: RTS returns no relevance score, so we score each result by query-term overlap
and sort (score desc, then ts desc) before taking the top-K. Same input -> same output.

No LLM here: the query is passed in verbatim (Phase 3 will generate it from a channel message).
"""

from __future__ import annotations

import logging
import os
import re
import time
from typing import Any

from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

from deja.models import Hit

_log = logging.getLogger(__name__)

RTS_METHOD = "assistant.search.context"
DEFAULT_CHANNEL_TYPES = ["public_channel", "private_channel", "mpim", "im"]
_WORD = re.compile(r"[a-z0-9]{3,}")

# Opt-in, process-scoped cache of RTS results, keyed by (query, limit). Off by default (live Slack
# must stay fresh); the benchmark sets DEJA_RECALL_CACHE=1 so repeated topic queries across cases
# don't re-hit the rate-limited RTS endpoint.
_RTS_CACHE: dict[tuple[str, int], list[Hit]] = {}

# Déjà must never recall its OWN output (cards, replies, dismissals) — it would pollute results
# and loop. All of Déjà's messages carry its name or tagline, so drop any hit that looks like one.
_DEJA_FINGERPRINTS = ("déjà", "your team already discussed", "powered by legibright")

# Nor should questions ADDRESSED to Déjà count as team discussion — otherwise asking the same thing
# three times inflates the "discussed N×" counter. Drop any hit that @-mentions the bot.
_BOT_UID = os.environ.get("DEJA_BOT_USER_ID", "")


def _is_deja_card(snippet: str) -> bool:
    s = snippet.lower()
    return any(fp in s for fp in _DEJA_FINGERPRINTS)


def _addressed_to_deja(snippet: str) -> bool:
    return bool(_BOT_UID) and f"<@{_BOT_UID}>" in snippet


def _resolve_token(explicit: str | None) -> str:
    token = explicit or os.environ.get("SLACK_USER_TOKEN")
    if not token:
        raise RuntimeError(
            "recall() needs a Slack USER token (xoxp-…) with search:read.public. "
            "RTS from outside the Slack client requires a user token; a bot token will not work. "
            "Set SLACK_USER_TOKEN in .env (User OAuth Token from the app's OAuth & Permissions page)."
        )
    return token


def _extract_results(data: dict[str, Any]) -> list[dict]:
    """Pull the result list out of the response, defensively.

    The exact container key is validated against the first real response (see debug_search);
    we accept the shapes the RTS docs imply so a minor naming difference doesn't break us.
    """
    for key in ("results", "messages", "matches"):
        value = data.get(key)
        if isinstance(value, list):
            return value
        if isinstance(value, dict):
            for inner in ("messages", "items", "results"):
                if isinstance(value.get(inner), list):
                    return value[inner]
    return []


def _first(d: dict, *keys: str, default: str = "") -> str:
    for k in keys:
        v = d.get(k)
        if v:
            return str(v)
    return default


def _score(query: str, snippet: str) -> float:
    q = set(_WORD.findall(query.lower()))
    if not q:
        return 0.0
    s = set(_WORD.findall(snippet.lower()))
    return round(len(q & s) / len(q), 4)


def _to_hit(result: dict, query: str) -> Hit:
    snippet = _first(result, "content", "text", "snippet")
    try:
        reply_count = int(result.get("reply_count") or 0)
    except (TypeError, ValueError):
        reply_count = 0
    return Hit(
        reply_count=reply_count,
        permalink=_first(result, "permalink", "link"),
        channel=_first(
            result, "channel_name", "channel", default=_first(result, "channel_id")
        ),
        channel_id=_first(result, "channel_id"),
        author=_first(
            result,
            "author_name",
            "username",
            default=_first(result, "author_user_id", "user"),
        ),
        author_id=_first(result, "author_user_id", "user"),
        ts=_first(result, "message_ts", "ts", "thread_ts"),
        snippet=snippet,
        score=_score(query, snippet),
    )


def recall(
    query: str,
    *,
    token: str | None = None,
    limit: int = 5,
    channel_types: list[str] | None = None,
    exclude_ts: str | None = None,
) -> list[Hit]:
    """Return the top-`limit` past messages most relevant to `query`, deterministically ordered.

    `exclude_ts` drops the triggering message itself (so a fresh "should we do X?" doesn't recall
    *itself*). Déjà's own cards and empty-content hits are always filtered out.
    """
    cacheable = (
        exclude_ts is None
        and channel_types is None
        and os.environ.get("DEJA_RECALL_CACHE")
    )
    cache_key = (query, limit)
    if cacheable and cache_key in _RTS_CACHE:
        return _RTS_CACHE[cache_key]

    pace = os.environ.get(
        "DEJA_RECALL_PACE"
    )  # benchmark-only: space calls to avoid self-throttle
    if pace:
        time.sleep(float(pace))

    client = WebClient(token=_resolve_token(token), timeout=15)
    payload = {
        "query": query,
        "channel_types": channel_types or DEFAULT_CHANNEL_TYPES,
        "limit": max(limit, 20),  # over-fetch, then we rank + trim deterministically
    }
    try:
        resp = None
        for attempt in range(3):  # RTS is rate-limited; honor Retry-After and back off
            try:
                resp = client.api_call(RTS_METHOD, json=payload)
                break
            except SlackApiError as e:
                if (e.response.data or {}).get(
                    "error"
                ) != "ratelimited" or attempt == 2:
                    raise
                wait = int(e.response.headers.get("Retry-After", 2 * (attempt + 1)))
                _log.info("recall: rate-limited, retrying in %ss", wait)
                time.sleep(wait)
    except SlackApiError as e:
        err = (e.response.data or {}).get("error")
        needed = (e.response.data or {}).get("needed")
        _log.warning("recall: RTS call failed: %s (needed=%s)", err, needed)
        raise RuntimeError(
            f"RTS call failed: {err}"
            + (f" (needed scope: {needed})" if needed else "")
            + ". If 'missing_scope' -> reinstall with search:read.public on the USER token; "
            "if 'not_allowed_token_type' -> you passed a bot token, RTS from outside Slack needs xoxp; "
            "if 'method_not_supported' / eligibility error -> the app may not be RTS-eligible (report back)."
        ) from e

    hits = [_to_hit(r, query) for r in _extract_results(resp.data)]
    hits = [
        h
        for h in hits
        if h.snippet.strip()
        and not _is_deja_card(h.snippet)
        and not _addressed_to_deja(h.snippet)
        and h.ts != exclude_ts
    ]
    # Deterministic ranking (Python sort is stable; apply least-significant key first):
    hits.sort(key=lambda h: h.ts, reverse=True)  # 3rd: newest
    hits.sort(
        key=lambda h: h.reply_count, reverse=True
    )  # 2nd: a discussed thread beats a lone line
    hits.sort(key=lambda h: h.score, reverse=True)  # 1st: query overlap
    result = hits[:limit]
    if cacheable:
        _RTS_CACHE[cache_key] = result
    return result


def debug_search(query: str, *, token: str | None = None) -> dict:
    """Return the raw RTS response — use once to validate the real field names/shape."""
    client = WebClient(token=_resolve_token(token), timeout=15)
    return client.api_call(
        RTS_METHOD, json={"query": query, "channel_types": DEFAULT_CHANNEL_TYPES}
    ).data
