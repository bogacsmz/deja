import re

from slack_bolt.async_app import AsyncApp

from .deja_card import (
    handle_ask_owner,
    handle_not_relevant,
    handle_open_thread,
    handle_save_decision,
)
from .feedback_buttons import handle_feedback_button


def register(app: AsyncApp):
    app.action("feedback")(handle_feedback_button)
    # Every "open thread" button carries a UNIQUE action_id (Slack rejects a view with duplicates),
    # so match them all by prefix — they only ack (the URL opens natively).
    app.action(re.compile(r"^deja_open"))(handle_open_thread)
    app.action("deja_not_relevant")(handle_not_relevant)
    app.action("deja_save_decision")(handle_save_decision)
    app.action("deja_ask_owner")(handle_ask_owner)
