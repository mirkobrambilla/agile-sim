"""Parity: `step_turn` matches one full CLI iteration of `run_once`."""

import json
from pathlib import Path

from harness.runner import _append_jsonl, character_turn_order, step_turn
from harness.runner import run_once as run_once_full
from harness.scenario import load_scenario

REPO = Path(__file__).resolve().parents[1]


class StubClient:
    def __init__(self, responses: list[str]) -> None:
        self._responses = list(responses)
        self._i = 0

    def chat_text(self, model, messages, temperature=0.7, max_tokens=4096):
        if self._i >= len(self._responses):
            raise RuntimeError("StubClient: no more scripted responses")
        r = self._responses[self._i]
        self._i += 1
        return r, {"input_tokens": 3, "output_tokens": 2, "cost": 0.0001}


def _agent_json(cid: str) -> str:
    return json.dumps(
        {
            "narrative": f"{cid} ok",
            "channel_posts": [
                {"channel": "#team", "content": f"hi {cid}", "parent_id": None},
            ],
            "vital_self_report": {"stress": -1},
            "work_item_updates": [],
            "process_invocations": [],
        }
    )


def _coach_json() -> str:
    return json.dumps(
        {
            "narrative": "ok",
            "channel_posts": [],
            "vital_nudges": [],
            "process_invocations": [],
        }
    )


def test_step_turn_one_iteration_matches_run_once(tmp_path: Path) -> None:
    bundle = load_scenario(REPO / "scenarios" / "two-devs-and-a-pm")
    bundle.scenario["goals"]["max_turns"] = 1

    seq: list[str] = []
    for cid in ["priya", "marcus", "lin"]:
        seq.append(_agent_json(cid))
    seq.append(_coach_json())

    stub_a = StubClient(list(seq))
    run_a = tmp_path / "via_run_once"
    run_a.mkdir()
    summary_a = run_once_full(
        bundle,
        stub_a,
        agent_model="stub",
        coach_model="stub",
        run_root=run_a,
        seed=42,
        coach_mode="llm",
        coach_preset=None,
    )

    stub_b = StubClient(list(seq))
    run_b = tmp_path / "via_step"
    run_b.mkdir()
    from harness.world import build_world_from_scenario, primary_team_channel

    channel = primary_team_channel(bundle.scenario)
    world = build_world_from_scenario(bundle.scenario, bundle.character_bodies)
    order = character_turn_order(bundle)
    _append_jsonl(
        run_b / "timeline.jsonl",
        {
            "kind": "run_start",
            "scenario_id": bundle.scenario.get("id"),
            "agent_model": "stub",
            "coach_model": "stub",
            "coach_mode": "llm",
        },
    )

    du, stop = step_turn(
        world,
        bundle,
        stub_b,
        agent_model="stub",
        coach_model="stub",
        run_root=run_b,
        vital_delta_cap=8,
        coach_nudge_cap=10,
        coach_mode="llm",
        coach_preset=None,
        preset_id=None,
        channel=channel,
        order=order,
        verbose=False,
        progress_prefix="",
    )

    assert stop is None
    assert du["input_tokens"] > 0
    assert stub_a._i == stub_b._i == len(seq)

    lines_a = (run_a / "timeline.jsonl").read_text(encoding="utf-8").strip().splitlines()
    lines_b = (run_b / "timeline.jsonl").read_text(encoding="utf-8").strip().splitlines()
    kinds_a = [json.loads(x)["kind"] for x in lines_a if x.strip()]
    kinds_b = [json.loads(x)["kind"] for x in lines_b if x.strip()]
    assert kinds_b == kinds_a[: len(kinds_b)]

    snap_a = [json.loads(x) for x in (run_a / "snapshots.jsonl").read_text().splitlines() if x.strip()][0]
    snap_b = [json.loads(x) for x in (run_b / "snapshots.jsonl").read_text().splitlines() if x.strip()][0]
    assert snap_a["turn"] == snap_b["turn"] == 1
    assert summary_a["final_turn"] == world.turn
