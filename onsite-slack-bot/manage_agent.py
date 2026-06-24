"""
Inspect and edit your EXISTING Onsite managed agent via the Anthropic API.
Managed agents are versioned, so "editing" = publishing a new version with updated
instructions. This never creates a new agent — it edits the one you already built.

Usage:
  python manage_agent.py --show                          # print current config
  python manage_agent.py --update-instructions FILE.md   # publish a new version

Env: ANTHROPIC_API_KEY, ONSITE_AGENT_ID (and ONSITE_ENV_ID for --show context).

NOTE: the exact method names in the managed-agents beta vary by SDK version. This
script fails loudly and prints the available attributes so the call can be corrected
against your installed `anthropic` version rather than guessing silently.
"""

import argparse
import os
import sys

from anthropic import Anthropic

BETA = "managed-agents-2026-04-01"
client = Anthropic()
AGENT_ID = os.environ.get("ONSITE_AGENT_ID")


def _agents_ns():
    ns = getattr(getattr(client, "beta", None), "agents", None)
    if ns is None:
        sys.exit("This anthropic SDK has no client.beta.agents. Run `pip show anthropic` "
                 f"and upgrade. Available beta attrs: {dir(getattr(client, 'beta', object()))}")
    return ns


def show():
    agents = _agents_ns()
    try:
        agent = agents.retrieve(AGENT_ID, betas=[BETA])
    except Exception as e:
        sys.exit(f"retrieve failed: {e}\nAvailable methods on client.beta.agents: {dir(agents)}")
    print(agent)


def update_instructions(path: str):
    with open(path) as f:
        instructions = f.read()
    agents = _agents_ns()
    versions = getattr(agents, "versions", None)
    try:
        if versions is not None:
            result = versions.create(agent_id=AGENT_ID, instructions=instructions, betas=[BETA])
        else:  # fallback: some SDKs expose update directly
            result = agents.update(AGENT_ID, instructions=instructions, betas=[BETA])
    except Exception as e:
        sys.exit(f"update failed: {e}\n"
                 f"client.beta.agents methods: {dir(agents)}\n"
                 f"versions methods: {dir(versions) if versions else 'n/a'}")
    print("Published new agent version:")
    print(result)
    print("\nUpdate ONSITE_AGENT_VERSION in .env to the new version above.")


if __name__ == "__main__":
    if not AGENT_ID:
        sys.exit("Set ONSITE_AGENT_ID in the environment.")
    p = argparse.ArgumentParser()
    p.add_argument("--show", action="store_true")
    p.add_argument("--update-instructions", metavar="FILE")
    args = p.parse_args()
    if args.show:
        show()
    elif args.update_instructions:
        update_instructions(args.update_instructions)
    else:
        p.print_help()
