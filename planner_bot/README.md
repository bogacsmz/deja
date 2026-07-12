# Planner Bot — the demo agent Déjà puts on trial

A deliberately tiny Slack app that plays the role of *any AI agent in your workspace*: it posts
action proposals to a channel. It knows nothing about Déjà. Déjà — running separately — watches the
channel and **brakes** the proposals that conflict with a standing decision (Mode B: governance
without the agent's cooperation).

Two separate Slack apps, two clearly different actors in the channel:

| Actor | App | Role |
|---|---|---|
| **Planner Bot** | this app (its own token) | proposes actions |
| **Déjà** | the main app (`slack run`) | judges them against standing decisions |

## Setup (≈2 minutes)

1. Create a new Slack app (From scratch) in the same workspace as Déjà: <https://api.slack.com/apps>.
2. **OAuth & Permissions → Bot Token Scopes:** add `chat:write` (and optionally `channels:read` if
   you want to pass a `#name` instead of a channel ID).
3. **Install to Workspace**, then copy the **Bot User OAuth Token** (`xoxb-…`).
4. Invite the Planner Bot to the demo channel: `/invite @Planner Bot`. (Déjà must already be a member
   of that channel too — it can only see messages in channels it's in.)

## Run the "Agents on trial" demo

```bash
export PLANNER_BOT_TOKEN=xoxb-…        # the Planner Bot's token — NOT Déjà's
python planner_bot/planner.py --channel C0123456789 --all      # posts all three, paced
# or one at a time:
python planner_bot/planner.py --channel C0123456789 --scene 2
```

(Use the channel **ID** — right-click the channel → *Copy link*, the `C…` at the end. A `#name` works
too if you added `channels:read`.)

## The three scenes

| # | Planner Bot posts | Déjà's live verdict |
|---|---|---|
| 1 | *"Proposing we add a usage add-on for heavy accounts."* | **ALLOW** — consistent with the standing pricing decision → Déjà stays **silent** (channel-clean). |
| 2 | *"Opening a PR to migrate the job queue to Temporal."* | ⚠️ **CONFLICTS** — the team rolled this back (Apr 23, @maya) → Déjà drops a sourced guardrail card. |
| 3 | *"Should we adopt an RFC process for big decisions?"* | 🤔 **INCONCLUSIVE** — discussed 3× but never decided → *"I won't invent one."* |

One AI stopping another, live, with sourced evidence — and refusing to fabricate on the third.

> Déjà never posts an ALLOW, never invents a verdict, and never reacts to its own or another bot's
> reply (no ping-pong). See the main README for the governance contract (`check_decision`).
