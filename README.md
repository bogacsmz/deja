# Déjà — the team memory that stops you re-litigating decisions

When a decision, claim, or proposal comes up in a Slack channel, **Déjà** quietly surfaces the
concrete past thread your team already had on it — **and what was decided** — as a clean Block Kit
memory card. Its memory is also a standalone **MCP tool** any external agent can call.

> ⏳ **Déjà vu — your team already discussed this** · #eng
> *"Kicking off the migration from Redis to Temporal…"*
> 🧵 **What happened next:** *"Rolling back — operational overhead isn't worth it. Sticking with Redis."*
> 🔒 Only searches channels you can access · powered by Legibright

**Slack Agent Builder Challenge · New Slack Agent track.** Two required technologies: **RTS recall**
(`assistant.search.context`, permission-aware) + **MCP** (a `recall_memory` tool). The LLM trigger
runs on a **Claude Max subscription** — no paid API key.

## Quick start
```bash
pip install -e ".[test]"
cp .env.sample .env         # SLACK_USER_TOKEN (xoxp) + CLAUDE_CODE_OAUTH_TOKEN (`claude setup-token`)
slack run                   # the Slack app (Socket Mode): auto-trigger + memory cards
python -m deja.mcp_server   # the MCP server (stdio) for external agents
python scripts/verify_all.py   # the cross-phase gate — one green table (below)
```

## How it was built (the phase story)
| Phase | What shipped | Gate proof in `verify_all` |
|---|---|---|
| 1 · Skeleton | Bolt app boots, listeners wired | `deja imports`, `manifest valid` |
| 2 · Recall (RTS) | Forgotten thread resurfaces, deterministic | `recall resurfaces decision 3/3` |
| 3 · Judge→Recall→Reply | LLM trigger (Max subscription), end-to-end | `pipeline PASS`, `trigger 4/4` |
| 4 · Block Kit card | Interactive card + App Home + privacy | `card builders`, `App Home view` |
| 5 · MCP | `recall_memory` tool + real stdio client | `recall_memory unit`, `MCP stdio` |
| 6 · Seed | Realistic multi-author workspace + decision arcs | `seed integrity`, `seed dry-run` |
| 6 · Decision arc | Timeline + standing decision + owner + INCONCLUSIVE + save→Canvas | `arc synthesis`, `arc card`, `decision store` |
| 7 · Docs | Architecture · submission · demo · review | — |

**One command proves it all:** `python scripts/verify_all.py` → a phase-by-phase ✅ table
(`--no-live` for the hermetic subset in CI). See [`docs/architecture.md`](docs/architecture.md) ·
[`docs/SUBMISSION.md`](docs/SUBMISSION.md) · [`docs/DEMO.md`](docs/DEMO.md) ·
[`docs/PHASE-REVIEW.md`](docs/PHASE-REVIEW.md) · [`docs/HARDENING.md`](docs/HARDENING.md).

## Does the arc beat search? (benchmark)

Measured on the **exact live pipeline** (`judge(sentence) → recall_arc`). On a **held-out set we
never tuned on**, single-hit search surfaces the standing decision **1/6** times and drifts onto an
unrelated decision **1/4** times. **Déjà → 4/6 recurring · 3/5 single, never invents one (0/4).**
(Dev set: 6/6 recurring, 7/7 single, 0 false decisions.)

> **We surface this, we don't hide it:** Slack's Real-Time Search is rate-limited to ~1 call every
> few minutes (measured `Retry-After: 288s`), so a 100+-query *live* benchmark isn't possible. The
> benchmark runs the **real engine including the LLM judge** (cached) through a reproducible RTS-free
> mirror, **calibrated to live** — sentences that fail live route through the same code here and were
> verified to match. Held-out recurring is **4/6, not higher**, because the live card path is
> lexical-only (no LLM in the hot path): the semantic-gap cases ('observability stack' → the *Datadog*
> decision) need the LLM expansion, which is available but off live for speed. Honest cost, not a
> hidden failure. Method + limits: [`docs/BENCHMARK.md`](docs/BENCHMARK.md) · `python benchmarks/run.py --md`.

## Robustness — silence is cheap, a confident wrong answer is fatal

