"""Tests for scenario folder loader."""

from pathlib import Path

from harness.scenario import load_scenario

REPO = Path(__file__).resolve().parents[1]


def test_load_two_devs_and_pm():
    b = load_scenario(REPO / "scenarios" / "two-devs-and-a-pm")
    assert b.scenario.get("id") == "two-devs-and-a-pm"
    assert len(b.character_bodies) == 3
    assert "priya" in b.character_bodies
    assert "api" in b.character_bodies["priya"].lower()


def test_load_two_teams_shared_staging():
    b = load_scenario(REPO / "scenarios" / "two-teams-shared-staging")
    assert b.scenario.get("id") == "two-teams-shared-staging"
    assert len(b.scenario.get("teams") or []) == 2
    assert len(b.scenario.get("characters") or []) == 4
    assert len(b.best_practices) >= 2
    assert b.setting_text.strip()


def test_load_priority_conflict_coaching():
    b = load_scenario(REPO / "scenarios" / "priority-conflict-coaching")
    assert b.scenario.get("id") == "priority-conflict-coaching"
    assert b.scenario.get("goals", {}).get("require_done_ids") == ["O1", "O2"]
    assert len(b.character_bodies) == 3
