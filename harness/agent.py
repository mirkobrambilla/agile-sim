"""Character (agent) turn: render prompt, call LLM, return structured output."""

from __future__ import annotations

import json
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from harness.llm import chat_structured, parse_model
from harness.schemas import AgentTurnOutput
from harness.scenario import ScenarioBundle
from harness.world import World, format_agent_inbox, primary_team_channel, describe_channels_policy_for_agents

_PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"


def _env() -> Environment:
    return Environment(
        loader=FileSystemLoader(str(_PROMPTS_DIR)),
        autoescape=False,
        trim_blocks=True,
        lstrip_blocks=True,
    )


def build_agent_system(*, vital_delta_cap: int) -> str:
    return f"""You are portraying one person inside a fictional organizational simulation.
Stay in character. Be concise.

You may post to the **simulation team chat** or to your **private DM with the coach** using channel `dm/<your_character_id>` (same id as in the prompt).

You MUST respond with a single JSON object only (no markdown fences, no commentary).
The JSON must match this structure:
{{
  "narrative": "short prose about what you did/felt this turn",
  "channel_posts": [{{"channel": "#team-channel OR dm/your_id", "content": "message text", "parent_id": null}}],
  "process_invocations": [],
  "vital_self_report": {{ "energy": <int>, "motivation": <int>, "stress": <int> }},
  "work_item_updates": [{{"id": "W1", "state": "doing"}}]
}}

Optional `process_invocations`: array of objects with `kind` such as `consult`, `invoke`, or `tick`. Use [] if none.

Rules for vital_self_report:
- Only include keys you want to change; each value is a **delta** added to your current vital.
- Each delta must be between -{vital_delta_cap} and +{vital_delta_cap} inclusive.
- Vitals stay in 0–100 after the harness applies deltas.

Rules for work_item_updates:
- Only move work items **you own** (your character id matches owner_id).
- state must be one of: backlog, doing, done.
"""


def render_agent_user_message(
    bundle: ScenarioBundle,
    world: World,
    char_id: str,
    *,
    channel: str,
    vital_delta_cap: int,
) -> str:
    ch = world.characters[char_id]
    tmpl = _env().get_template("agent_turn.j2")
    work_lines = []
    for wi in world.work_items:
        own = " (you own)" if wi.owner_id == char_id else ""
        work_lines.append(f"- {wi.id}: {wi.title} — state={wi.state}{own}, owner={wi.owner_id}")
    recent_text = format_agent_inbox(world, char_id, channel)
    return tmpl.render(
        setting=bundle.setting_text.strip(),
        name=ch.name,
        role=ch.role,
        char_id=char_id,
        backstory=ch.backstory or "(none)",
        turn=world.turn,
        max_turns=world.max_turns,
        vitals_json=json.dumps(ch.vitals, sort_keys=True),
        work_items_text="\n".join(work_lines) or "(none)",
        org_json=json.dumps(world.org, sort_keys=True),
        channel=channel,
        recent_messages_text=recent_text,
        vital_delta_cap=vital_delta_cap,
        channels_policy=describe_channels_policy_for_agents(bundle.scenario),
    )


def run_agent_turn(
    *,
    client: object,
    model: str,
    bundle: ScenarioBundle,
    world: World,
    char_id: str,
    vital_delta_cap: int = 8,
    temperature: float = 0.65,
    max_tokens: int = 1400,
) -> tuple[AgentTurnOutput, str, dict]:
    channel = primary_team_channel(bundle.scenario)
    system = build_agent_system(vital_delta_cap=vital_delta_cap)
    user = render_agent_user_message(
        bundle,
        world,
        char_id,
        channel=channel,
        vital_delta_cap=vital_delta_cap,
    )
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]
    return chat_structured(
        client,
        model,
        messages,
        temperature,
        max_tokens,
        lambda s: parse_model(s, AgentTurnOutput),
        retries=1,
    )

