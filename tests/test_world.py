"""Tests for in-memory world / goals."""

from pathlib import Path

from harness.scenario import load_scenario
from harness.world import (
    append_channel_message,
    build_world_from_scenario,
    format_agent_inbox,
    goal_abort,
    goal_met,
)

REPO = Path(__file__).resolve().parents[1]


def test_goal_met_requires_done_and_stress():
    bundle = load_scenario(REPO / "scenarios" / "two-devs-and-a-pm")
    w = build_world_from_scenario(bundle.scenario, bundle.character_bodies)
    assert not goal_met(w)
    for wi in w.work_items:
        wi.state = "done"
    assert goal_met(w)
    w.characters["marcus"].vitals["stress"] = 85
    assert not goal_met(w)
    for c in w.characters.values():
        c.vitals["stress"] = 40
    assert goal_met(w)


def test_goal_abort_high_stress():
    bundle = load_scenario(REPO / "scenarios" / "two-devs-and-a-pm")
    w = build_world_from_scenario(bundle.scenario, bundle.character_bodies)
    w.characters["priya"].vitals["stress"] = 99
    assert goal_abort(w)


def test_per_team_goal_two_squads():
    bundle = load_scenario(REPO / "scenarios" / "two-teams-shared-staging")
    w = build_world_from_scenario(bundle.scenario, bundle.character_bodies)
    assert w.team_members["falcon"] == ["alex", "jordan"]
    assert not goal_met(w)

    for wi in w.work_items:
        if wi.id in ("F1", "F2"):
            wi.state = "done"
    assert not goal_met(w)

    for wi in w.work_items:
        if wi.id in ("R1", "R2"):
            wi.state = "done"
    assert goal_met(w)


def test_goal_met_require_done_ids_skips_min_done_count():
    bundle = load_scenario(REPO / "scenarios" / "priority-conflict-coaching")
    w = build_world_from_scenario(bundle.scenario, bundle.character_bodies)
    assert not goal_met(w)
    for wi in w.work_items:
        if wi.id == "O1":
            wi.state = "done"
    assert not goal_met(w)
    for wi in w.work_items:
        if wi.id == "O2":
            wi.state = "done"
    for c in w.characters.values():
        c.vitals["stress"] = min(c.vitals["stress"], 75)
    assert goal_met(w)


def test_agent_inbox_includes_dm_thread():
    bundle = load_scenario(REPO / "scenarios" / "priority-conflict-coaching")
    w = build_world_from_scenario(bundle.scenario, bundle.character_bodies)
    ch = bundle.scenario["channels"][0]["name"]
    append_channel_message(w, "coach", "dm/lia", "Private: want to rehearse the ask?")
    append_channel_message(w, "lia", ch, "Team: I'll pull Director tomorrow.")
    text = format_agent_inbox(w, "lia", ch)
    assert "dm/lia" in text
    assert "rehearse" in text
    assert "Director" in text
