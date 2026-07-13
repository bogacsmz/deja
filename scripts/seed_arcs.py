#!/usr/bin/env python3
"""Phase 6 — rich, multi-author DECISION ARCS + noise.

Seeds 3 topics that were each discussed several times across months, by different people, so
`recall_arc` can reconstruct a real decision arc (timeline · standing decision · owner · times
discussed). Plus noise threads so recall isn't trivial. Multi-author via the BOT token +
chat:write.customize (username/icon per message). Channels are resolved with the USER token.

Content rules that make the live arc work (learned from real RTS behavior):
  * RTS matches on a thread's PARENT text and returns only a few top hits — so every parent in an
    arc carries the topic keywords, or RTS won't return the whole arc.
  * The genuine decision lives in a REPLY with a decision cue ("decision/rolling back/going with/…").
  * Reopen/restatement threads deliberately AVOID decision cues, so the standing decision stays the
    real one (the latest genuine decision), not a later re-mention of it.
  * Dates live in the text as a leading "[Mon DD]" (Slack can't back-date); threads post oldest-first.

Idempotent: each thread carries a hidden marker; re-runs skip already-seeded threads. Obsolete
markers from earlier revisions are deleted first.

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
        "‹deja-arc:temporal-1-v2›",
        Msg(
            "Maya Chen",
            "[Mar 12] Proposing we migrate our Redis job queue to Temporal — the "
            "durability + retries story is much nicer. Any objections?",
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
        "‹deja-arc:temporal-2-v2›",
        Msg(
            "Alex Rivera",
            "[Apr 2] Redis→Temporal job queue migration update: workers are live in "
            "staging, replaying a week of jobs to validate.",
        ),
        (Msg("Sam Okoro", "how's the operational overhead looking so far?"),),
    ),
    Thread(
        "eng",
        "‹deja-arc:temporal-3-v2›",
        Msg(
            "Maya Chen",
            "[Apr 23] Redis vs Temporal job queue migration — final call after three "
            "weeks of trial.",
        ),
        (
            Msg(
                "Maya Chen",
                "Decision: we're ROLLING BACK the Temporal migration to Redis. Two "
                "blockers — duplicate task execution under a network partition, and the ops cost of "
                "running the cluster. Staying on Redis + a thin idempotency wrapper.",
            ),
            Msg(
                "Sam Okoro",
                "Agreed. Documenting so nobody relitigates this in six months.",
            ),
        ),
    ),
    Thread(
        "product",
        "‹deja-arc:temporal-4-v2›",
        Msg(
            "Diego Santos",
            "[Jun 5] For the new ingestion pipeline, should we revisit the Temporal "
            "job queue migration?",
        ),
        (
            Msg(
                "Sam Okoro",
                "we explored this in #eng back in April and stepped away from it — "
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
        "‹deja-arc:monitoring-1-v2›",
        Msg(
            "Sam Okoro",
            "[Feb 8] Starting a Datadog trial for observability/monitoring — APM + logs "
            "in one place would be great.",
        ),
        (
            Msg(
                "Priya Nair",
                "let's watch the log ingestion pricing, that's where Datadog bites.",
            ),
        ),
    ),
    Thread(
        "ops",
        "‹deja-arc:monitoring-2-v2›",
        Msg("Priya Nair", "[Mar 3] Datadog monitoring verdict after the trial."),
        (
            Msg(
                "Priya Nair",
                "Decision: we're DROPPING Datadog for monitoring. At our log volume the "
                "bill projected to 5x our infra cost. Going with self-hosted Grafana + Loki + Tempo.",
            ),
            Msg("Tom Becker", "makes sense, I'll own the Grafana stack."),
        ),
    ),
    Thread(
        "eng",
        "‹deja-arc:monitoring-3-v2›",
        Msg(
            "Tom Becker",
            "[May 19] Can we get Datadog APM for the new payments service? The "
            "monitoring/tracing would really help.",
        ),
        (
            Msg(
                "Priya Nair",
                "we looked at Datadog back in March — the Grafana/Loki/Tempo stack we "
                "run already covers tracing, happy to wire the payments service into it.",
            ),
        ),
    ),
)

# --- Arc 3: Deploy cadence (propose -> DECIDED continuous -> re-debated) --------------------------
DEPLOY = (
    Thread(
        "eng",
        "‹deja-arc:deploy-1-v2›",
        Msg(
            "Lena Fischer",
            "[Jan 15] Our weekly release trains keep bottlenecking. Should we move "
            "to continuous deploy on merge to main?",
        ),
        (
            Msg(
                "Alex Rivera",
                "as long as we have good CI gates and feature flags, I'm for it.",
            ),
        ),
    ),
    Thread(
        "eng",
        "‹deja-arc:deploy-2-v2›",
        Msg(
            "Lena Fischer",
            "[Jan 29] Continuous deploy vs weekly release trains — final cadence call.",
        ),
        (
            Msg(
                "Lena Fischer",
                "Decided: we're going with continuous deploy on merge to main, gated "
                "by CI + feature flags. I'll own the rollout runbook. Weekly release trains are gone.",
            ),
            Msg("Diego Santos", "🎉 finally. Docs updated."),
        ),
    ),
    Thread(
        "general",
        "‹deja-arc:deploy-3-v2›",
        Msg(
            "Tom Becker",
            "[Apr 11] Can we go back to scheduled release trains? Continuous deploy "
            "feels risky for the payments work.",
        ),
        (
            Msg(
                "Lena Fischer",
                "we moved to continuous deploy on merge back in January for flow + "
                "smaller blast radius, and I own that runbook. Happy to add an extra gate for "
                "payments specifically.",
            ),
        ),
    ),
)

# --- Arc 5: Launch timing (positioning) — propose GA -> DECIDED stay in beta -> reopened ---------
LAUNCH = (
    Thread(
        "product",
        "‹deja-arc:launch-1›",
        Msg(
            "Priya Nair",
            "[Feb 10] Should we do a public GA launch this quarter, or stay in private "
            "beta a bit longer? Inbound is picking up.",
        ),
        (
            Msg(
                "Diego Santos",
                "tempting, but activation is still rough for cold signups.",
            ),
        ),
    ),
    Thread(
        "product",
        "‹deja-arc:launch-2›",
        Msg("Maya Chen", "[Mar 5] Public GA launch vs private beta — timing decision."),
        (
            Msg(
                "Maya Chen",
                "Decided: we're STAYING IN PRIVATE BETA through Q2. A public GA now would "
                "churn the inbound — onboarding activation isn't there yet. Public launch targeted for "
                "Q3 once activation is fixed.",
            ),
            Msg(
                "Priya Nair",
                "agreed, I'll own the activation metrics we need to hit first.",
            ),
        ),
    ),
    Thread(
        "general",
        "‹deja-arc:launch-3›",
        Msg(
            "Diego Santos",
            "[May 20] Can we pull the public launch forward? Sales keeps asking for a "
            "GA date.",
        ),
        (
            Msg(
                "Maya Chen",
                "we set the bar in March — GA holds until activation improves, that's still "
                "the gate. Not pulling it forward without the metrics.",
            ),
        ),
    ),
)

# (A 'free tier' arc was tried here but conflicted with the existing seat-vs-usage pricing single —
# 'free tier pricing' pulled the pricing reversal in as the standing decision, a confident-wrong.
# Removed. The launch arc gives the positioning example; pricing is the usage→seat-based decision.
# Its live threads are deleted via OBSOLETE_MARKERS below.)


# --- Single decisions, moved here from the raw-user seed so the owner/date are real personas + a
# back-dated "[Mon DD]", not the sandbox account posting today. Each is one thread (proposal +
# decision reply) → a confident, sourced single-decision arc. -------------------------------------
AUTH = (
    Thread(
        "product",
        "‹deja-arc:auth-1›",
        Msg(
            "Diego Santos",
            "[Mar 4] Do we build our own auth (sessions, SSO, MFA) or buy a provider? "
            "Building it keeps us flexible and avoids per-MAU fees.",
        ),
        (
            Msg(
                "Lena Fischer",
                "Auth is a security minefield — SAML edge cases alone will eat weeks.",
            ),
            Msg(
                "Diego Santos",
                "Decision: we're BUYING auth (Auth0) rather than building in-house. Not "
                "worth owning the security surface pre-scale. We'll re-evaluate bringing it "
                "in-house if per-MAU cost becomes a real line item.",
            ),
        ),
    ),
)

# Datastore — a full multi-author arc (propose Mongo -> DECIDED Postgres -> reopened for analytics).
DATASTORE = (
    Thread(
        "eng",
        "‹deja-arc:datastore-1-v2›",
        Msg(
            "Sam Okoro",
            "[Jan 20] Proposing we standardize the primary datastore on MongoDB — the "
            "flexible schema lets us move faster on new features. Thoughts before I write the ADR?",
        ),
        (
            Msg(
                "Maya Chen",
                "my worry is transactions across collections — a lot of our flows need "
                "multi-row consistency.",
            ),
        ),
    ),
    Thread(
        "eng",
        "‹deja-arc:datastore-2-v2›",
        Msg(
            "Maya Chen",
            "[Feb 3] Primary datastore — Postgres vs MongoDB, final call after the ADR review.",
        ),
        (
            Msg(
                "Maya Chen",
                "Decision: we're going with Postgres, not Mongo. JSONB gives us the schema "
                "flexibility we wanted, and we keep real transactions + mature tooling. ADR-014: "
                "Postgres is the system of record. Mongo stays out of the core stack.",
            ),
            Msg("Alex Rivera", "👍 migrating the schema now."),
        ),
    ),
    Thread(
        "product",
        "‹deja-arc:datastore-3-v2›",
        Msg(
            "Diego Santos",
            "[Apr 15] For the new analytics store, should we revisit MongoDB for the flexible "
            "documents?",
        ),
        (
            Msg(
                "Sam Okoro",
                "we settled the primary datastore on Postgres back in Feb (JSONB covers flexible "
                "docs). A separate analytics store is a different question — let's not reopen the core.",
            ),
        ),
    ),
)

# Pricing (positioning) — propose usage-based -> TRIED and REVERTED to seat-based.
PRICING = (
    Thread(
        "product",
        "‹deja-arc:pricing-1›",
        Msg(
            "Priya Nair",
            "[Feb 15] Should we switch our pricing from seat-based to pure usage-based billing? "
            "Usage-based feels more modern and aligned with value.",
        ),
        (
            Msg(
                "Diego Santos",
                "sales is nervous about unpredictable bills scaring off procurement.",
            ),
        ),
    ),
    Thread(
        "product",
        "‹deja-arc:pricing-2›",
        Msg(
            "Diego Santos",
            "[Mar 20] Usage-based pricing verdict after the trial quarter.",
        ),
        (
            Msg(
                "Diego Santos",
                "Update: we TRIED usage-based for a quarter and REVERTED. Customers hated the "
                "unpredictable invoices and churn ticked up. Back to seat-based with a usage add-on "
                "for overages — predictable base, upside on heavy users.",
            ),
        ),
    ),
)

# Remaining single decisions — one back-dated persona thread each (parent proposal + decision reply),
# so the owner/date read as a real teammate, not the raw sandbox account.
MONOREPO = (
    Thread(
        "eng",
        "‹deja-arc:monorepo-1v2›",
        Msg(
            "Alex Rivera",
            "[Jan 10] The polyrepo setup is getting painful — shared types drift and cross-repo "
            "PRs are a nightmare. Should we consolidate into a monorepo?",
        ),
        (
            Msg(
                "Lena Fischer",
                "Outcome: we consolidated everything into a single monorepo with Turborepo for "
                "task caching. Shared packages live in packages/*. Migration done, CI is green.",
            ),
        ),
    ),
)

K8S = (
    Thread(
        "ops",
        "‹deja-arc:k8s-1v2›",
        Msg(
            "Tom Becker",
            "[Feb 5] For the new services, do we stand up our own Kubernetes cluster or use a "
            "managed container platform? Leaning k8s for the flexibility.",
        ),
        (
            Msg(
                "Sam Okoro",
                "Decided: managed containers (ECS Fargate), not self-hosted k8s. The ops overhead "
                "of running our own cluster isn't justified at our size — we revisit only if we outgrow it.",
            ),
        ),
    ),
)

TAILWIND = (
    Thread(
        "design",
        "‹deja-arc:tailwind-1v2›",
        Msg(
            "Lena Fischer",
            "[Mar 1] Our UI is a mix of MUI and hand-rolled CSS and it's inconsistent. Should we "
            "go all-in on a component library like MUI to unify it?",
        ),
        (
            Msg(
                "Maya Chen",
                "Decided: we're standardizing on Tailwind + Radix primitives and DROPPING MUI. "
                "Utility CSS + headless primitives gave us consistency without the theming fights.",
            ),
        ),
    ),
)

STANDUP = (
    Thread(
        "general",
        "‹deja-arc:standup-1v2›",
        Msg(
            "Diego Santos",
            "[Jan 8] The 10am daily standup keeps getting derailed and eats focus time across "
            "timezones. Should we keep the sync meeting?",
        ),
        (
            Msg(
                "Priya Nair",
                "Outcome: we KILLED the sync standup and moved to an ASYNC thread — everyone posts "
                "yesterday/today/blockers by 11am local, call only when a blocker needs it. Focus went up.",
            ),
        ),
    ),
)


# --- Noise: no decisions, recall should stay silent / inconclusive on these ----------------------
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

# --- Arc 4: RFC / design-doc process — discussed 3× across months, NEVER decided (INCONCLUSIVE) ---
# Every reply is an opinion or a deferral; NONE contains a decision cue, so the arc stays honestly
# inconclusive (Déjà surfaces the discussion but invents no standing decision). Distinct keyword
# ("RFC / design-doc") so it doesn't collide with the settled arcs or the single decisions.
RFC = (
    Thread(
        "eng",
        "‹deja-arc:rfc-1›",
        Msg(
            "Alex Rivera",
            "[Feb 20] Should we adopt a lightweight RFC / design-doc process for big "
            "technical decisions? We keep re-hashing the same debates in threads.",
        ),
        (
            Msg(
                "Maya Chen",
                "+1 in spirit, though I worry it turns bureaucratic. Who'd own reviewing "
                "them?",
            ),
        ),
    ),
    Thread(
        "product",
        "‹deja-arc:rfc-2›",
        Msg(
            "Priya Nair",
            "[Apr 8] Reviving the RFC / design-doc idea — a couple of calls lately "
            "would've been smoother with a written proposal first. Worth a trial?",
        ),
        (
            Msg(
                "Diego Santos",
                "maybe? I've seen it help and I've seen it stall teams. Not sure where "
                "we'd land.",
            ),
            Msg("Alex Rivera", "let's chat about it sometime."),
        ),
    ),
    Thread(
        "eng",
        "‹deja-arc:rfc-3›",
        Msg(
            "Tom Becker",
            "[Jun 12] Coming back to the RFC / design-doc process question — should we "
            "just try it for one quarter and see?",
        ),
        (
            Msg(
                "Priya Nair",
                "I'm open to it but nobody's driving it. Let's revisit at next planning.",
            ),
            Msg("Tom Becker", "fair, parking it again 😅"),
        ),
    ),
)

ARCS = {
    "Temporal job queue": TEMPORAL,
    "Observability vendor": MONITORING,
    "Deploy cadence": DEPLOY,
    "RFC / design-doc process": RFC,
    "Launch timing": LAUNCH,
    "Auth build vs buy": AUTH,
    "Primary datastore": DATASTORE,
    "Pricing model": PRICING,
    "Repo layout": MONOREPO,
    "Container platform": K8S,
    "Styling": TAILWIND,
    "Daily standup": STANDUP,
}
ALL_THREADS = [t for arc in ARCS.values() for t in arc] + list(NOISE)
# Earlier revisions (single-author Temporal + v1 arc content) are replaced by the v2 arcs above; the
# removed free-tier arc's threads are deleted too (it confused with the seat-vs-usage pricing single).
OBSOLETE_MARKERS = (
    "‹deja-seed:eng-temporal-v1›",
    "‹deja-arc:temporal-1›",
    "‹deja-arc:temporal-2›",
    "‹deja-arc:temporal-3›",
    "‹deja-arc:temporal-4›",
    "‹deja-arc:monitoring-1›",
    "‹deja-arc:monitoring-2›",
    "‹deja-arc:monitoring-3›",
    "‹deja-arc:deploy-1›",
    "‹deja-arc:deploy-2›",
    "‹deja-arc:deploy-3›",
    "‹deja-arc:freetier-1›",
    "‹deja-arc:freetier-2›",
    # raw-user single seeds (seed_data.py), replaced by the back-dated persona arcs above:
    "‹deja-seed:product-auth-v1›",
    "‹deja-seed:eng-db-postgres-v1›",
    "‹deja-seed:eng-monorepo-v1›",
    "‹deja-seed:ops-managed-k8s-v1›",
    "‹deja-seed:product-pricing-v1›",
    "‹deja-seed:design-tailwind-v1›",
    "‹deja-seed:general-async-standup-v1›",
    # the single-thread datastore arc posted earlier this session, replaced by the full arc above:
    "‹deja-arc:datastore-1›",
)


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
    except SlackApiError:
        pass  # already in channel, or no invite scope — a failed post will report not_in_channel


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
            print(
                f"[seed] removed {removed} obsolete message(s) from earlier revisions"
            )

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
