from listeners.views.app_home_builder import build_app_home_view
from listeners.views.feedback_builder import build_feedback_blocks


def test_build_feedback_blocks():
    blocks = build_feedback_blocks()

    assert len(blocks) > 0
    # The block should contain a feedback action
    block_dict = blocks[0].to_dict()
    action_ids = [e["action_id"] for e in block_dict["elements"]]
    assert "feedback" in action_ids


def test_home_view_structure():
    """Déjà's App Home is a valid home view with a header and sections (not barren)."""
    view = build_app_home_view()

    assert view["type"] == "home"
    block_types = [b["type"] for b in view["blocks"]]
    assert "header" in block_types
    assert block_types.count("section") >= 2  # what it is + how it works + privacy


def _all_text(view: dict) -> str:
    parts: list[str] = []
    for b in view["blocks"]:
        if b.get("type") in ("section", "header") and isinstance(b.get("text"), dict):
            parts.append(b["text"]["text"])
        for e in b.get("elements", []):
            if isinstance(e, dict) and isinstance(e.get("text"), str):
                parts.append(e["text"])
    return " ".join(parts)


def test_home_view_explains_and_states_privacy():
    """It says what Déjà does and makes the permission-aware privacy promise."""
    text = _all_text(build_app_home_view())
    assert "what your team already decided" in text  # what it does
    assert "channels you can access" in text  # permission-aware privacy promise


def test_home_view_ignores_legacy_args():
    """Legacy scaffold args are accepted (compat) but no longer change the view."""
    assert (
        build_app_home_view(install_url="x", is_connected=True) == build_app_home_view()
    )
