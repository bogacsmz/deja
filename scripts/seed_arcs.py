#!/usr/bin/env python3
"""Phase 6 — rich, multi-author DECISION ARCS + noise.

Seeds 3 topics that were each discussed several times across months, by different people, so
`recall_arc` can reconstruct a real decision arc (timeline · standing decision · owner · times
discussed). Plus noise threads so recall isn't trivial. Multi-author via the BOT token +
chat:write.customize (username/icon per message). Channels are resolved with the USER token.

Dates live in the message text as a leading "[Mon DD]" so the timeline can show months apart
(Slack messages can't be back-dated); threads are posted oldest-first so ts order matches.

Idempotent: each thread carries a hidden marker; re-runs skip already-seeded threads.

    python scripts/seed_arcs.py            # seed
    python scripts/seed_arcs.py --dry-run  # plan only
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field

from dotenv import load_dotenv
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

load_dotenv(".env", override=False)
TEAM_ID = os.environ.get("DEJA_TEAM_ID", "T0BGF1BJYUT")

AUTHORS = {
    "Maya Chen": ":woman_technologist:",
    "Alex Rivera": ":man_technologist:",
    "Sam Okoro": ":man_scientist:",
    "Priya Nair": ":woman_scientist:",
    "Diego Santos": ":male-office-worker:",
    "Lena Fischer": ":female-office-worker:",
    "Tom Becker": ":man_cook:",
}


@dataclass(frozen=True)
class Msg:
    author: str
    text: str


@dataclass(frozen=True)
class Thread:
    channel: str
    marker: str
    parent: Msg
    replies: tuple[Msg, ...] = field(default_factory=tuple)


# --- Arc 1: Temporal job-queue migration (propose -> migrate -> ROLLBACK -> reopened) -------------
TEMPORAL = (
    Thread(
        "eng",
        "‹deja-arc:temporal-1›",
        Msg(
            "Maya Chen",
            "[Mar 12] Kicking off the migration from our Redis job queue to Temporal "
            "next sprint — durability + retries are much nicer. Objections?",
        ),
        (
            Msg(
                "Alex Rivera",
                "+1, the Temporal UI for stuck workflows alone is worth it.",
            ),
        ),
    ),
    Thread(
        "eng",
        "‹deja-arc:temporal-2›",
        Msg(
            "Alex Rivera",
            "[Apr 2] Temporal migration update: workers live in staging, replaying "
            "a week of jobs to validate.",
        ),
        (Msg("Sam Okoro", "how's the operational overhead looking so far?"),),
    ),
    Thread(
        "eng",
        "‹deja-arc:temporal-3›",
        Msg("Maya Chen", "[Apr 23] Calling it on the Temporal migration."),
        (
            Msg(
                "Maya Chen",
                "Decision: we're ROLLING BACK to Redis. Two blockers — (1) duplicate task "
                "execution under a network partition, (2) the operational cost of the cluster isn't "
                "worth it at our scale. Staying on Redis + a thin idempotency wrapper.",
            ),
            Msg(
                "Sam Okoro",
                "Agreed. Documenting so nobody relitigates this in six months.",
            ),
        ),
    ),
    Thread(
        "product",
        "‹deja-arc:temporal-4›",
        Msg(
            "Diego Santos",
            "[Jun 5] For the new ingestion pipeline, should we revisit Temporal "
            "for orchestration?",
        ),
        (
            Msg(
                "Sam Okoro",
                "we explored this in #eng back in April and moved away from it — "
                "duplicate execution + ops cost. Let's not reopen without new data.",
            ),
            Msg("Diego Santos", "ah, missed that thread. Parking it for now."),
        ),
    ),
)

# --- Arc 2: Observability vendor (trial Datadog -> DROPPED for cost -> reopened) ------------------
MONITORING = (
    Thread(
        "ops",
        "‹deja-arc:monitoring-1›",
        Msg(
            "Sam Okoro",
            "[Feb 8] Starting a Datadog trial for observability — APM + logs in one "
            "place would be great.",
        ),
        (
            Msg(
                "Priya Nair",
                "let's watch the log ingestion pricing, that's where it bites.",
            ),
        ),
    ),
    Thread(
        "ops",
        "‹deja-arc:monitoring-2›",
        Msg("Priya Nair", "[Mar 3] Datadog verdict after the trial."),
        (
            Msg(
                "Priya Nair",
                "Decision: we're DROPPING Datadog. At our log volume the bill "
                "projected to 5x our infra cost. Going with self-hosted Grafana + Loki + Tempo "
                "instead — more setup, but predictable cost.",
            ),
            Msg("Tom Becker", "makes sense, I'll own the Grafana stack."),
        ),
    ),
    Thread(
        "eng",
        "‹deja-arc:monitoring-3›",
        Msg(
            "Tom Becker",
            "[May 19] Can we get Datadog APM just for the new payments service? "
            "The tracing would help.",
        ),
        (
            Msg(
                "Priya Nair",
                "we evaluated Datadog in March and dropped it for cost — standing "
                "decision is the Grafana/Loki/Tempo stack. Happy to help wire tracing into that.",
            ),
        ),
    ),
)

# --- Arc 3: Deploy cadence (proposed -> DECIDED continuous -> re-debated) -------------------------
DEPLOY = (
    Thread(
        "eng",
        "‹deja-arc:deploy-1›",
        Msg(
            "Lena Fischer",
            "[Jan 15] Our weekly release trains keep bottlenecking. Should we move "
            "to continuous deploy on merge to main?",
        ),
        (
            Msg(
                "Alex Rivera",
                "as long as we have solid rollback + feature flags, I'm for it.",
            ),
        ),
    ),
    Thread(
        "eng",
        "‹deja-arc:deploy-2›",
        Msg("Lena Fischer", "[Jan 29] Deploy cadence decision."),
        (
            Msg(
                "Lena Fischer",
                "Decided: we're going with continuous deploy on merge to main, "
                "gated by CI + feature flags. I'll own the rollout runbook. Weekly trains are gone.",
            ),
            Msg("Diego Santos", "🎉 finally. Docs updated."),
        ),
    ),
    Thread(
        "general",
        "‹deja-arc:deploy-3›",
        Msg(
            "Tom Becker",
            "[Apr 11] Can we go back to scheduled releases? Continuous deploy feels "
            "risky for the payments work.",
        ),
        (
            Msg(
                "Lena Fischer",
                "we moved to continuous deploy in January for flow + smaller blast "
                "radius, and I own that runbook — let's not relitigate. Happy to add an extra gate "
                "for payments specifically though.",
            ),
        ),
    ),
)

# --- Noise: no decisions, recall should stay silent on these -------------------------------------
NOISE = (
    Thread(
        "random",
        "‹deja-noise:1›",
        Msg(
            "Diego Santos",
            "anyone else's coffee machine on the 3rd floor broken again ☕😭",
        ),
        (Msg("Tom Becker", "third time this month lol"),),
    ),
    Thread(
        "general",
        "‹deja-noise:2›",
        Msg("Alex Rivera", "reminder: lunch & learn moved to 1pm today"),
        (Msg("Priya Nair", "thanks!"),),
    ),
    Thread(
        "random",
        "‹deja-noise:3›",
        Msg("Sam Okoro", "hot take: tabs > spaces and I will not be taking questions"),
        (Msg("Maya Chen", "😂 blocked"),),
    ),
    Thread(
        "eng",
        "‹deja-noise:4›",
        Msg("Lena Fischer", "flaky test in the checkout suite again, anyone looking?"),
        (Msg("Alex Rivera", "on it, looks like a timing issue in the fixture"),),
    ),
)

ARCS = {
    "Temporal job queue": TEMPORAL,
    "Observability vendor": MONITORING,
    "Deploy cadence": DEPLOY,
}
ALL_THREADS = [t for arc in ARCS.values() for t in arc] + list(NOISE)
# Old single-author Temporal thread (Phase-5) is replaced by the multi-author arc above.
OBSOLETE_MARKERS = ("‹deja-seed:eng-temporal-v1›",)


def _channels(user: WebClient) -> dict[str, str]:
    out: dict[str, str] = {}
    cursor = None
    while True:
        r = user.conversations_list(
            types="public_channel,private_channel",
            limit=200,
            cursor=cursor,
            team_id=TEAM_ID,
        )
        for ch in r["channels"]:
            out[ch["name"]] = ch["id"]
        cursor = (r.get("response_metadata") or {}).get("next_cursor")
        if not cursor:
            return out


def _seeded_markers(user: WebClient, channel_id: str) -> set[str]:
    r = user.conversations_history(channel=channel_id, limit=200)
    return {m.get("text", "") for m in r["messages"]}


def _ensure_bot_in(user: WebClient, channel_id: str, bot_user: str) -> None:
    try:
        user.conversations_invite(channel=channel_id, users=bot_user)
    except SlackApiError as e:
        if e.response.data.get("error") not in (
            "already_in_channel",
            "cant_invite_self",
        ):
            pass  # best-effort; a post that fails will report not_in_channel


def _delete_obsolete(user: WebClient, channels: dict[str, str]) -> int:
    n = 0
    for cid in set(channels.values()):
        try:
            r = user.conversations_history(channel=cid, limit=200)
        except SlackApiError:
            continue
        for m in r["messages"]:
            if any(mk in (m.get("text") or "") for mk in OBSOLETE_MARKERS):
                try:
                    thread = user.conversations_replies(
                        channel=cid, ts=m["ts"], limit=50
                    )
                    for tm in thread["messages"]:
                        user.chat_delete(channel=cid, ts=tm["ts"])
                        n += 1
                except SlackApiError:
                    pass
    return n


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    dry = "--dry-run" in argv
    user = WebClient(token=os.environ["SLACK_USER_TOKEN"])
    bot = WebClient(token=os.environ["SLACK_BOT_TOKEN"])
    bot_user = bot.auth_test()["user_id"]
    channels = _channels(user)

    posted = skipped = missing = 0
    if not dry:
        removed = _delete_obsolete(user, channels)
        if removed:
            print(f"[seed] removed {removed} obsolete single-author message(s)")

    seen_cache: dict[str, set[str]] = {}
    for t in ALL_THREADS:
        cid = channels.get(t.channel)
        if not cid:
            print(f"  ⚠️  missing  #{t.channel:<8} {t.marker}")
            missing += 1
            continue
        if cid not in seen_cache:
            seen_cache[cid] = _seeded_markers(user, cid) if not dry else set()
        if not dry and any(t.marker in txt for txt in seen_cache[cid]):
            print(f"  ⏭️  skip     #{t.channel:<8} {t.marker}")
            skipped += 1
            continue
        if dry:
            print(f"  📝 would-post #{t.channel:<8} {t.parent.author:<13} {t.marker}")
            posted += 1
            continue
        _ensure_bot_in(user, cid, bot_user)
        try:
            parent = bot.chat_postMessage(
                channel=cid,
                text=f"{t.parent.text} {t.marker}",
                username=t.parent.author,
                icon_emoji=AUTHORS.get(t.parent.author, ":bust_in_silhouette:"),
            )
            for rep in t.replies:
                bot.chat_postMessage(
                    channel=cid,
                    text=rep.text,
                    thread_ts=parent["ts"],
                    username=rep.author,
                    icon_emoji=AUTHORS.get(rep.author, ":bust_in_silhouette:"),
                )
            print(f"  ✅ posted   #{t.channel:<8} {t.parent.author:<13} {t.marker}")
            posted += 1
        except SlackApiError as e:
            print(f"  ❌ {e.response.data.get('error')} #{t.channel} {t.marker}")
            missing += 1

    verb = "would-post" if dry else "posted"
    print(f"\n[seed] {posted} {verb} · {skipped} skipped · {missing} missing/failed")
    if not dry and posted:
        print(
            "[seed] note: allow RTS a short while to index the new messages before recall/arc."
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
