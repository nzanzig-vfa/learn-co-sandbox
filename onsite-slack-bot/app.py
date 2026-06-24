"""
OnsiteOS Slack listener.

Wraps your EXISTING Onsite managed agent (reused by ID — nothing is rebuilt) so it is:
  - taggable:   @OnsiteOS ... triggers a session
  - replying:   answers in the same Slack thread
  - multi-turn: follow-up replies in the thread continue the same agent session

Run: python app.py   (requires the env vars in .env.example)
Socket Mode => no public URL/ingress needed, but the PROCESS must stay running (hosting required).
"""

import io
import os
import re
import threading

import requests
from anthropic import Anthropic
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler

BETA = "managed-agents-2026-04-01"

# --- existing Onsite managed agent (from the Anthropic console) ---
ONSITE = {
    "environment_id": os.environ["ONSITE_ENV_ID"],
    "agent_id": os.environ["ONSITE_AGENT_ID"],
    "agent_version": os.environ["ONSITE_AGENT_VERSION"],
}

app = App(token=os.environ["SLACK_BOT_TOKEN"])
client = Anthropic()  # reads ANTHROPIC_API_KEY

# thread_ts -> session_id. In-memory: fine for one process. Swap for Redis/DB if you
# run multiple replicas or need it to survive restarts.
thread_sessions: dict[str, str] = {}

SLACK_LIMIT = 3900


def to_mrkdwn(md: str) -> str:
    """Minimal Markdown -> Slack mrkdwn. Slack uses *bold*, _italic_, <url|text>."""
    md = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r"<\2|\1>", md)   # links
    md = re.sub(r"\*\*([^*]+)\*\*", r"*\1*", md)               # **bold** -> *bold*
    md = re.sub(r"^#{1,6}\s*(.+)$", r"*\1*", md, flags=re.M)   # headings -> bold
    return md


def post(channel: str, thread_ts: str, text: str) -> None:
    text = to_mrkdwn(text)
    if len(text) > SLACK_LIMIT:
        text = text[:SLACK_LIMIT] + "\n_(truncated — see full session trace)_"
    app.client.chat_postMessage(channel=channel, thread_ts=thread_ts, text=text)


def relay_stream(session_id: str, channel: str, thread_ts: str) -> None:
    """Stream the agent's session events and mirror them into the Slack thread."""
    summary = ""
    posted_progress = False
    for ev in client.beta.sessions.events.stream(session_id, betas=[BETA]):
        if ev.type == "agent.message":
            for b in ev.content:
                if b.type == "text" and b.text.strip():
                    summary = b.text
        elif ev.type == "agent.tool_use" and not posted_progress:
            post(channel, thread_ts, "Working on it…")
            posted_progress = True
        elif ev.type == "session.status_idle":
            break
        elif ev.type == "session.status_terminated":
            post(channel, thread_ts,
                 f"Session ended unexpectedly. Trace: https://platform.claude.com/sessions/{session_id}")
            return
    if summary:
        post(channel, thread_ts, summary)

    # forward any files the agent produced (e.g. an itinerary doc)
    outputs = client.beta.files.list(scope_id=session_id, betas=[BETA])
    for f in outputs.data:
        if getattr(f, "downloadable", False):
            content = client.beta.files.download(f.id).read()
            app.client.files_upload_v2(
                channel=channel, thread_ts=thread_ts, filename=f.filename, content=content)


def start_session(channel: str, thread_ts: str, question: str) -> None:
    session = client.beta.sessions.create(
        environment_id=ONSITE["environment_id"],
        agent={"type": "agent", "id": ONSITE["agent_id"], "version": ONSITE["agent_version"]},
        title=question[:80] or "Onsite request",
        metadata={"slack_channel": channel, "slack_thread_ts": thread_ts},
        betas=[BETA],
    )
    thread_sessions[thread_ts] = session.id
    client.beta.sessions.events.send(
        session.id,
        events=[{"type": "user.message", "content": [{"type": "text", "text": question}]}],
        betas=[BETA],
    )
    relay_stream(session.id, channel, thread_ts)


def continue_session(session_id: str, channel: str, thread_ts: str, text: str) -> None:
    client.beta.sessions.events.send(
        session_id,
        events=[{"type": "user.message", "content": [{"type": "text", "text": text}]}],
        betas=[BETA],
    )
    relay_stream(session_id, channel, thread_ts)


@app.event("app_mention")
def on_mention(event, ack):
    ack()  # Slack requires ack < 3s
    channel = event["channel"]
    thread_ts = event.get("thread_ts") or event["ts"]
    question = event["text"].split(">", 1)[-1].strip()  # text after the @mention
    post(channel, thread_ts, "On it.")
    threading.Thread(target=start_session, args=(channel, thread_ts, question), daemon=True).start()


@app.event("message")
def on_thread_reply(event, ack):
    ack()
    thread_ts = event.get("thread_ts")
    if event.get("subtype") or event.get("bot_id"):
        return  # skip edits/deletes and the bot's own messages
    if not thread_ts or thread_ts not in thread_sessions:
        return  # only continue threads we already own
    threading.Thread(
        target=continue_session,
        args=(thread_sessions[thread_ts], event["channel"], thread_ts, event["text"]),
        daemon=True,
    ).start()


if __name__ == "__main__":
    SocketModeHandler(app, os.environ["SLACK_APP_TOKEN"]).start()
