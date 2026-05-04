"""FastAPI route smoke tests."""

from __future__ import annotations

import json
from pathlib import Path

import yaml
from starlette.testclient import TestClient

from harness.scenario import load_scenario
from harness.web.app import create_app
from harness.web.run_session import SESSIONS, RunSession


def _seed_run(tmp_path: Path) -> None:
    scen = tmp_path / "scenario.yaml"
    scen.write_text(
        yaml.safe_dump(
            {
                "id": "x",
                "channels": [{"name": "#team"}],
                "characters": [{"id": "a", "sprite_set": "char_a"}],
            }
        ),
        encoding="utf-8",
    )
    run = tmp_path / "run_web"
    run.mkdir()
    (run / "meta.yaml").write_text(
        yaml.safe_dump({"scenario_path": str(scen)}, sort_keys=False), encoding="utf-8"
    )
    (run / "summary.json").write_text(
        json.dumps({"final_turn": 1, "goal_met": True, "totals": {"cost": 0.0}}),
        encoding="utf-8",
    )
    (run / "messages.jsonl").write_text(
        json.dumps(
            {"id": "1", "turn": 1, "author": "a", "channel": "#team", "content": "m"}
        )
        + "\n",
        encoding="utf-8",
    )
    (run / "snapshots.jsonl").write_text(
        json.dumps({"turn": 1, "world": {"characters": {}, "work_items": []}}) + "\n",
        encoding="utf-8",
    )
    (run / "timeline.jsonl").write_text("", encoding="utf-8")


def test_runner_and_partials(tmp_path: Path) -> None:
    _seed_run(tmp_path)
    app = create_app(runs_dir=tmp_path)
    c = TestClient(app)
    r = c.get("/runs/run_web")
    assert r.status_code == 200
    assert "run_web" in r.text
    p = c.get("/partials/run/run_web/kanban?turn=1")
    assert p.status_code == 200
    assert c.get("/partials/run/run_web/roster?turn=1").status_code == 200
    assert c.get("/partials/run/run_web/inspector/character/a?turn=1").status_code == 200
    assert c.get("/partials/run/run_web/inspector/work_item/w1?turn=1").status_code == 200
    assert c.get("/partials/run/run_web/inspector/channel?channel=%23team&turn=1").status_code == 200
    t = c.get("/partials/run/run_web/timeline?turn=1")
    assert t.status_code == 200
    assert "T1" in t.text or "turn" in t.text


def test_batch_run_path_redirects_to_experiments(tmp_path: Path) -> None:
    batch = tmp_path / "batch_x"
    batch.mkdir()
    (batch / "manifest.json").write_text(json.dumps({"runs": []}), encoding="utf-8")
    app = create_app(runs_dir=tmp_path)
    c = TestClient(app, follow_redirects=False)
    r = c.get("/runs/batch_x", follow_redirects=False)
    assert r.status_code in (301, 302, 303, 307, 308)
    assert r.headers.get("location", "").endswith("/experiments/batch_x")


def test_ambiguous_top_level_prefix_returns_helpful_json(tmp_path: Path) -> None:
    for name in ("batch_20260501T155006Z", "batch_20260501T155040Z"):
        d = tmp_path / name
        d.mkdir()
        (d / "manifest.json").write_text(json.dumps({"runs": []}), encoding="utf-8")
    app = create_app(runs_dir=tmp_path)
    c = TestClient(app)
    r = c.get("/runs/batch_20260501T1550")
    assert r.status_code == 404
    body = r.json()
    assert "detail" in body
    assert "155006Z" in body["detail"] or "155040Z" in body["detail"]


def test_home_landing_and_runs_picker(tmp_path: Path) -> None:
    _seed_run(tmp_path)
    app = create_app(runs_dir=tmp_path)
    c = TestClient(app)
    home = c.get("/")
    assert home.status_code == 200
    assert "This landing page is a placeholder" in home.text
    runs = c.get("/runs")
    assert runs.status_code == 200
    assert "run_web" in runs.text


def test_channel_renders_mention_links(tmp_path: Path) -> None:
    _seed_run(tmp_path)
    run = tmp_path / "run_web"
    (run / "messages.jsonl").write_text(
        "\n".join(
            [
                json.dumps({"id": "1", "turn": 1, "author": "a", "channel": "#team", "content": "ping @a please"}),
                json.dumps({"id": "2", "turn": 1, "author": "a", "channel": "#team", "content": "no link @ghost"}),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    app = create_app(runs_dir=tmp_path)
    c = TestClient(app)
    r = c.get("/partials/run/run_web/channel?channel=%23team&turn=1")
    assert r.status_code == 200
    assert 'class="msg-mention"' in r.text
    assert "dm/a" in r.text
    assert "@ghost" in r.text
    assert ">@ghost</a>" not in r.text


def test_channel_uses_character_sprite_set(tmp_path: Path, monkeypatch) -> None:
    _seed_run(tmp_path)
    sprite = tmp_path / "harness" / "web" / "static" / "sprites" / "char_a" / "idle.png"
    sprite.parent.mkdir(parents=True, exist_ok=True)
    sprite.write_bytes(b"\x89PNG\r\n\x1a\n")
    monkeypatch.setattr("harness.web.sprites.repo_root", lambda: tmp_path)

    app = create_app(runs_dir=tmp_path)
    c = TestClient(app)
    r = c.get("/partials/run/run_web/channel?channel=%23team&turn=1")
    assert r.status_code == 200
    assert "/static/sprites/char_a/idle.png" in r.text


def test_scenarios_routes(tmp_path: Path) -> None:
    repo = Path(__file__).resolve().parents[1]
    app = create_app(runs_dir=tmp_path)
    c = TestClient(app)
    idx = c.get("/scenarios")
    assert idx.status_code == 200
    assert "Scenarios" in idx.text
    one = c.get("/scenarios/two-devs-and-a-pm")
    assert one.status_code == 200
    assert "make a copy" in one.text.lower()


def test_live_edit_and_reflection_endpoints(tmp_path: Path) -> None:
    repo = Path(__file__).resolve().parents[1]
    bundle = load_scenario(repo / "scenarios" / "two-devs-and-a-pm")

    class _Stub:
        def chat_text(self, model, messages, temperature=0.7, max_tokens=4096):
            return (
                json.dumps(
                    {
                        "narrative": "n",
                        "channel_posts": [],
                        "vital_self_report": {},
                        "work_item_updates": [],
                        "process_invocations": [],
                    }
                ),
                {"input_tokens": 1, "output_tokens": 1, "cost": 0.0},
            )

    sess = RunSession.start(
        scenario_dir=bundle.path,
        runs_dir=tmp_path,
        agent_model="stub",
        coach_model="stub",
        coach_mode_cli="human",
        coach_preset_cli=None,
        secrets=None,
        client=_Stub(),
        seed=None,
    )
    key = sess.run_root.name
    SESSIONS[key] = sess
    app = create_app(runs_dir=tmp_path)
    c = TestClient(app)
    rv = c.post(
        f"/runs/{key}/edit/vital",
        data={"character_id": "priya", "vital_name": "energy", "delta": 2},
    )
    assert rv.status_code == 200
    rp = c.post(f"/runs/{key}/edit/parameter", data={"key": "x", "value": "y"})
    assert rp.status_code == 200
    rr = c.post(f"/runs/{key}/reflection", data={"content": "memo"})
    assert rr.status_code == 200
    SESSIONS.pop(key, None)
