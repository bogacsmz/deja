"""Resolve a decision's OWNER (a display name on the arc) to a real Slack user id — so Déjà can
@-mention them from the 'Ask the decision owner' button. If the owner isn't a real workspace member,
resolution fails and the button is hidden (never a fake ping).

The workspace member list is fetched once and cached. `DEJA_OWNER_FALLBACK` (a user id) is an optional
demo aid: when a seeded persona ('Maya Chen') has no real account, it lets the coordination flow be
shown by routing to a stand-in. Unset in production → unresolved owners simply hide the button.
"""

from __future__ import annotations

import logging
import os
import re

_log = logging.getLogger(__name__)
_USER_ID = re.compile(r"^[UW][A-Z0-9]{6,}$")
_NAME_MAP: dict[str, str] | None = (
    None  # lowercased display/real name -> user id (cached)
)


async def _name_map(client) -> dict[str, str]:
    global _NAME_MAP
    if _NAME_MAP is not None:
        return _NAME_MAP
    mapping: dict[str, str] = {}
    try:
        cursor = None
        while True:
            resp = await client.users_list(limit=200, cursor=cursor)
            for u in resp.get("members", []):
                if u.get("deleted") or u.get("is_bot") or u.get("id") == "USLACKBOT":
                    continue
                prof = u.get("profile", {}) or {}
                for nm in (
                    prof.get("display_name"),
                    prof.get("real_name"),
                    u.get("real_name"),
                    u.get("name"),
                ):
                    if nm and nm.strip():
                        mapping.setdefault(nm.strip().lower(), u["id"])
            cursor = (resp.get("response_metadata") or {}).get("next_cursor")
            if not cursor:
                break
    except Exception as e:  # noqa: BLE001 — missing scope / transport: fall back to no match
        _log.debug("owner: users_list failed: %s", e)
    _NAME_MAP = mapping
    return mapping


async def resolve_owner_id(client, name: str) -> str:
    """Return the owner's Slack user id, or '' if they can't be resolved (→ hide the ask button)."""
    if not name or client is None:
        return ""
    if _USER_ID.match(name):
        return name  # already a raw id
    uid = (await _name_map(client)).get(name.strip().lower(), "")
    return uid or os.environ.get("DEJA_OWNER_FALLBACK", "")
