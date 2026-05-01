"""In-memory ledger for harness runs."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any
from uuid import uuid4


def clamp_int(v: int, lo: int = 0, hi: int = 100) -> int:
    return max(lo, min(hi, v))


@dataclass
class ChannelDef:
    """Scenario channel record (public #channels only)."""

    name: str
    coach_engagement: str  # post | read | none


@dataclass
class CharacterState:
    id: str
    name: str
    role: str
    backstory: str
    vitals: dict[str, int]


@dataclass
class WorkItemState:
    id: str
    title: str
    state: str
    owner_id: str


@dataclass
class Message:
    id: str
    turn: int
    author: str
    channel: str
    content: str


@dataclass
class World:
    turn: int
    max_turns: int
    goals: dict[str, Any]
    characters: dict[str, CharacterState]
    work_items: list[WorkItemState]
    org: dict[str, int]
    messages: list[Message] = field(default_factory=list)
    team_members: dict[str, list[str]] = field(default_factory=dict)

    def snapshot(self) -> dict[str, Any]:
        return {
            "turn": self.turn,
            "max_turns": self.max_turns,
            "goals": self.goals,
            "team_members": dict(self.team_members),
            "characters": {k: asdict(v) for k, v in self.characters.items()},
            "work_items": [asdict(w) for w in self.work_items],
            "org": dict(self.org),
            "messages": [asdict(m) for m in self.messages],
        }

    def recent_channel_messages(self, channel: str, limit: int = 12) -> list[Message]:
        got = [m for m in self.messages if m.channel == channel]
        return got[-limit:]


def format_agent_inbox(world: World, char_id: str, primary_channel: str) -> str:
    """Team channel + private coach DM thread for this character."""

    dm_ch = f"dm/{char_id}"
    team_msgs = world.recent_channel_messages(primary_channel, limit=12)
    dm_msgs = world.recent_channel_messages(dm_ch, limit=10)

    blocks: list[str] = []
    if dm_msgs:
        lines = [f"- @{m.author} (turn {m.turn}) [{dm_ch}]: {m.content}" for m in dm_msgs]
        blocks.append("### Direct messages (coach only in this thread)\n" + "\n".join(lines))
    if team_msgs:
        lines = [f"- @{m.author} (turn {m.turn}): {m.content}" for m in team_msgs]
        blocks.append(f"### Team channel {primary_channel}\n" + "\n".join(lines))
    if not blocks:
        return "(no messages yet)"
    return "\n\n".join(blocks)


def format_coach_dm_traffic(world: World, *, per_thread: int = 4) -> str:
    """Recent coach↔person DM threads (channels `dm/<id>`)."""

    dm_channels = sorted({m.channel for m in world.messages if m.channel.startswith("dm/")})
    if not dm_channels:
        return "(no DMs yet)"
    parts: list[str] = []
    for ch in dm_channels:
        msgs = world.recent_channel_messages(ch, limit=per_thread)
        if not msgs:
            continue
        lines = [f"  @{m.author} t{m.turn}: {m.content}" for m in msgs]
        parts.append(f"{ch}:\n" + "\n".join(lines))
    return "\n".join(parts) if parts else "(no DMs yet)"


def build_world_from_scenario(
    scenario: dict[str, Any],
    character_bodies: dict[str, str],
    start_turn: int = 1,
) -> World:
    g = scenario.get("goals") or {}
    goals = dict(g)
    max_turns = int(goals.get("max_turns", 10))

    chars: dict[str, CharacterState] = {}
    for ch in scenario.get("characters") or []:
        cid = str(ch["id"])
        v0 = ch.get("initial_vitals") or {}
        chars[cid] = CharacterState(
            id=cid,
            name=str(ch.get("name", cid)),
            role=str(ch.get("role", "")),
            backstory=character_bodies.get(cid, "").strip(),
            vitals={k: int(v) for k, v in v0.items()},
        )

    items: list[WorkItemState] = []
    for wi in scenario.get("work_items") or []:
        items.append(
            WorkItemState(
                id=str(wi["id"]),
                title=str(wi.get("title", "")),
                state=str(wi.get("state", "backlog")).lower(),
                owner_id=str(wi.get("owner_id", "")),
            )
        )

    org0 = scenario.get("org_initial_vitals") or {"delivery_progress": 0, "happiness": 50}
    org = {k: int(v) for k, v in org0.items()}

    team_members: dict[str, list[str]] = {}
    for t in scenario.get("teams") or []:
        tid = str(t["id"])
        team_members[tid] = [str(x) for x in t.get("member_ids", [])]

    return World(
        turn=start_turn,
        max_turns=max_turns,
        goals=goals,
        characters=chars,
        work_items=items,
        org=org,
        messages=[],
        team_members=team_members,
    )


def world_from_snapshot(data: dict[str, Any]) -> World:
    """Rebuild a World from `world.snapshot()`-shaped dict (e.g. last snapshots.jsonl row)."""

    chars_raw = data.get("characters") or {}
    chars: dict[str, CharacterState] = {}
    for cid, c in chars_raw.items():
        if not isinstance(c, dict):
            continue
        cid_s = str(c.get("id", cid))
        chars[cid_s] = CharacterState(
            id=cid_s,
            name=str(c.get("name", cid_s)),
            role=str(c.get("role", "")),
            backstory=str(c.get("backstory", "")),
            vitals={k: int(v) for k, v in (c.get("vitals") or {}).items()},
        )
    items: list[WorkItemState] = []
    for w in data.get("work_items") or []:
        if not isinstance(w, dict):
            continue
        items.append(
            WorkItemState(
                id=str(w.get("id", "")),
                title=str(w.get("title", "")),
                state=str(w.get("state", "backlog")).lower(),
                owner_id=str(w.get("owner_id", "")),
            )
        )
    msgs: list[Message] = []
    for m in data.get("messages") or []:
        if not isinstance(m, dict):
            continue
        msgs.append(
            Message(
                id=str(m.get("id", "")),
                turn=int(m.get("turn", 0)),
                author=str(m.get("author", "")),
                channel=str(m.get("channel", "")),
                content=str(m.get("content", "")),
            )
        )
    return World(
        turn=int(data.get("turn", 1)),
        max_turns=int(data.get("max_turns", 10)),
        goals=dict(data.get("goals") or {}),
        characters=chars,
        work_items=items,
        org={k: int(v) for k, v in (data.get("org") or {}).items()},
        messages=msgs,
        team_members={str(k): list(v) for k, v in (data.get("team_members") or {}).items()},
    )


def normalize_coach_engagement(raw: str | None) -> str:
    v = (raw or "post").strip().lower()
    return v if v in {"post", "read", "none"} else "post"


def channel_defs_from_scenario(scenario: dict[str, Any]) -> dict[str, ChannelDef]:
    out: dict[str, ChannelDef] = {}
    for ch in scenario.get("channels") or []:
        name = str(ch.get("name", "")).strip()
        if not name.startswith("#"):
            continue
        out[name] = ChannelDef(
            name=name,
            coach_engagement=normalize_coach_engagement(ch.get("coach_engagement")),
        )
    return out


def character_ids_from_scenario(scenario: dict[str, Any]) -> set[str]:
    return {str(c.get("id", "")).strip() for c in scenario.get("characters") or [] if c.get("id")}


def can_post(*, author: str, channel: str, scenario: dict[str, Any]) -> tuple[bool, str | None]:
    """Whether a message may be appended; second value is a short machine reason if False."""

    ch = channel.strip()
    ids = character_ids_from_scenario(scenario)
    if ch.startswith("dm/"):
        recip = ch[3:].strip()
        if recip not in ids:
            return False, "dm_unknown_character"
        if author == "coach":
            return True, None
        if author == recip:
            return True, None
        return False, "dm_wrong_owner"
    if not ch.startswith("#"):
        return False, "invalid_channel"
    defs = channel_defs_from_scenario(scenario)
    cdef = defs.get(ch)
    if cdef is None:
        return False, "unknown_channel"
    if cdef.coach_engagement in ("read", "none"):
        return False, f"channel_{cdef.coach_engagement}"
    return True, None


def describe_channels_policy_for_agents(scenario: dict[str, Any]) -> str:
    defs = channel_defs_from_scenario(scenario)
    lines: list[str] = []
    for name in sorted(defs):
        ce = defs[name].coach_engagement
        lines.append(
            f"- `{name}` — mode **{ce}** (you may post only where mode is `post`; "
            "`read`/`none` are observation-only)."
        )
    lines.append(
        "- `dm/<your_character_id>` — private coach thread (only ever target your own id here)."
    )
    return "\n".join(lines) if lines else "(no team channels declared)"


def describe_channels_policy_for_coach(scenario: dict[str, Any]) -> str:
    lines: list[str] = ["Team channels and coach-engagement modes:"]
    for name, cdef in sorted(channel_defs_from_scenario(scenario).items()):
        lines.append(f"- `{cdef.name}` — **{cdef.coach_engagement}**")
    lines.append("- `dm/<character_id>` — private 1:1 threads")
    return "\n".join(lines)


def append_channel_message(
    world: World,
    author: str,
    channel: str,
    content: str,
) -> Message:
    m = Message(
        id=str(uuid4())[:10],
        turn=world.turn,
        author=author,
        channel=channel,
        content=content.strip(),
    )
    world.messages.append(m)
    return m


def apply_vital_deltas(world: World, char_id: str, deltas: dict[str, int], *, clamp_delta: int) -> None:
    c = world.characters[char_id]
    for name, d in deltas.items():
        if name not in c.vitals or not isinstance(d, int):
            continue
        d = max(-clamp_delta, min(clamp_delta, d))
        c.vitals[name] = clamp_int(c.vitals[name] + d)


def apply_work_updates(
    world: World,
    char_id: str,
    updates: list[dict[str, Any]],
) -> None:
    allowed = {"backlog", "doing", "done"}
    for upd in updates:
        wid = str(upd.get("id", ""))
        st = str(upd.get("state", "")).lower()
        if st not in allowed:
            continue
        for wi in world.work_items:
            if wi.id == wid and wi.owner_id == char_id:
                wi.state = st
    _recompute_org(world)


def _recompute_org(world: World) -> None:
    n = len(world.work_items)
    if n:
        done = sum(1 for wi in world.work_items if wi.state == "done")
        world.org["delivery_progress"] = clamp_int(round(100 * done / n))
    if world.characters:
        avg = sum(c.vitals.get("motivation", 0) for c in world.characters.values()) / len(
            world.characters
        )
        world.org["happiness"] = clamp_int(int(avg))


def apply_coach_nudges(world: World, nudges: list[dict[str, Any]], *, max_abs: int = 10) -> None:
    for n in nudges:
        cid = str(n.get("character_id", "")).lower()
        vn = str(n.get("vital_name", ""))
        d = n.get("delta")
        if cid not in world.characters or vn not in world.characters[cid].vitals:
            continue
        if not isinstance(d, int):
            continue
        d = max(-max_abs, min(max_abs, d))
        world.characters[cid].vitals[vn] = clamp_int(world.characters[cid].vitals[vn] + d)
    _recompute_org(world)


def primary_team_channel(scenario: dict[str, Any]) -> str:
    for ch in scenario.get("channels") or []:
        name = str(ch.get("name", "#team"))
        if name.startswith("#"):
            return name
    return "#team"


def goal_met(world: World) -> bool:
    g = world.goals
    max_s = int(g.get("max_stress_any", 80))
    for c in world.characters.values():
        if c.vitals.get("stress", 0) > max_s:
            return False

    req = g.get("require_done_ids")
    if req:
        need_ids = {str(x) for x in req}
        done_ids = {wi.id for wi in world.work_items if wi.state == "done"}
        if not need_ids.issubset(done_ids):
            return False

    per_team = g.get("per_team_min_done")
    if per_team is not None and world.team_members:
        need_team = int(per_team)
        for _tid, members in world.team_members.items():
            member_set = set(members)
            n_done = sum(
                1
                for wi in world.work_items
                if wi.state == "done" and wi.owner_id in member_set
            )
            if n_done < need_team:
                return False
        return True

    if g.get("require_done_ids"):
        return True

    need = int(g.get("min_done_work_items", 4))
    done = sum(1 for wi in world.work_items if wi.state == "done")
    return done >= need


def goal_abort(world: World) -> bool:
    lim = int(world.goals.get("abort_stress_any", 95))
    return any(c.vitals.get("stress", 0) > lim for c in world.characters.values())