`benchmarks/adversarial.py` runs the live pipeline over **83 hostile queries** (paraphrases,
never-discussed topics, **lexical traps**, nonsense, typos, multi-topic, other languages,
false-premise provocations) and splits the result honestly: **correct 45 · MISS 6 · correct-silent
32 · CONFIDENT-WRONG 0** → **recall 88%, zero confident-wrong.** It runs against a *permissive* mirror
(a superset of live search), so a trap like "did we decide to **buy** a boat?" surfaces the "**BUYING**
auth" thread and the **grounding gate** must reject it: a decision shows only if one of the query's
distinctive *subject* words is in the retrieved threads — a shared action verb (buy · migrate · drop ·
launch) is not a topic match. See [`docs/ROBUSTNESS.md`](docs/ROBUSTNESS.md).

## MCP — query Déjà's memory from any agent
```bash
python -m deja.mcp_server   # stdio (Cursor/Claude Desktop); DEJA_MCP_TRANSPORT=streamable-http for remote
```
Wire into Cursor (`.cursor/mcp.json`) or Claude Desktop (`claude_desktop_config.json`):
```json
{ "mcpServers": { "deja": {
  "command": ".venv/bin/python", "args": ["-m", "deja.mcp_server"],
  "cwd": "/absolute/path/to/slackhack"
} } }
```
`recall_memory(query, channel=None, limit=3)` → `{summary, memories:[{source_message,
what_happened_next, channel, author, ts, permalink, score}], searched}`. Permission-aware (user
token). Verify end-to-end with `python scripts/mcp_smoke.py`.

## Layout
`deja/` — the engine (`recall`/RTS · `trigger`/LLM · `thread` enrichment · `card` · `memory` ·
`mcp_server`) · `listeners/` — Slack events/actions/views · `scripts/` — seed + verify + smoke ·
`tests/` · `docs/`. The Bolt starter-template README this was scaffolded from is preserved below.

---

# Starter Agent for Slack (Bolt for Python and Claude Agent SDK)

