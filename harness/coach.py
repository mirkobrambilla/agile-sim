"""Coach turn: single structured LLM call per simulation round."""

from __future__ import annotations

import json
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from harness.llm import chat_structured, parse_model
from harness.schemas import CoachTurnOutput
from harness.scenario import ScenarioBundle
from harness.world import World, format_coach_dm_traffic, primary_team_channel, describe_channels_policy_for_coach

_PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"


def _env() -> Environment:
    return Environment(
        loader=FileSystemLoader(str(_PROMPTS_DIR)),
        autoescape=False,
        trim_blocks=True,
        lstrip_blocks=True,
    )


def build_coach_system(*, nudge_cap: int, primary_channel: str) -> str:
    return f"""You are the coach in a team simulation. You are outside the fiction.

Use **two channels** in `channel_posts`:
- **Team**: `{primary_channel}` — public leadership: framing, psychological safety, shared norms, inviting the group to solve problems (not micromanaging tickets).
- **Direct**: `dm/<character_id>` — private 1:1 with that person (e.g. rehearsal before a hard convo, naming impact without shaming, or sensitive feedback).

Return ONE JSON object only (no markdown). Shape:
{{
  "narrative": "short private reasoning",
  "channel_posts": [
    {{"channel": "{primary_channel}", "content": "…", "parent_id": null}},
    {{"channel": "dm/lia", "content": "…", "parent_id": null}}
  ],
  "vital_nudges": [{{"character_id": "priya", "vital_name": "stress", "delta": -5}}],
  "process_invocations": []
}}

`process_invocations` is optional; each item is an object with a `kind` string such as `request_approval`
(with fields like `gate`, `rationale`) or `change_deadline` (e.g. `id`, `due_turn`). Use [] when you have no process move.

vital_nudges are optional; each delta must be between -{nudge_cap} and +{nudge_cap}.
Use nudges **rarely** — prefer words. Nudging stress without addressing the system teaches the wrong lesson."""


def _best_practices_text(bundle: ScenarioBundle) -> str:
    lines = []
    for p in bundle.best_practices:
        pid = p.get("id", "")
        name = p.get("name", "")
        desc = p.get("description", "")
        lines.append(f"- **{pid}** — {name}: {desc}")
    return "\n".join(lines) if lines else "(none listed)"


def render_coach_user_message(bundle: ScenarioBundle, world: World, *, channel: str, nudge_cap: int) -> str:
    tmpl = _env().get_template("coach_turn.j2")
    excerpt = bundle.setting_text.strip()[:1200]
    goals = world.goals
    goals_text = json.dumps(goals, sort_keys=True, indent=2)
    c_lines = []
    for cid, c in world.characters.items():
        c_lines.append(f"- `{cid}` **{c.name}** ({c.role}): vitals={json.dumps(c.vitals)}")
    w_lines = [f"- {wi.id}: [{wi.state}] {wi.title} (owner {wi.owner_id})" for wi in world.work_items]
    recent = world.recent_channel_messages(channel, limit=16)
    recent_text = (
        "\n".join(f"- @{m.author} (turn {m.turn}): {m.content}" for m in recent)
        if recent
        else "(none)"
    )
    dm_text = format_coach_dm_traffic(world, per_thread=4)
    return tmpl.render(
        setting_excerpt=excerpt,
        turn=world.turn,
        max_turns=world.max_turns,
        goals_text=goals_text,
        characters_text="\n".join(c_lines),
        work_items_text="\n".join(w_lines),
        org_json=json.dumps(world.org, sort_keys=True),
        best_practices_text=_best_practices_text(bundle),
        channel=channel,
        recent_messages_text=recent_text,
        dm_traffic_text=dm_text,
        nudge_cap=nudge_cap,
        channels_policy=describe_channels_policy_for_coach(bundle.scenario),
    )


def run_coach_turn(
    *,
    client: object,
    model: str,
    bundle: ScenarioBundle,
    world: World,
    nudge_cap: int = 10,
    temperature: float = 0.5,
    max_tokens: int = 1000,
) -> tuple[CoachTurnOutput, str, dict]:
    channel = primary_team_channel(bundle.scenario)
    system = build_coach_system(nudge_cap=nudge_cap, primary_channel=channel)
    user = render_coach_user_message(bundle, world, channel=channel, nudge_cap=nudge_cap)
    messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]
    return chat_structured(
        client,
        model,
        messages,
        temperature,
        max_tokens,
        lambda s: parse_model(s, CoachTurnOutput),
        retries=1,
    )
