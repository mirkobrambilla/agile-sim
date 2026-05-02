from __future__ import annotations

import json
from pathlib import Path

import yaml
from starlette.testclient import TestClient

from harness.web.app import create_app


def test_summary_baseline_render(tmp_path: Path) -> None:
    scen = tmp_path / "scenario.yaml"
    scen.write_text(
        yaml.safe_dump({"id": "x", "channels": [{"name": "#team"}], "characters": [{"id": "a"}]}),
        encoding="utf-8",
    )
    run = tmp_path / "run_summ"
    run.mkdir()
    (run / "meta.yaml").write_text(yaml.safe_dump({"scenario_path": str(scen)}), encoding="utf-8")
    (run / "summary.json").write_text(
        json.dumps({"goal_met": True, "final_turn": 1, "work_done": 0, "aborted_stress": False}),
        encoding="utf-8",
    )
    (run / "messages.jsonl").write_text("", encoding="utf-8")
    (run / "snapshots.jsonl").write_text("", encoding="utf-8")
    (run / "timeline.jsonl").write_text("", encoding="utf-8")

    app = create_app(runs_dir=tmp_path)
    c = TestClient(app)
    r = c.get("/partials/run/run_summ/summary")
    assert r.status_code == 200
    assert "Outcome:" in r.text
    assert "Character arcs" in r.text
