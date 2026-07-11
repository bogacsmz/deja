"""Contradiction / staleness detection against a standing decision.

When someone proposes something the team already settled, Déjà shouldn't just show the old thread
— it should say so. Given the message that triggered a recall and the synthesized `DecisionArc`,
this returns a short warning when the proposal re-opens (or outright contradicts) a standing
decision. Heuristic and deterministic (no LLM) so it stays hermetic and predictable; it errs toward
*staleness* ("already settled") and only escalates to *contradiction* when the standing decision is
clearly a rejection and the new message is clearly re-proposing the rejected thing.
"""

from __future__ import annotations

from dataclasses import dataclass

from deja.arc import DecisionArc

# Standing decision reads like a REJECTION of the topic ("we're not doing X").
_REJECTION = (
    "rolling back",
    "rolled back",
    "roll back",
    "dropping",
    "dropped",
    "reverted",
    "not worth",
    "staying on",
    "moved away",
    "killed",
    "abandon",
    "against",
    "instead of",
    "back to",
    "we tried",
    "isn't worth",
)
# New message reads like a fresh PROPOSAL to adopt something.
_PROPOSAL = (
    "should we",
    "let's",
    "proposing",
    "propose",
    "can we",
    "thinking about",
    "want to",
    "migrate to",
    "switch to",
    "move to",
    "adopt",
    "go with",
    "bring back",
    "revisit",
    "go back to",
)


@dataclass(frozen=True)
class ConflictWarning:
    kind: str  # "contradiction" | "staleness"
    text: str


def detect_conflict(message: str, arc: DecisionArc | None) -> ConflictWarning | None:
    """Warn if `message` re-opens or contradicts the arc's standing decision. None otherwise.

    Requires a real standing decision (not inconclusive). A single non-recurring thread is not
    enough on its own to warn *unless* the message clearly re-proposes something already rejected.
    """
    if arc is None or arc.inconclusive or not arc.standing_decision:
        return None

    sd, msg = arc.standing_decision.lower(), message.lower()
    rejected = any(r in sd for r in _REJECTION)
    proposing = any(p in msg for p in _PROPOSAL)

    if not (arc.is_recurring or rejected):
        return None  # a lone, non-rejecting decision isn't worth a warning

    who = f" ({arc.owner}, {arc.decided_at})" if arc.owner else ""
    if rejected and proposing:
        return ConflictWarning(
            "contradiction",
            f"⚠️ Heads up — the team already settled this the other way{who}: "
            f"“{arc.standing_decision}” Re-opening it means overturning a standing decision.",
        )
    return ConflictWarning(
        "staleness",
        f"⚠️ This has come up before — discussed {arc.times_discussed}× , "
        f"standing decision{who}: “{arc.standing_decision}”",
    )
