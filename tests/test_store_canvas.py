"""Hermetic tests for the saved-decision store, Canvas rendering, and the App Home digest."""

import importlib
import json


def _fresh_store(tmp_path, monkeypatch):
    monkeypatch.setenv("DEJA_STORE", str(tmp_path / "decisions.json"))
    import deja.store as store

    importlib.reload(store)
    return store


_REC = {
    "topic": "Temporal",
    "decision": "rolling back to Redis",
    "owner": "Maya Chen",
    "at": "Apr 23",
    "n": 4,
    "url": "https://x/p1",
}


def test_save_list_and_weekly_count(tmp_path, monkeypatch):
    store = _fresh_store(tmp_path, monkeypatch)
    store.save_decision(_REC, saved_by="U1")
    got = store.list_decisions()
    assert len(got) == 1 and got[0]["decision"] == "rolling back to Redis"
    assert got[0]["owner"] == "Maya Chen" and got[0]["times_saved"] == 1
    assert store.count_saved_since(7) == 1


def test_resave_updates_and_bumps_counter(tmp_path, monkeypatch):
    store = _fresh_store(tmp_path, monkeypatch)
    store.save_decision(_REC, saved_by="U1")
    store.save_decision({**_REC, "decision": "still Redis, reaffirmed"}, saved_by="U2")
    got = store.list_decisions()
    assert len(got) == 1  # same topic → one entry
    assert got[0]["times_saved"] == 2 and "reaffirmed" in got[0]["decision"]


def test_canvas_markdown_has_ai_label_and_content(tmp_path, monkeypatch):
    _fresh_store(tmp_path, monkeypatch)
    from deja.canvas import render_canvas_markdown

    md = render_canvas_markdown([dict(_REC, times_discussed=4)])
    assert "AI-generated" in md and "Temporal" in md and "rolling back to Redis" in md
    assert "No decisions saved yet" in render_canvas_markdown([])


def test_canonical_memory_first(tmp_path, monkeypatch):
    """A saved decision on a named product is returned as a sourced arc, no retrieval needed."""
    store = _fresh_store(tmp_path, monkeypatch)
    store.save_decision(_REC, saved_by="U1")
    import importlib

    import deja.arc as arc_mod

    importlib.reload(arc_mod)
    hit = arc_mod._canonical("should we use Temporal for jobs?")  # names 'Temporal'
    assert hit is not None and not hit.inconclusive
    assert "rolling back" in hit.standing_decision.lower()
    assert hit.sources == ("https://x/p1",)  # sourced
    assert (
        arc_mod._canonical("should we adopt Kafka?") is None
    )  # unrelated -> no false canonical hit


def test_app_home_digest_shows_saved_decisions(tmp_path, monkeypatch):
    store = _fresh_store(tmp_path, monkeypatch)
    store.save_decision(_REC, saved_by="U1")
    import listeners.views.app_home_builder as b

    importlib.reload(b)
    view = b.build_app_home_view()
    flat = json.dumps(view)
    assert "Saved decisions" in flat and "Temporal" in flat and "circled back" in flat
