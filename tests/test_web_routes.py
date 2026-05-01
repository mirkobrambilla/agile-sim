"""FastAPI route smoke tests."""

from __future__ import annotations

import json
from pathlib import Path

import yaml
from starlette.testclient import TestClient

from harness.web.app import create_app


def _seed_run(tmp_path: Path) -> None:
    scen = tmp_path / "scenario.yaml"
    scen.write_text(
        yaml.safe_dump({"id": "x", "channels": [{"name": "#team"}], "characters": [{"id": "a"}]}),
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


def test_picker_home(tmp_path: Path) -> None:
    _seed_run(tmp_path)
    app = create_app(runs_dir=tmp_path)
    c = TestClient(app)
    r = c.get("/")
    assert r.status_code == 200
    assert "run_web" in r.text
