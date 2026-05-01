"""Batch / experiments views."""

from __future__ import annotations

import json
from pathlib import Path

import yaml
from starlette.testclient import TestClient

from harness.web.app import create_app


def test_experiments_batch_page(tmp_path: Path) -> None:
    batch = tmp_path / "batch_1"
    batch.mkdir()
    r1 = batch / "sub_0"
    r1.mkdir()
    (r1 / "meta.yaml").write_text(
        yaml.safe_dump({"variant_name": "vA", "models": {"agent": "m", "coach": "m"}}),
        encoding="utf-8",
    )
    (r1 / "summary.json").write_text(
        json.dumps({"goal_met": True, "work_done": 1, "totals": {"cost": 0.01}}),
        encoding="utf-8",
    )
    (batch / "manifest.json").write_text(
        json.dumps({"runs": [{"path": "sub_0", "ok": True}]}), encoding="utf-8"
    )
    app = create_app(runs_dir=tmp_path)
    c = TestClient(app)
    r = c.get("/experiments/batch_1")
    assert r.status_code == 200
    assert "batch_1" in r.text
    r2 = c.get("/runs/batch_1/sub_0")
    assert r2.status_code == 200
