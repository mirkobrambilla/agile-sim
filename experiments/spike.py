#!/usr/bin/env python3
"""Phase-1 spike: one-file multi-agent + coach loop, real OpenRouter calls, JSONL outputs.

Run from repo root:
  uv run python experiments/spike.py --model google/gemma-4-26b-a4b-it:free
  # or: python experiments/spike.py (after pip install deps and PYTHONPATH=src)
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import yaml
from pydantic import BaseModel, Field

# Repo root = parent of experiments/
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from openrouter import OpenRouterClient  # noqa: E402


# --- Structured outputs (subset of agentic-design.md) ---


class ChannelPost(BaseModel):
    channel: str
    content: str
    parent_id: str | None = None


class AgentTurnOutput(BaseModel):
    narrative: str = ""
    channel_posts: list[ChannelPost] = Field(default_factory=list)
    vital_self_report: dict[str, int] = Field(default_factory=dict)
    work_item_updates: list[dict] = Field(
        default_factory=list,
        description="Each: {id: str, state: backlog|doing|done}",
    )


class CoachTurnOutput(BaseModel):
    narrative: str = ""
    channel_posts: list[ChannelPost] = Field(default_factory=list)
    vital_nudges: list[dict] = Field(
        default_factory=list,
        description="Each: {character_id, vital_name, delta} integers, applied after clamp",
    )


def _extract_json_blob(text: str) -> str:
    text = text.strip()
    fence = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if fence:
        return fence.group(1).strip()
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        return text[start : end + 1]
    return text


def parse_agent_output(raw: str) -> AgentTurnOutput:
    blob = _extract_json_blob(raw)
    return AgentTurnOutput.model_validate_json(blob)


def parse_coach_output(raw: str) -> CoachTurnOutput:
    blob = _extract_json_blob(raw)
    return CoachTurnOutput.model_validate_json(blob)


@dataclass
class Character:
    id: str
    name: str
    role: str
    personality: str
    vitals: dict[str, int]  # energy, motivation, stress


@dataclass
class WorkItem:
    id: str
    title: str
    state: str  # backlog | doing | done
    owner_id: str


@dataclass
class World:
    turn: int = 0
    max_turns: int = 10
    characters: dict[str, Character] = field(default_factory=dict)
    work_items: list[WorkItem] = field(default_factory=list)
    org: dict[str, int] = field(
        default_factory=lambda: {"delivery_progress": 0, "happiness": 50}
    )
    messages: list[dict] = field(default_factory=list)


def clamp_vital(v: int, lo: int = 0, hi: int = 100) -> int:
    return max(lo, min(hi, v))


def world_to_context_lines(w: World, char_id: str) -> str:
    c = w.characters[char_id]
    lines = [
        f"Turn {w.turn} / max {w.max_turns}.",
        f"You are {c.name} ({c.role}). {c.personality}",
        f"Your vitals: energy={c.vitals['energy']}, motivation={c.vitals['motivation']}, "
        f"stress={c.vitals['stress']}.",
        "Work items:",
    ]
    for wi in w.work_items:
        tag = f" [owner: {wi.owner_id}]" if wi.owner_id else ""
        lines.append(f"  - {wi.id}: {wi.title} — state={wi.state}{tag}")
    lines.append(f"Org snapshot: delivery_progress={w.org['delivery_progress']}, happiness={w.org['happiness']}.")
    recent = [m for m in w.messages if m.get("channel") == "#team"][-8:]
    if recent:
        lines.append("Recent #team messages:")
        for m in recent:
            lines.append(f"  - @{m['author']}: {m['content'][:300]}")
    return "\n".join(lines)


AGENT_SYSTEM = """You are simulating one person in a fictional org. Stay in character.
Respond with a single JSON object only (no markdown outside JSON), matching this shape:
{
  "narrative": "short prose what you did this turn",
  "channel_posts": [{"channel": "#team", "content": "...", "parent_id": null}],
  "vital_self_report": {"energy": <int -5..+5 delta>, "motivation": <delta>, "stress": <delta>},
  "work_item_updates": [{"id": "W1", "state": "doing"}]
}
Rules: vital_self_report values are DELTAS applied to your current vitals (clamped 0-100).
You may post 0-1 messages to #team this turn. You may move work you own toward done realistically.
work_item_updates states: backlog, doing, done only."""

COACH_SYSTEM = """You are the coach (outside the story) observing the simulation.
You see recent #team traffic and aggregate vitals next user message.
Respond with ONE JSON object only:
{
  "narrative": "your private reasoning",
  "channel_posts": [{"channel": "#team", "content": "...", "parent_id": null}],
  "vital_nudges": [{"character_id": "priya", "vital_name": "stress", "delta": -5}]
}
vital_nudges are optional small nudges (-10..+10). Use sparingly. You may post one short coaching note in #team."""


