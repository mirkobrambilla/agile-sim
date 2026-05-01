"""Helpers used by inspector / vitals (Phase 2)."""

from __future__ import annotations

import json
from pathlib import Path

import yaml

from harness.web.run_reader import (
    channel_meta_for,
    recent_posts_for_character,
    vitals_history_for_character,
    work_item_timeline_events,
)


def _bundle(tmp: Path):
    scen = tmp / "scenario.yaml"
    scen.write_text(
        yaml.safe_dump(
            {
                "id": "t",
                "channels": [{"name": "#team", "member_ids": ["a"], "coach_engagement": "post"}],
                "characters": [{"id": "a"}],
            }
        ),
        encoding="utf-8",
    )
    run = tmp / "r1"
    run.mkdir()
    (run / "meta.yaml").write_text(
        yaml.safe_dump({"scenario_path": str(scen)}, sort_keys=False),
        encoding="utf-8",
    )
    (run / "summary.json").write_text(
        json.dumps({"final_turn": 2, "goal_met": False, "totals": {}}),
        encoding="utf-8",
    )
    (run / "messages.jsonl").write_text(
        json.dumps(
            {"id": "1", "turn": 1, "author": "a", "channel": "dm/a", "content": "dm1"}
        )
        + "\n"
        + json.dumps(
            {"id": "2", "turn": 2, "author": "coach", "channel": "dm/a", "content": "dm2"}
        )
        + "\n"
        + json.dumps(
            {"id": "3", "turn": 2, "author": "a", "channel": "#team", "content": "pub"}
        )
        + "\n",
        encoding="utf-8",
    )
    (run / "snapshots.jsonl").write_text(
        json.dumps(
            {
                "turn": 1,
                "world": {"characters": {"a": {"vitals": {"energy": 50, "motivation": 5, "stress": 5}}}},
            }
        )
        + "\n"
        + json.dumps(
            {
                "turn": 2,
                "world": {"characters": {"a": {"vitals": {"energy": 40, "motivation": 5, "stress": 5}}}},
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (run / "timeline.jsonl").write_text(
        json.dumps(
            {
                "kind": "agent_turn",
                "turn": 1,
                "character": "a",
                "work_updates": [{"id": "W1", "state": "doing"}],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    from harness.web.run_reader import load_run

    return load_run(run_dir=run, url_path="r1")


def test_vitals_history_for_character(tmp_path: Path) -> None:
    b = _bundle(tmp_path)
    h = vitals_history_for_character(b, "a", "energy")
    assert h == [(1, 50), (2, 40)]


def test_work_item_timeline_events(tmp_path: Path) -> None:
    b = _bundle(tmp_path)
    ev = work_item_timeline_events(b, "W1")
    assert len(ev) == 1
    assert ev[0]["turn"] == 1


def test_channel_meta_for(tmp_path: Path) -> None:
    b = _bundle(tmp_path)
    scen = {"channels": [{"name": "#team", "member_ids": ["a"], "coach_engagement": "post"}]}
    m = channel_meta_for(b, "#team", scen)
    assert m["message_count"] == 1
    assert "a" in m["members"]


def test_recent_posts_for_character(tmp_path: Path) -> None:
    b = _bundle(tmp_path)
    posts = recent_posts_for_character(b, "a")
    assert len(posts) == 3
    assert {p.content for p in posts} == {"dm1", "dm2", "pub"}
