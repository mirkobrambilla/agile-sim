from __future__ import annotations

import json
from pathlib import Path

import yaml
from starlette.testclient import TestClient

from harness.scenario import list_scenarios
from harness.web.app import create_app
from harness.web.run_session import SESSIONS, RunSession
from harness.world import build_world_from_scenario, goal_met


def test_scenarios_list_view_and_copy(tmp_path: Path) -> None:
    scenarios_root = tmp_path / "scenarios"
    src = scenarios_root / "two-devs-and-a-pm"
    src.mkdir(parents=True, exist_ok=True)
    (src / "scenario.yaml").write_text(
        yaml.safe_dump(
            {
                "id": "two-devs-and-a-pm",
                "name": "Two devs and a PM",
                "channels": [{"name": "#team"}],
                "characters": [{"id": "a"}],
                "goals": {"max_turns": 2},
            }
        ),
        encoding="utf-8",
    )
    (src / "setting.md").write_text("hello", encoding="utf-8")
    app = create_app(runs_dir=tmp_path, scenarios_dir=scenarios_root)
    c = TestClient(app)
    r1 = c.get("/scenarios")
    assert r1.status_code == 200

    r2 = c.get("/scenarios/two-devs-and-a-pm")
    assert r2.status_code == 200

    r3 = c.post("/scenarios/two-devs-and-a-pm/copy_and_edit", follow_redirects=False)
    assert r3.status_code in (302, 303)
    loc = r3.headers.get("location", "")
    assert "/scenarios/two-devs-and-a-pm__copy-" in loc
    assert loc.endswith("/edit")
    old = c.post("/scenarios/two-devs-and-a-pm/fork", follow_redirects=False)
    assert old.status_code == 307
    assert old.headers.get("location", "").endswith("/scenarios/two-devs-and-a-pm/copy")
    metas = list_scenarios(scenarios_root)
    assert metas and metas[0].id == "two-devs-and-a-pm"


def _seed_min_scenario(scenarios_root: Path, slug: str = "two-devs-and-a-pm") -> Path:
    src = scenarios_root / slug
    src.mkdir(parents=True, exist_ok=True)
    (src / "scenario.yaml").write_text(
        yaml.safe_dump(
            {
                "id": slug,
                "name": "Two devs and a PM",
                "setting_file": "setting.md",
                "channels": [{"name": "#team"}],
                "characters": [{"id": "a"}],
                "goals": {"max_turns": 2},
            }
        ),
        encoding="utf-8",
    )
    (src / "setting.md").write_text("hello **world**", encoding="utf-8")
    return src


def test_scenario_edit_page_and_setting_save(tmp_path: Path) -> None:
    scenarios_root = tmp_path / "scenarios"
    _seed_min_scenario(scenarios_root)
    app = create_app(runs_dir=tmp_path, scenarios_dir=scenarios_root)
    c = TestClient(app)

    r = c.get("/scenarios/two-devs-and-a-pm/edit")
    assert r.status_code == 200
    assert "Setting" in r.text
    assert "hello **world**" in r.text
    assert "pre-run" in r.text

    p = c.post(
        "/scenarios/two-devs-and-a-pm/edit/setting",
        data={"content": "new markdown line", "preview": "0"},
    )
    assert p.status_code == 200
    assert "Saved" in p.text
    assert "new markdown line" in (scenarios_root / "two-devs-and-a-pm" / "setting.md").read_text(
        encoding="utf-8"
    )