def append_message(w: World, author: str, content: str, channel: str = "#team") -> None:
    w.messages.append(
        {
            "id": str(uuid.uuid4())[:8],
            "turn": w.turn,
            "author": author,
            "channel": channel,
            "content": content,
        }
    )


def apply_agent_output(w: World, char_id: str, out: AgentTurnOutput) -> None:
    c = w.characters[char_id]
    deltas = out.vital_self_report or {}
    for k, d in deltas.items():
        if k in c.vitals and isinstance(d, int):
            c.vitals[k] = clamp_vital(c.vitals[k] + d)
    for post in out.channel_posts:
        if post.channel == "#team" and post.content.strip():
            append_message(w, char_id, post.content.strip(), "#team")
    for upd in out.work_item_updates:
        wid = str(upd.get("id", ""))
        st = str(upd.get("state", "")).lower()
        if st not in ("backlog", "doing", "done"):
            continue
        for wi in w.work_items:
            if wi.id == wid and wi.owner_id == char_id:
                wi.state = st
    # Simple org heuristics
    done = sum(1 for wi in w.work_items if wi.state == "done")
    w.org["delivery_progress"] = min(100, done * 20)
    avg_mot = sum(x.vitals["motivation"] for x in w.characters.values()) / len(w.characters)
    w.org["happiness"] = clamp_vital(int(avg_mot))


def apply_coach_output(w: World, out: CoachTurnOutput) -> None:
    for post in out.channel_posts:
        if post.channel == "#team" and post.content.strip():
            append_message(w, "coach", post.content.strip(), "#team")
    for n in out.vital_nudges:
        cid = str(n.get("character_id", "")).lower()
        vn = str(n.get("vital_name", ""))
        d = n.get("delta")
        if cid not in w.characters or vn not in w.characters[cid].vitals:
            continue
        if not isinstance(d, int):
            continue
        d = max(-10, min(10, d))
        w.characters[cid].vitals[vn] = clamp_vital(w.characters[cid].vitals[vn] + d)


def goal_met(w: World) -> bool:
    done = sum(1 for wi in w.work_items if wi.state == "done")
    if done < 4:
        return False
    if any(c.vitals["stress"] > 80 for c in w.characters.values()):
        return False
    return True


def goal_failed(w: World) -> bool:
    return any(c.vitals["stress"] > 95 for c in w.characters.values())


def build_world() -> World:
    return World(
        turn=1,
        characters={
            "priya": Character(
                id="priya",
                name="Priya",
                role="Tech lead",
                personality="Direct, protective of the team; escalates early when blocked.",
                vitals={"energy": 70, "motivation": 75, "stress": 55},
            ),
            "marcus": Character(
                id="marcus",
                name="Marcus",
                role="Backend engineer",
                personality="Quiet, deep focus; hates context switching.",
                vitals={"energy": 65, "motivation": 70, "stress": 50},
            ),
            "lin": Character(
                id="lin",
                name="Lin",
                role="PM",
                personality="Optimistic, pressure from above; wants dates.",
                vitals={"energy": 75, "motivation": 72, "stress": 58},
            ),
        },
        work_items=[
            WorkItem("W1", "API contract for partner integration", "backlog", "priya"),
            WorkItem("W2", "Rate limiting + auth middleware", "doing", "marcus"),
            WorkItem("W3", "Customer comms for launch window", "doing", "lin"),
            WorkItem("W4", "Load test harness", "backlog", "marcus"),
            WorkItem("W5", "Exec demo deck", "backlog", "lin"),
        ],
    )


BEST_PRACTICES_SPIKE = """
- address_blockers_early: surface blockers in #team within one turn
- private_before_public: nudge individuals before calling them out publicly
- protect_focus: avoid thrashing engineers with new priorities mid-stream
""".strip()


