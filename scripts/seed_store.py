#!/usr/bin/env python3
"""Populate the canonical decision store from the seeded arcs — so Déjà's App Home 'Recent decisions'
is alive on first open (the jury's first click), each row linking to its REAL Slack thread.

Runs the actual arc engine (`build_arc`) over each seeded arc to derive its standing decision, fetches
the real Slack permalink of the decision thread, and saves it via the same `save_decision` the 💾
button uses. The inconclusive RFC arc is skipped (it has no decision — by design). Idempotent:
re-running just refreshes the entries.

    python scripts/seed_store.py            # write the store from the live workspace
    python scripts/seed_store.py --dry-run  # build + print, write nothing
"""

from __future__ import annotations

import os
import sys

from dotenv import load_dotenv
from slack_sdk import WebClient

load_dotenv(".env", override=False)

from deja.arc import build_arc  # noqa: E402
from deja.store import save_decision  # noqa: E402
from deja.thread import pick_decision  # noqa: E402
from scripts.seed_arcs import ARCS, _channels  # noqa: E402

# Crafted, tight headlines + the standing-state icon for each arc — the demo polish the App Home shows
# as the bold line (the full decision text sits underneath as the quote).
HEADLINES: dict[str, tuple[str, str]] = {
    "Temporal job queue": ("Stay on Redis — rolled back Temporal", "↩️"),
    "Observability vendor": ("Grafana/Loki/Tempo, not Datadog", "↩️"),
    "Deploy cadence": ("Continuous deploy on merge to main", "✅"),
    "Launch timing": ("Stay in private beta through Q2", "✅"),
    "Auth build vs buy": ("Buy Auth0 — don't build in-house", "✅"),
    "Primary datastore": ("Postgres, not Mongo", "✅"),
    "Pricing model": ("Seat-based — reverted usage-based", "↩️"),
    "Repo layout": ("Monorepo with Turborepo", "✅"),
    "Container platform": ("Managed ECS Fargate, not k8s", "✅"),
    "Styling": ("Tailwind + Radix — dropped MUI", "✅"),
    "Daily standup": ("Async standup — killed the sync meeting", "✅"),
}


def _thread_msgs(thread) -> list[dict]:
    msgs = [{"text": thread.parent.text, "username": thread.parent.author}]
    for r in thread.replies:
        msgs.append({"text": r.text, "username": r.author, "subtype": "bot_message"})
    return msgs


def _marker_locations(
    user: WebClient, channels: dict[str, str]
) -> dict[str, tuple[str, str]]:
    """marker -> (channel_id, message_ts) for every seeded arc thread present in the workspace."""
    wanted = {th.marker for arc in ARCS.values() for th in arc}
    loc: dict[str, tuple[str, str]] = {}
    for cid in set(channels.values()):
        try:
            msgs = user.conversations_history(channel=cid, limit=200)["messages"]
        except Exception:  # noqa: BLE001
            continue
        for m in msgs:
            text = m.get("text", "")
            for mk in wanted:
                if mk in text:
                    loc[mk] = (cid, m["ts"])
    return loc


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    dry = "--dry-run" in argv
    user = WebClient(token=os.environ["SLACK_USER_TOKEN"])
    channels = _channels(user)
    loc = {} if dry else _marker_locations(user, channels)

    def permalink(marker: str) -> str:
        hit = loc.get(marker)
        if not hit:
            return ""
        try:
            return user.chat_getPermalink(channel=hit[0], message_ts=hit[1])[
                "permalink"
            ]
        except Exception:  # noqa: BLE001
            return ""

    # App Home shows the 5 most-recently-saved first, so save the supporting decisions first and the
    # iconic ones LAST (in reverse display order) — the jury sees these five on top, matching 'Try these'.
    display_top = [
        "Primary datastore",
        "Observability vendor",
        "Temporal job queue",
        "Auth build vs buy",
        "Pricing model",
    ]
    order = [n for n in ARCS if n not in display_top] + list(reversed(display_top))

    saved = 0
    for name in order:
        arc = ARCS[name]
        ts = 1_000_000.0
        memories = []
        for th in arc:
            ts += 1
            found = pick_decision(_thread_msgs(th), require_decision=True)
            memories.append(
                {
                    "source_message": th.parent.text,  # keeps the leading [Mon DD] for ordering
                    "what_happened_next": found[0] if found else "",
                    "channel": th.channel,
                    "author": (found[1] if found else "") or th.parent.author,
                    "ts": f"{ts:.6f}",
                    "permalink": permalink(th.marker),
                }
            )
        arc_obj = build_arc(name, memories)
        if arc_obj is None or arc_obj.inconclusive:
            print(f"  ⏭️  skip (inconclusive) {name}")
            continue
        standing = next(
            (
                e
                for e in reversed(arc_obj.timeline)
                if e.state in ("adopted", "reversed") and e.permalink
            ),
            None,
        )
        headline, icon = HEADLINES.get(name, ("", "✅"))
        record = {
            "topic": name,
            "decision": arc_obj.standing_decision,
            "headline": headline,
            "icon": icon,
            "owner": arc_obj.owner,
            "at": arc_obj.decided_at,
            "channel": standing.channel if standing else "",
            "n": arc_obj.times_discussed,
            "url": arc_obj.sources[-1] if arc_obj.sources else "",
        }
        link = "🔗" if record["url"] else "⚠️ no-link"
        print(
            f"  {icon} {link} {name}: {headline or record['decision'][:50]}  ({record['owner']}, {record['at']})"
        )
        if not dry:
            save_decision(record, saved_by="seed")
            saved += 1

    print(
        f"\n[seed-store] {'DRY RUN — nothing written' if dry else f'{saved} decision(s) written'}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
