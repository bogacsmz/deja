from slack_bolt.async_app import AsyncApp

from .deja_card import (
    handle_not_relevant,
    handle_open_thread,
    handle_save_decision,
)
from .feedback_buttons import handle_feedback_button


def register(app: AsyncApp):
    app.action("feedback")(handle_feedback_button)
    app.action("deja_open_thread")(handle_open_thread)
    app.action("deja_not_relevant")(handle_not_relevant)
    app.action("deja_save_decision")(handle_save_decision)
