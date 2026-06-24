# OnsiteOS — interactive Slack bot for the Onsite managed agent

Makes your existing **Onsite managed agent** taggable and conversational in Slack. It does
**not** rebuild the agent — it reuses it by ID and adds a Slack listener in front of it.

## Pieces
- `app.py` — the listener (Bolt + Socket Mode). Handles `@OnsiteOS` mentions and thread
  follow-ups, relays to/from the managed-agent session.
- `slack_app_manifest.yaml` — paste into api.slack.com/apps to create the Slack app.
- `manage_agent.py` — inspect/edit the managed agent's instructions via the Anthropic API.
- `onsite_agent_instructions.md` — draft instructions tuned for interactive Slack use.
- `.env.example` — the credentials/IDs you must supply.

## Setup
1. **Create the Slack app**: api.slack.com/apps → *Create New App* → *From manifest* →
   paste `slack_app_manifest.yaml`. Install to workspace. Copy the Bot token (`xoxb-`) and
   create an App-level token (`xapp-`, scope `connections:write`).
2. **Fill `.env`**: `cp .env.example .env` and add the Slack tokens, `ANTHROPIC_API_KEY`,
   and your Onsite agent's `ONSITE_ENV_ID` / `ONSITE_AGENT_ID` / `ONSITE_AGENT_VERSION`.
3. **(Optional) edit the agent**: `python manage_agent.py --show` then
   `python manage_agent.py --update-instructions onsite_agent_instructions.md`.
4. **Run**: `pip install -r requirements.txt && python app.py`
5. **Invite** `@OnsiteOS` into `#onsite-jul-2026` and mention it.

## Hosting
Socket Mode needs no inbound URL, but the process must stay running. Deploy to Fly.io,
Render, or any always-on container/host. Set the `.env` values as host secrets.

## Notes / limits
- `thread_sessions` is in-memory: restarting the bot forgets thread→session links. Use a
  small persistent store (Redis/DB) if you run multiple replicas or need restart survival.
- This `learn-co-sandbox` repo auto-syncs and is a poor production home; consider moving
  this folder to a dedicated repo before going live.