A minimal starter template for building AI-powered Slack agents with [Bolt for Python](https://docs.slack.dev/tools/bolt-python/) and the [Claude Agent SDK](https://platform.claude.com/docs/en/agent-sdk/overview) using models from [Anthropic](https://www.anthropic.com). Works with the [Slack MCP Server](https://github.com/slackapi/slack-mcp-server) to search messages, read channels, send messages, and manage canvases — all from within your agent.

## App Overview

The starter agent interacts with users through four entry points:

* **App Home** — Displays a welcome message with instructions on how to interact.
* **Direct Messages** — Users message the agent directly. It responds in-thread, maintaining context across follow-ups.
* **Channel @mentions** — Mention the agent in any channel to get a response without leaving the conversation.
* **Assistant Panel** — Users click _Add Agent_ in Slack, select the agent, and pick from suggested prompts or type a message.

The template also includes one example tool (emoji reactions). Add your own tools to customize it for your use case.

### Slack MCP Server

When connected to the [Slack MCP Server](https://github.com/slackapi/slack-mcp-server), the agent can search messages and files, read channel history and threads, send and schedule messages, and create and update canvases. When deployed with OAuth (HTTP mode), the agent automatically connects to the Slack MCP Server using the user's token.

## Setup

Before getting started, make sure you have a development workspace where you have permissions to install apps.

### Developer Program

Join the [Slack Developer Program](https://api.slack.com/developer-program) for exclusive access to sandbox environments for building and testing your apps, tooling, and resources created to help you build and grow.

### Create the Slack app

<details><summary><strong>Using Slack CLI</strong></summary>

Install the latest version of the Slack CLI for your operating system:

- [Slack CLI for macOS & Linux](https://docs.slack.dev/tools/slack-cli/guides/installing-the-slack-cli-for-mac-and-linux/)
- [Slack CLI for Windows](https://docs.slack.dev/tools/slack-cli/guides/installing-the-slack-cli-for-windows/)

You'll also need to log in if this is your first time using the Slack CLI.

```sh
slack login
```

#### Initializing the project

```sh
slack create my-starter-agent --template slack-samples/bolt-python-starter-agent --subdir claude-agent-sdk
cd my-starter-agent
```

</details>

<details><summary><strong>Using App Settings</strong></summary>

#### Create Your Slack App

1. Open [https://api.slack.com/apps/new](https://api.slack.com/apps/new) and choose "From an app manifest"
2. Choose the workspace you want to install the application to
3. Copy the contents of [manifest.json](./manifest.json) into the text box that says `*Paste your manifest code here*` (within the JSON tab) and click _Next_
4. Review the configuration and click _Create_
5. Click _Install to Workspace_ and _Allow_ on the screen that follows. You'll then be redirected to the App Configuration dashboard.

#### Environment Variables

Before you can run the app, you'll need to store some environment variables.

1. Rename `.env.sample` to `.env`.
2. Open your apps setting page from [this list](https://api.slack.com/apps), click _OAuth & Permissions_ in the left hand menu, then copy the _Bot User OAuth Token_ into your `.env` file under `SLACK_BOT_TOKEN`.

```sh
SLACK_BOT_TOKEN=YOUR_SLACK_BOT_TOKEN
```

3. Click _Basic Information_ from the left hand menu and follow the steps in the _App-Level Tokens_ section to create an app-level token with the `connections:write` scope. Copy that token into your `.env` as `SLACK_APP_TOKEN`.

```sh
SLACK_APP_TOKEN=YOUR_SLACK_APP_TOKEN
```

#### Initializing the project

```sh
git clone https://github.com/slack-samples/bolt-python-starter-agent.git my-starter-agent
cd my-starter-agent
```

</details>

### Setup your python virtual environment

```sh
python3 -m venv .venv
source .venv/bin/activate  # for Windows OS, .\.venv\Scripts\Activate instead should work
```

#### Install dependencies

```sh
pip install -r requirements.txt
```

## Providers

### Anthropic Setup

This app uses Claude through the Claude Agent SDK.

1. Create an API key from your [Anthropic dashboard](https://console.anthropic.com/settings/keys).
1. Rename `.env.sample` to `.env`.
3. Save the Anthropic API key to `.env`:

```sh
ANTHROPIC_API_KEY=YOUR_ANTHROPIC_API_KEY
```

## Development

### Starting the app

<details><summary><strong>Using the Slack CLI</strong></summary>

#### Slack CLI

```sh
slack run
```
</details>

<details><summary><strong>Using the Terminal</strong></summary>

#### Terminal

```sh
python3 app.py
```

</details>

<details><summary><strong>Using OAuth HTTP Server (with ngrok)</strong></summary>

#### OAuth HTTP Server

This mode uses an HTTP server instead of Socket Mode, which is required for OAuth-based distribution.

1. Install [ngrok](https://ngrok.com/download) and start a tunnel:

```sh
ngrok http 3000
```

2. Copy the `https://*.ngrok-free.app` URL from the ngrok output.

<details><summary><strong>Using Slack CLI</strong></summary>

#### Slack CLI

3. Update `manifest.json` for HTTP mode:
   - Set `socket_mode_enabled` to `false`
   - Replace `ngrok-free.app` with your ngrok domain (e.g. `YOUR_NGROK_SUBDOMAIN.ngrok-free.app`)

4. Create a new local dev app:

```sh
slack install -E local
```

5. _(Slack CLI < v4.1.0 only)_ Enable MCP for your app:
   - Run `slack app settings` to open your app's settings
   - Navigate to **Agents & AI Apps** in the left-side navigation
   - Toggle **Model Context Protocol** on

6. Update your `.env` OAuth environment variables:
   - Run `slack app settings` to open App Settings
   - Copy **Client ID**, **Client Secret**, and **Signing Secret**
   - Update `SLACK_REDIRECT_URI` in `.env` with your ngrok domain

```sh
SLACK_CLIENT_ID=YOUR_CLIENT_ID
SLACK_CLIENT_SECRET=YOUR_CLIENT_SECRET
SLACK_SIGNING_SECRET=YOUR_SIGNING_SECRET
SLACK_REDIRECT_URI=https://YOUR_NGROK_SUBDOMAIN.ngrok-free.app/slack/oauth_redirect
```

7. Start the app:

```sh
slack run app_oauth.py
```

8. Click the install URL printed in the terminal to install the app to your workspace via OAuth.

</details>

<details><summary><strong>Using the Terminal</strong></summary>

#### Terminal

3. Create your Slack app at [api.slack.com/apps/new](https://api.slack.com/apps/new) using [`manifest.json`](./manifest.json). Before pasting the manifest, set `socket_mode_enabled` to `false` and replace `ngrok-free.app` with your ngrok domain.

4. Install the app to your workspace and copy the following values into your `.env`:
   - **Signing Secret** — from _Basic Information_
   - **Bot User OAuth Token** — from _OAuth & Permissions_
   - **Client ID** and **Client Secret** — from _Basic Information_

```sh
SLACK_BOT_TOKEN=xoxb-YOUR_BOT_TOKEN
SLACK_CLIENT_ID=YOUR_CLIENT_ID
SLACK_CLIENT_SECRET=YOUR_CLIENT_SECRET
SLACK_SIGNING_SECRET=YOUR_SIGNING_SECRET
SLACK_REDIRECT_URI=https://YOUR_NGROK_SUBDOMAIN.ngrok-free.app/slack/oauth_redirect
```

Replace `your-subdomain` in `SLACK_REDIRECT_URI` with your ngrok subdomain.

5. Start the app:

```sh
python3 app_oauth.py
```

6. Click the install URL printed in the terminal to install the app to your workspace via OAuth.

</details>

> **Note:** Each time ngrok restarts, it generates a new URL. You'll need to update the ngrok domain in `manifest.json`, `SLACK_REDIRECT_URI` in your `.env`, and re-install the app.

</details>

### Using the App

Once the agent is running, there are several ways to interact:

**App Home** — Open the agent in Slack and click the _Home_ tab. You'll see a welcome message with instructions on how to interact.

**Direct Messages** — Open a DM with the agent. You'll see suggested prompts like _Write a Message_, _Summarize_, and _Brainstorm_ — pick one or type your own message. The agent replies in a thread. Send follow-up messages in the same thread and the agent will maintain the full conversation context.

**Channel @mentions** — Invite the agent to a channel by typing `/invite @agent-name` in the message box, then @mention it followed by your message. The agent responds in a thread so the channel stays clean.

**Assistant Panel** — Click _Add Agent_ in the top-right corner of Slack, select the agent from the list, then pick a suggested prompt or type a message.

### Linting

```sh
# Run ruff check from root directory for linting
ruff check

# Run ruff format from root directory for code formatting
ruff format
```

## Project Structure

### `manifest.json`

`manifest.json` is a configuration for Slack apps. With a manifest, you can create an app with a pre-defined configuration, or adjust the configuration of an existing app.

### `app.py`

`app.py` is the entry point for the application and is the file you'll run to start the server. This project uses `AsyncApp` from Bolt for Python, with all handlers running asynchronously.

### `app_oauth.py`

`app_oauth.py` is an alternative entry point that runs the app in HTTP mode instead of Socket Mode. This is intended for deployments that use OAuth for app distribution. See the HTTP Mode section under Development for setup instructions.

### `/listeners`

Every incoming request is routed to a "listener". This directory groups each listener based on the Slack Platform feature used.

**`/listeners/events`** — Handles incoming events:

- `app_home_opened.py` — Publishes the App Home view with a welcome message and MCP status.
- `app_mentioned.py` — Responds to @mentions in channels.
- `message.py` — Responds to direct messages from users.

**`/listeners/actions`** — Handles interactive components:

- `feedback_buttons.py` — Handles thumbs up/down feedback on agent responses.

**`/listeners/views`** — Builds Block Kit views:

- `app_home_builder.py` — Constructs the App Home Block Kit view.
- `feedback_builder.py` — Creates the feedback button block attached to responses.

### `/agent`

The `agent.py` file configures the Claude Agent SDK with a system prompt, tools registered via an MCP server, and a `run_agent()` async function that handles sending queries and collecting responses.

The `deps.py` file defines the `AgentDeps` dataclass passed to the agent at runtime, providing access to the Slack client and conversation context.

The `tools` directory contains one example tool (emoji reaction) defined using the `@tool` decorator from the Claude Agent SDK.

### `/thread_context`

The `store.py` file implements a thread-safe in-memory session ID store, keyed by channel and thread. The Claude Agent SDK manages conversation history server-side via sessions, so only session IDs need to be tracked locally for resuming conversations.

## Troubleshooting

### MCP Server connection error: `HTTP error 400 (Bad Request)`

If you see an error like:

```
Failed to connect to MCP server 'streamable_http: https://mcp.slack.com/mcp': HTTP error 400 (Bad Request)
```

This means the Slack MCP feature has not been enabled for your app. There is no manifest property for this yet, so it must be toggled on manually:

1. Run `slack app settings` to open your app's settings page (or visit [api.slack.com/apps](https://api.slack.com/apps) and select your app)
2. Navigate to **Agents & AI Apps** in the left-side navigation
3. Toggle **Slack Model Context Protocol** on
