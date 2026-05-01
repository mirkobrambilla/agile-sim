"""Channel posting rules and DM ownership."""

from __future__ import annotations

from harness.runner import apply_agent_output, apply_coach_output
from harness.schemas import AgentTurnOutput, ChannelPost, CoachTurnOutput
from harness.world import build_world_from_scenario, can_post


def _mini_scenario() -> dict:
    return {
        "id": "eng-test",
        "goals": {"max_turns": 3},
        "channels": [
            {"name": "#team", "coach_engagement": "post"},
            {"name": "#announce", "coach_engagement": "read"},
        ],
        "characters": [{"id": "alice"}, {"id": "bob"}],
        "work_items": [],
        "teams": [],
        "org_initial_vitals": {"delivery_progress": 0, "happiness": 50},
    }


def test_can_post_team_read_blocks_everyone():
    sc = _mini_scenario()
    assert can_post(author="alice", channel="#announce", scenario=sc)[0] is False
    assert can_post(author="coach", channel="#announce", scenario=sc)[0] is False


def test_dm_only_owner_or_coach():
    sc = _mini_scenario()
    assert can_post(author="alice", channel="dm/alice", scenario=sc) == (True, None)
    assert can_post(author="bob", channel="dm/alice", scenario=sc)[0] is False
    assert can_post(author="coach", channel="dm/alice", scenario=sc) == (True, None)


def test_apply_agent_rejects_wrong_dm(tmp_path):
    world = build_world_from_scenario(_mini_scenario(), {})
    out = AgentTurnOutput(
        channel_posts=[ChannelPost(channel="dm/bob", content="hi from alice")]
    )
    rej = apply_agent_output(
        world, "alice", out, vital_delta_cap=8, channel="#team", scenario=_mini_scenario()
    )
    assert rej and rej[0]["reason"] == "dm_wrong_owner"
    assert len(world.messages) == 0


def test_apply_coach_rejects_read_only_channel():
    world = build_world_from_scenario(_mini_scenario(), {})
    cout = CoachTurnOutput(
        channel_posts=[ChannelPost(channel="#announce", content="nope")]
    )
    rej = apply_coach_output(
        world, cout, "#team", 10, scenario=_mini_scenario()
    )
    assert any(r["reason"].startswith("channel_") for r in rej)
