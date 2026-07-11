"""Slack Canvas — a living decision log the team can open as a native surface.

Each saved decision is mirrored into a single team Canvas, rendered from the store. The markdown is
AI-generated, so it carries an explicit AI label (Slack agent-design requirement). Rendering is a
pure function (testable); writing is best-effort and never raises — a Canvas failure must not break
the save flow. Requires the bot's `canvases:write` scope.
"""

from __future__ import annotations

import datetime as dt
import logging

from deja.store import get_meta, set_meta

_log = logging.getLogger(__name__)
CANVAS_TITLE = "Déjà — Team Decision Log"


def render_canvas_markdown(decisions: list[dict]) -> str:
    """The decision log as Canvas markdown. AI-labelled per Slack's agent-design guidance."""
    lines = [
        "# ⏳ Team Decision Log",
        "",
        "> 🤖 _AI-generated and maintained by Déjà — the standing decisions your team has saved._",
        "",
    ]
    if not decisions:
        lines.append(
            "_No decisions saved yet. Hit **💾 Save decision** on a Déjà card to start._"
        )
        return "\n".join(lines)
    for d in decisions:
        bits = []
        if d.get("owner"):
            bits.append(f"owner **{d['owner']}**")
        if d.get("at"):
            bits.append(f"decided {d['at']}")
        if d.get("times_discussed"):
            bits.append(f"discussed {d['times_discussed']}×")
        meta = " · ".join(bits)
        link = f"  ·  [source]({d['url']})" if d.get("url") else ""
        lines.append(f"## {d.get('topic', 'Decision')}")
        lines.append(d.get("decision", ""))
        if meta or link:
            lines.append(f"_{meta}_{link}" if meta else link.strip())
        lines.append("")
    lines.append(f"---\n_Updated {dt.datetime.now():%Y-%m-%d %H:%M}._")
    return "\n".join(lines)


async def write_canvas(client, decisions: list[dict]) -> str | None:
    """Create or update the team Canvas from the saved decisions. Returns the canvas id, or None on
    failure (best-effort — never raises)."""
    md = render_canvas_markdown(decisions)
    content = {"type": "markdown", "markdown": md}
    canvas_id = get_meta("canvas_id")
    try:
        if canvas_id:
            await client.canvases_edit(
                canvas_id=canvas_id,
                changes=[{"operation": "replace", "document_content": content}],
            )
            return canvas_id
    except Exception as e:  # noqa: BLE001 — fall through to (re)create
        _log.info("canvas: edit failed (%s); recreating", type(e).__name__)
    try:
        resp = await client.canvases_create(
            title=CANVAS_TITLE, document_content=content
        )
        canvas_id = resp.get("canvas_id")
        if canvas_id:
            set_meta("canvas_id", canvas_id)
        return canvas_id
    except Exception as e:  # noqa: BLE001 — Canvas is a nice-to-have, not the save's success
        _log.warning(
            "canvas: create failed (%s); decision still saved to the log",
            type(e).__name__,
        )
        return None
