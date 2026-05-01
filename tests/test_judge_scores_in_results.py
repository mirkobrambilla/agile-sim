"""Judge scores merged into results.json via batch_metrics."""

from __future__ import annotations

import json
from pathlib import Path

import yaml

from harness.analyse import write_results_json


def test_write_results_json_includes_judge_scores(tmp_path: Path) -> None:
    batch = tmp_path / "batch_judge"
    batch.mkdir()
    r1 = batch / "run_a"
    r1.mkdir()
    (r1 / "meta.yaml").write_text(
        yaml.safe_dump({"variant_name": "v1", "models": {"agent": "m", "coach": "m"}}, sort_keys=False),
        encoding="utf-8",
    )
    (r1 / "summary.json").write_text(
        json.dumps({"goal_met": True, "work_done": 2, "totals": {"cost": 0.01}}),
        encoding="utf-8",
    )
    (batch / "manifest.json").write_text(
        json.dumps({"runs": [{"path": "run_a", "ok": True}]}),
        encoding="utf-8",
    )
    (batch / "judge_report.md").write_text(
        "# Judge report (`stub`)\n\n"
        "## Run `run_a`\n\n"
        "## Score\n"
        "4.5\n"
        "## Strengths\nok\n",
        encoding="utf-8",
    )
    write_results_json(batch)
    data = json.loads((batch / "results.json").read_text(encoding="utf-8"))
    assert data["mean_judge_score"] == 4.5
    assert data["variants"][0]["runs"][0]["judge_score"] == 4.5
    assert data["variants"][0]["mean_judge_score"] == 4.5
