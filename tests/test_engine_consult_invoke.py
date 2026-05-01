"""Process invocation logging."""

from __future__ import annotations

from harness import engine
from harness.scenario import ScenarioBundle
from harness.world import build_world_from_scenario
from pathlib import Path


def test_apply_process_invocations_emits_rows():
    scenario = {
        "id": "p1",
        "goals": {"max_turns": 2},
        "channels": [{"name": "#team"}],
        "characters": [{"id": "u1"}],
        "work_items": [],
        "teams": [],
        "org_initial_vitals": {"delivery_progress": 0, "happiness": 50},
    }
    world = build_world_from_scenario(scenario, {})
    bundle = ScenarioBundle(
        path=Path("."),
        scenario=scenario,
        setting_text="",
        character_bodies={},
        best_practices=[],
    )
    events = engine.apply_process_invocations(
        [{"kind": "consult", "topic": "design"}, {"kind": "unknown_kind", "x": 1}],
        world=world,
        bundle=bundle,
        source="coach",
        turn=2,
    )
    kinds = [e["kind"] for e in events]
    assert "process_invocation" in kinds
    assert "process_invocation_unhandled" in kinds


def test_tick_empty():
    scenario = {
        "id": "p2",
        "goals": {"max_turns": 1},
        "channels": [],
        "characters": [],
        "work_items": [],
        "teams": [],
        "org_initial_vitals": {"delivery_progress": 0, "happiness": 50},
    }
    world = build_world_from_scenario(scenario, {})
    bundle = ScenarioBundle(
        path=Path("."),
        scenario=scenario,
        setting_text="",
        character_bodies={},
        best_practices=[],
    )
    assert engine.tick(world, bundle) == []
