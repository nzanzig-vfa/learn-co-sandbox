# Onsite Agent → Interactive Slack Bot — Implementation Plan

> Status: **PLAN ONLY** (no code written yet). Goal: turn the one-way "Onsite agent"
> into a bot you can `@mention`, that replies in-thread, and holds a multi-turn conversation.

## Why the current setup feels bad

The screenshots show messages footed with **"Sent using Claude"** in `#onsite-jul-2026`.
That means the Onsite agent (a **Claude console managed agent**) is *pushing* messages
one-way on a trigger/schedule. Typing `@Onsit…` does nothing because:

1. There is **no Slack bot user** registered for it — so nothing autocompletes.
2. Nothing is **listening** for your messages — a managed agent only wakes on its trigger.
3. It has no notion of **replying in a thread** or continuing a conversation.

Being "interactive, replies to me, taggable" is not a setting on the existing agent —
it requires wrapping the managed agent in a real **Slack App** with a bot user and an
event handler. The managed agent (its instructions/brain) stays; we add ears and a mouth.

## Target architecture (from the official "managed agents Slack bot" cookbook)

```
You: @OnsiteOS what's the plan for Tuesday afternoon?
   ↓ (app_mention event)
Slack App (bot user "OnsiteOS")  ──►  Bot service (Bolt for Python, Socket Mode)
   ↓ ack < 3s, "On it…" in thread
   ↓ create/continue a managed-agent session via Anthropic Sessions API
Onsite managed agent runs ──► streams events back ──► bot posts reply in the SAME thread
   ↓
You reply in thread ──► same session continues (multi-turn, keeps context)
```

Four components:

| Component | Role |
|---|---|
| **Slack App** (bot user `OnsiteOS`) | Receives `@mention`/thread events, posts replies. Socket Mode = no public URL needed. |
| **Bot service** (`slack_bolt` for Python) | Always-on process. Maps Slack threads → agent sessions, relays events both ways. |
| **Onsite managed agent** | Your existing agent in the Claude console — its instructions are the "brain". Reused by ID, not rebuilt. |
| **Anthropic SDK** | `client.beta.sessions.*` to create/continue sessions and stream agent output. |

## Concrete behavior to build

1. **Taggable** — `@OnsiteOS …` triggers `app_mention`; bot acks immediately, posts "On it" in-thread.
2. **Replies in-thread** — bot streams the agent's output and posts the final answer to `thread_ts`.
3. **Multi-turn** — a `thread_ts → session_id` map lets follow-up replies continue the same session (context + files persist). Handled via the `message` event, ignoring the bot's own messages/edits.
4. **Progress signal** — post "Working on it…" when the agent starts using tools, so it doesn't look frozen.
5. **(Keep) proactive briefings** — the existing scheduled onsite briefing can stay, but now posts *as* the `OnsiteOS` bot user and (optionally) opens a thread you can reply into.

## Build steps (once approved)

1. **Create the Slack App** at api.slack.com/apps using a manifest with:
   - Socket Mode enabled
   - Scopes: `app_mentions:read`, `chat:write`, `channels:history`, `files:read`, `files:write`, `im:history`
   - Event subscriptions: `app_mention`, `message.channels` (and `message.im` for DMs)
   - Bot display name: `OnsiteOS`
   - Tokens: Bot User OAuth Token (`xoxb-…`) and App-Level Token (`xapp-…`, scope `connections:write`)
2. **Wire to the existing Onsite managed agent** — capture its `environment_id`, `agent_id`, `agent_version` from the Claude console (no new agent needed).
3. **Write the bot service** (~150 lines): `on_mention`, `on_thread_reply`, `start_session`, `relay_stream`, with markdown→Slack `mrkdwn` conversion and 3900-char truncation.
4. **Host it** — small always-on process (Fly.io / Render / a container on Sandbar infra). Socket Mode means no inbound URL/ingress required.
5. **Invite the bot** to `#onsite-jul-2026` and test: mention, reply, follow-up.
6. **Migrate the scheduled push** to post through the bot identity (optional, second pass).

## What I need from you to execute

- [ ] **Slack admin** ability to create/install an app in your workspace (or someone who can).
- [ ] **Onsite agent IDs** from the Claude console: environment, agent, and version.
- [ ] **Anthropic API key** with the managed-agents beta enabled.
- [ ] **A host** for the always-on bot (your call — Fly.io/Render/internal).
- [ ] Decide: keep the **proactive scheduled briefings** in addition to interactivity? (recommended: yes)

## Note on where the code should live

This repo (`learn-co-sandbox`) is the **Learn.co IDE sandbox**, which auto-syncs and is
not a good home for a production always-on service. Recommend a dedicated repo (e.g.
`onsite-slack-bot`) for the bot. This plan doc is fine to keep here.

## Alternative (faster, less tailored)

The official **Claude in Slack** integration already lets you `@Claude` and routes to
Claude Code. It's quick to enable, but it's *generic Claude*, not *your tuned Onsite
agent* — so it won't carry the onsite-specific instructions/behavior. The custom bot
above is the right call if "the Onsite agent" specifically is what you want taggable.

## Sources
- Managed agents Slack data bot cookbook — https://platform.claude.com/cookbook/managed-agents-slack-data-bot
- Claude in Slack (official) — https://code.claude.com/docs/en/slack
- Claude Code on the web — https://code.claude.com/docs/en/claude-code-on-the-web
