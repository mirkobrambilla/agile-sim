"""Tests for in-memory world / goals."""

from pathlib import Path

from harness.scenario import load_scenario
from harness.world import (
    append_channel_message,
    build_world_from_scenario,
    format_agent_inbox,
    goal_abort,
    goal_met,
    mentions_for_character,
    parse_mentions,
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


def test_parse_mentions_resolves_only_known_ids():
    ids = {"priya", "marcus", "lin"}
    text = "ping @priya and @MARCUS, ignore @ghost or naked email a@b.com"
    out = parse_mentions(text, ids)
    assert out == ["priya", "marcus"]


def test_parse_mentions_dedupes_in_order():
    ids = {"a", "b"}
    assert parse_mentions("@a @b @a @b", ids) == ["a", "b"]


def test_mentions_for_character_skips_self_and_unaddressed_dms():
    bundle = load_scenario(REPO / "scenarios" / "two-devs-and-a-pm")
    w = build_world_from_scenario(bundle.scenario, bundle.character_bodies)
    ids = set(w.characters.keys())
    w.turn = 3
    append_channel_message(w, "marcus", "#team", "hey @priya can you look")
    append_channel_message(w, "priya", "#team", "@priya self mention")
    append_channel_message(w, "coach", "dm/lin", "private to lin: @priya FYI")
    rows = mentions_for_character(w, "priya", ids, recent_turns=3)
    assert [m.author for m in rows] == ["marcus"]


def test_format_agent_inbox_surfaces_off_channel_mention():
    bundle = load_scenario(REPO / "scenarios" / "two-devs-and-a-pm")
    w = build_world_from_scenario(bundle.scenario, bundle.character_bodies)
    w.turn = 2
    append_channel_message(w, "lin", "#side-channel", "fyi @marcus please review")
    text = format_agent_inbox(w, "marcus", "#team")
    assert "Mentions" in text
    assert "#side-channel" in text
    assert "review" in text


def test_format_agent_inbox_does_not_duplicate_primary_channel_mentions():
    bundle = load_scenario(REPO / "scenarios" / "two-devs-and-a-pm")
    w = build_world_from_scenario(bundle.scenario, bundle.character_bodies)
    w.turn = 2
    append_channel_message(w, "lin", "#team", "ping @marcus on #team")
    text = format_agent_inbox(w, "marcus", "#team")
    assert text.count("ping @marcus on #team") == 1


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