def run_spike(model: str, max_turns: int, out_dir: Path) -> None:
    secrets_path = ROOT / "secrets.yaml"
    if not secrets_path.exists():
        raise SystemExit(f"Missing {secrets_path}")
    secrets = yaml.safe_load(secrets_path.read_text()) or {}
    key = secrets.get("openrouter_api_key") or secrets.get("OPENROUTER_API_KEY")
    if not key:
        raise SystemExit("secrets.yaml needs openrouter_api_key")

    client = OpenRouterClient(api_key=key)
    world = build_world()
    world.max_turns = max_turns

    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_root = out_dir / run_id
    run_root.mkdir(parents=True, exist_ok=True)

    timeline_fp = run_root / "timeline.jsonl"
    snapshots_fp = run_root / "snapshots.jsonl"
    messages_fp = run_root / "messages.jsonl"
    llm_fp = run_root / "llm_calls.jsonl"

    def log_event(obj: dict) -> None:
        with timeline_fp.open("a", encoding="utf-8") as f:
            f.write(json.dumps(obj, default=str) + "\n")

    def log_snapshot() -> None:
        snap = {
            "turn": world.turn,
            "characters": {k: asdict(v) for k, v in world.characters.items()},
            "work_items": [asdict(wi) for wi in world.work_items],
            "org": dict(world.org),
        }
        with snapshots_fp.open("a", encoding="utf-8") as f:
            f.write(json.dumps(snap, default=str) + "\n")
        with messages_fp.open("w", encoding="utf-8") as f:
            for m in world.messages:
                f.write(json.dumps(m, default=str) + "\n")

    def log_llm(payload: dict) -> None:
        with llm_fp.open("a", encoding="utf-8") as f:
            f.write(json.dumps(payload, default=str) + "\n")

    log_event({"kind": "run_start", "run_id": run_id, "model": model})

    while world.turn <= world.max_turns:
        print(f"--- Turn {world.turn} ---")
        log_event({"kind": "turn_start", "turn": world.turn})

        for cid, character in world.characters.items():
            ctx = world_to_context_lines(world, cid)
            user_msg = (
                f"{ctx}\n\nOutput JSON only for your actions this turn. "
                f"Your character_id for work_item_updates ownership is {cid}."
            )
            messages = [
                {"role": "system", "content": AGENT_SYSTEM},
                {"role": "user", "content": user_msg},
            ]
            t0 = time.perf_counter()
            raw, usage = client.chat_text(
                model=model,
                messages=messages,
                temperature=0.65,
                max_tokens=1200,
            )
            dt_ms = int((time.perf_counter() - t0) * 1000)
            log_llm(
                {
                    "turn": world.turn,
                    "role": "agent",
                    "character": cid,
                    "model": model,
                    "usage": usage,
                    "latency_ms": dt_ms,
                }
            )
            try:
                out = parse_agent_output(raw)
            except Exception as e:
                log_event({"kind": "parse_error", "turn": world.turn, "who": cid, "error": str(e)})
                out = AgentTurnOutput(narrative="(parse failed)", channel_posts=[])

            apply_agent_output(world, cid, out)
            log_event(
                {
                    "kind": "agent_turn",
                    "turn": world.turn,
                    "character": cid,
                    "narrative": out.narrative,
                    "posts": [p.model_dump() for p in out.channel_posts],
                    "vital_deltas": out.vital_self_report,
                }
            )
            print(f"  {cid}: {out.narrative[:120]}...")

        coach_ctx = (
            f"Turn {world.turn}.\nBest practices:\n{BEST_PRACTICES_SPIKE}\n\n"
            f"Characters:\n"
            + "\n".join(
                f"  {cid}: stress={c.vitals['stress']}, motivation={c.vitals['motivation']}"
                for cid, c in world.characters.items()
            )
            + "\nWork:\n"
            + "\n".join(f"  {wi.id} {wi.state} — {wi.title}" for wi in world.work_items)
            + "\nLast messages:\n"
            + "\n".join(
                f"  @{m['author']}: {m['content'][:200]}"
                for m in world.messages[-12:]
            )
        )
        t0 = time.perf_counter()
        raw_c, usage_c = client.chat_text(
            model=model,
            messages=[
                {"role": "system", "content": COACH_SYSTEM},
                {"role": "user", "content": coach_ctx},
            ],
            temperature=0.5,
            max_tokens=800,
        )
        dt_ms = int((time.perf_counter() - t0) * 1000)
        log_llm(
            {
                "turn": world.turn,
                "role": "coach",
                "model": model,
                "usage": usage_c,
                "latency_ms": dt_ms,
            }
        )
        try:
            cout = parse_coach_output(raw_c)
        except Exception as e:
            log_event({"kind": "parse_error", "turn": world.turn, "who": "coach", "error": str(e)})
            cout = CoachTurnOutput()
        apply_coach_output(world, cout)
        log_event(
            {
                "kind": "coach_turn",
                "turn": world.turn,
                "narrative": cout.narrative,
                "nudges": cout.vital_nudges,
            }
        )
        print(f"  coach: {cout.narrative[:100]}...")

        log_snapshot()

        if goal_met(world):
            print("Goal met.")
            break
        if goal_failed(world):
            print("Abort: stress crisis.")
            break

        world.turn += 1

    summary = {
        "run_id": run_id,
        "final_turn": world.turn,
        "goal_met": goal_met(world),
        "work_done": sum(1 for wi in world.work_items if wi.state == "done"),
        "final_vitals": {k: v.vitals for k, v in world.characters.items()},
        "org": world.org,
    }
    (run_root / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    log_event({"kind": "run_end", "summary": summary})
    print(f"Wrote {run_root}")


def main() -> None:
    ap = argparse.ArgumentParser(description="Spike: multi-agent + coach harness")
    ap.add_argument("--model", default="google/gemma-4-26b-a4b-it:free", help="OpenRouter model id")
    ap.add_argument("--max-turns", type=int, default=10)
    ap.add_argument("--out", type=Path, default=ROOT / "runs" / "spike")
    args = ap.parse_args()
    run_spike(args.model, args.max_turns, args.out)


if __name__ == "__main__":
    main()
