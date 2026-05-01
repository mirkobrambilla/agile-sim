"""Run reader loads messages and summaries."""

from __future__ import annotations

import json
import os
import time
from pathlib import Path

import yaml

from harness.web.run_reader import build_picker_entries, load_run


def test_build_picker_entries_includes_batch_and_run(tmp_path: Path) -> None:
    scen = tmp_path / "scen"
    scen.mkdir()
    (scen / "scenario.yaml").write_text(
        yaml.safe_dump({"id": "s1", "name": "Scenario One"}), encoding="utf-8"
    )
    batch = tmp_path / "batch_z"
    batch.mkdir()
    (batch / "manifest.json").write_text(
        json.dumps({"scenario_dir": str(scen), "runs": [{"path": "a", "ok": True}]}),
        encoding="utf-8",
    )
    run = tmp_path / "run_y"
    run.mkdir()
    (run / "summary.json").write_text("{}", encoding="utf-8")
    (run / "meta.yaml").write_text(
        yaml.safe_dump({"scenario_path": str(scen)}), encoding="utf-8"
    )
    t_old = time.time() - 100
    os.utime(run, (t_old, t_old))

    entries = build_picker_entries(tmp_path)
    kinds = [e["kind"] for e in entries]
    assert "batch" in kinds
    assert "run" in kinds
    batch_row = next(e for e in entries if e["kind"] == "batch")
    assert "Scenario One" in batch_row["scenario"]
    assert batch_row["href"].startswith("/experiments/")


def test_load_run_minimal(tmp_path: Path) -> None:
    scen = tmp_path / "scenario.yaml"
    scen.write_text(
        yaml.safe_dump(
            {
                "id": "sr",
                "channels": [{"name": "#team"}],
                "characters": [{"id": "alice"}],
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    run = tmp_path / "run1"
    run.mkdir()
    (run / "meta.yaml").write_text(
        yaml.safe_dump({"scenario_path": str(scen)}, sort_keys=False),
        encoding="utf-8",
    )
    (run / "summary.json").write_text(
        json.dumps({"final_turn": 2, "goal_met": False, "totals": {"cost": 0.03}}),
        encoding="utf-8",
    )
    (run / "messages.jsonl").write_text(
        json.dumps(
            {
                "id": "1",
                "turn": 1,
                "author": "alice",
                "channel": "#team",
                "content": "hi",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    bundle = load_run(run_dir=run, url_path="run1")
    assert bundle.primary_channel == "#team"
    assert "#team" in bundle.messages_by_channel
    assert len(bundle.messages_by_channel["#team"]) == 1