def test_scenario_edit_page_shows_live_lock_chip(tmp_path: Path) -> None:
    scenarios_root = tmp_path / "scenarios"
    src = _seed_min_scenario(scenarios_root)

    class _Stub:
        def chat_text(self, model, messages, temperature=0.7, max_tokens=4096):
            return (
                '{"narrative":"n","channel_posts":[],"vital_self_report":{},"work_item_updates":[],"process_invocations":[]}',
                {"input_tokens": 1, "output_tokens": 1, "cost": 0.0},
            )

    sess = RunSession.start(
        scenario_dir=src,
        runs_dir=tmp_path,
        agent_model="stub",
        coach_model="stub",
        coach_mode_cli="human",
        coach_preset_cli=None,
        secrets=None,
        client=_Stub(),
        seed=None,
    )
    SESSIONS[sess.run_root.name] = sess
    try:
        app = create_app(runs_dir=tmp_path, scenarios_dir=scenarios_root)
        c = TestClient(app)
        r = c.get("/scenarios/two-devs-and-a-pm/edit")
        assert r.status_code == 200
        assert "live:" in r.text
    finally:
        SESSIONS.pop(sess.run_root.name, None)


def _seed_character_scenario(scenarios_root: Path) -> Path:
    src = scenarios_root / "character-lab"
    src.mkdir(parents=True, exist_ok=True)
    (src / "scenario.yaml").write_text(
        yaml.safe_dump(
            {
                "id": "character-lab",
                "name": "Character Lab",
                "setting_file": "setting.md",
                "channels": [{"name": "#team", "member_ids": ["priya"]}],
                "teams": [{"id": "core", "member_ids": ["priya"]}],
                "characters": [
                    {
                        "id": "priya",
                        "name": "Priya Shah",
                        "role": "Tech lead",
                        "markdown_file": "characters/priya.md",
                        "initial_vitals": {"energy": 70, "motivation": 75, "stress": 50},
                    }
                ],
                "work_items": [
                    {"id": "W1", "owner_id": "priya", "title": "t", "state": "backlog"},
                    {"id": "O1", "owner_id": "priya", "title": "outcome one", "state": "backlog"},
                    {"id": "O2", "owner_id": "priya", "title": "outcome two", "state": "backlog"},
                ],
                "goals": {"max_turns": 2},
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    (src / "setting.md").write_text("seed", encoding="utf-8")
    (src / "characters").mkdir(exist_ok=True)
    (src / "characters" / "priya.md").write_text("Priya backstory body", encoding="utf-8")
    (src / "process.yaml").write_text("rules:\n  - name: default\n", encoding="utf-8")
    (src / "best_practices.yaml").write_text("practices:\n  - id: bp1\n    name: test\n", encoding="utf-8")
    return src


def test_character_inspector_edit_and_backstory(tmp_path: Path) -> None:
    scenarios_root = tmp_path / "scenarios"
    _seed_character_scenario(scenarios_root)
    app = create_app(runs_dir=tmp_path, scenarios_dir=scenarios_root)
    c = TestClient(app)

    g = c.get("/partials/scenario/character-lab/inspector/character/priya")
    assert g.status_code == 200
    assert "Priya backstory body" in g.text

    p1 = c.post(
        "/scenarios/character-lab/edit/character/priya",
        data={
            "name": "Priya Prime",
            "role": "Lead Engineer",
            "sprite_set": "char_priya",
            "model": "stub/model",
            "energy": "66",
            "motivation": "64",
            "stress": "52",
        },
    )
    assert p1.status_code == 200
    scen_raw = yaml.safe_load((scenarios_root / "character-lab" / "scenario.yaml").read_text(encoding="utf-8"))
    priya = scen_raw["characters"][0]
    assert priya["name"] == "Priya Prime"
    assert priya["initial_vitals"]["energy"] == 66

    p2 = c.post(
        "/scenarios/character-lab/edit/character/priya/backstory",
        data={"content": "Updated backstory text", "preview": "0"},
    )
    assert p2.status_code == 200
    assert "Saved backstory" in p2.text
    assert (
        scenarios_root / "character-lab" / "characters" / "priya.md"
    ).read_text(encoding="utf-8") == "Updated backstory text"


def test_character_add_duplicate_and_delete_blockers(tmp_path: Path) -> None:
    scenarios_root = tmp_path / "scenarios"
    _seed_character_scenario(scenarios_root)
    app = create_app(runs_dir=tmp_path, scenarios_dir=scenarios_root)
    c = TestClient(app)

    add = c.post("/scenarios/character-lab/character/new", data={"id": "dana", "name": "Dana"})
    assert add.status_code == 200
    scen_raw = yaml.safe_load((scenarios_root / "character-lab" / "scenario.yaml").read_text(encoding="utf-8"))
    assert any(ch.get("id") == "dana" for ch in scen_raw.get("characters") or [])
    assert (scenarios_root / "character-lab" / "characters" / "dana.md").exists()

    dup = c.post("/scenarios/character-lab/character/new", data={"id": "dana", "name": "Dup Dana"})
    assert dup.status_code == 200
    assert "already exists" in dup.text

    blocked = c.post("/scenarios/character-lab/character/priya/delete")
    assert blocked.status_code == 200
    assert "owns work item W1" in blocked.text


def test_channel_team_work_item_validation(tmp_path: Path) -> None:
    scenarios_root = tmp_path / "scenarios"
    _seed_character_scenario(scenarios_root)
    app = create_app(runs_dir=tmp_path, scenarios_dir=scenarios_root)
    c = TestClient(app)

    bad_ce = c.post(
        "/scenarios/character-lab/edit/channel",
        data={"name": "#x", "type": "open", "coach_engagement": "bogus", "member_ids": ["priya"]},
    )
    assert bad_ce.status_code == 200
    assert "coach_engagement must be post, read, or none" in bad_ce.text

    bad_name = c.post(
        "/scenarios/character-lab/edit/channel",
        data={"name": "x", "type": "open", "coach_engagement": "post", "member_ids": ["priya"]},
    )
    assert bad_name.status_code == 200
    assert "must start with #" in bad_name.text

    bad_owner = c.post(
        "/scenarios/character-lab/edit/work_item",
        data={"id": "W2", "title": "new", "state": "backlog", "owner_id": "ghost"},
    )
    assert bad_owner.status_code == 200
    assert "unknown owner_id: ghost" in bad_owner.text


def test_goals_and_parameters_roundtrip(tmp_path: Path) -> None:
    scenarios_root = tmp_path / "scenarios"
    src = _seed_character_scenario(scenarios_root)
    app = create_app(runs_dir=tmp_path, scenarios_dir=scenarios_root)
    c = TestClient(app)

    g = c.post(
        "/scenarios/character-lab/edit/goals",
        data={
            "max_turns": "9",
            "max_stress_any": "82",
            "abort_stress_any": "96",
            "min_done_work_items": "2",
            "per_team_min_done": "",
            "require_done_ids": ["O1", "O2"],
        },
    )
    assert g.status_code == 200
    data = yaml.safe_load((src / "scenario.yaml").read_text(encoding="utf-8"))
    assert data["goals"]["require_done_ids"] == ["O1", "O2"]

    bundle_world = build_world_from_scenario(data, {"priya": "bio"})
    assert not goal_met(bundle_world)
    for wi in bundle_world.work_items:
        if wi.id in {"O1", "O2"}:
            wi.state = "done"
    for ch in bundle_world.characters.values():
        ch.vitals["stress"] = min(ch.vitals.get("stress", 0), 70)
    assert goal_met(bundle_world)

    p = c.post(
        "/scenarios/character-lab/edit/parameters",
        data={
            "param_keys": ["turn_pressure", "verbosity", "team_mode", "label"],
            "param_values": ["5", "0.75", "true", "pilot"],
        },
    )
    assert p.status_code == 200
    data2 = yaml.safe_load((src / "scenario.yaml").read_text(encoding="utf-8"))
    params = data2.get("parameters") or {}
    assert params["turn_pressure"] == 5
    assert params["verbosity"] == 0.75
    assert params["team_mode"] is True
    assert params["label"] == "pilot"


def test_yaml_editors_highlight_errors_and_save_valid(tmp_path: Path) -> None:
    scenarios_root = tmp_path / "scenarios"
    src = _seed_character_scenario(scenarios_root)
    app = create_app(runs_dir=tmp_path, scenarios_dir=scenarios_root)
    c = TestClient(app)

    bad = c.post(
        "/scenarios/character-lab/edit/process",
        data={"content": "rules:\n  - name: ok\n    bad: [\n"},
    )
    assert bad.status_code == 422
    assert "yaml-error-line" in bad.text
    assert "Line" in bad.text

    ok = c.post(
        "/scenarios/character-lab/edit/process",
        data={"content": "rules:\n  - name: tightened\n"},
    )
    assert ok.status_code == 200
    assert "Process YAML saved" in ok.text
    assert "tightened" in (src / "process.yaml").read_text(encoding="utf-8")

    ok_bp = c.post(
        "/scenarios/character-lab/edit/best_practices",
        data={"content": "practices:\n  - id: bp2\n    name: review blockers early\n"},
    )
    assert ok_bp.status_code == 200
    assert "Best-practices YAML saved" in ok_bp.text
    assert "bp2" in (src / "best_practices.yaml").read_text(encoding="utf-8")


def test_live_run_lock_semantics_and_timeline_edits(tmp_path: Path) -> None:
    scenarios_root = tmp_path / "scenarios"
    src = _seed_character_scenario(scenarios_root)

    class _Stub:
        def chat_text(self, model, messages, temperature=0.7, max_tokens=4096):
            return (
                '{"narrative":"n","channel_posts":[],"vital_self_report":{},"work_item_updates":[],"process_invocations":[]}',
                {"input_tokens": 1, "output_tokens": 1, "cost": 0.0},
            )

    sess = RunSession.start(
        scenario_dir=src,
        runs_dir=tmp_path,
        agent_model="stub",
        coach_model="stub",
        coach_mode_cli="human",
        coach_preset_cli=None,
        secrets=None,
        client=_Stub(),
        seed=None,
    )
    SESSIONS[sess.run_root.name] = sess
    try:
        app = create_app(runs_dir=tmp_path, scenarios_dir=scenarios_root)
        c = TestClient(app)

        old_backstory = (src / "characters" / "priya.md").read_text(encoding="utf-8")
        locked = c.post(
            "/scenarios/character-lab/edit/character/priya/backstory",
            data={"content": "should not apply"},
        )
        assert locked.status_code == 423
        assert "locked" in locked.text.lower()
        assert (src / "characters" / "priya.md").read_text(encoding="utf-8") == old_backstory

        ok_params = c.post(
            "/scenarios/character-lab/edit/parameters",
            data={"param_keys": ["budget_cap"], "param_values": ["9"]},
        )
        assert ok_params.status_code == 200
        rows = [json.loads(line) for line in (sess.run_root / "timeline.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
        edits = [r for r in rows if r.get("kind") == "coach_edit" and r.get("target") == "parameters"]
        assert edits
        assert edits[-1]["effective_turn"] == sess.world.turn + 1

        ok_model = c.post(
            "/scenarios/character-lab/edit/character/priya",
            data={"name": "Priya Shah", "role": "Tech lead", "sprite_set": "char_priya", "model": "openrouter/new"},
        )
        assert ok_model.status_code == 200
        scen = yaml.safe_load((src / "scenario.yaml").read_text(encoding="utf-8"))
        assert scen["characters"][0]["model"] == "openrouter/new"

        bad_name = c.post(
            "/scenarios/character-lab/edit/character/priya",
            data={"name": "Renamed", "role": "Tech lead", "sprite_set": "char_priya", "model": "openrouter/new"},
        )
        assert bad_name.status_code == 423
        scen2 = yaml.safe_load((src / "scenario.yaml").read_text(encoding="utf-8"))
        assert scen2["characters"][0]["name"] != "Renamed"
    finally:
        SESSIONS.pop(sess.run_root.name, None)
