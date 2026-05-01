"""Batch analysis smoke test."""

import json
from pathlib import Path

import yaml

from harness.analyse import analyse_batch, batch_metrics, write_results_json


def test_analyse_writes_report(tmp_path):
    batch = tmp_path / "batch_test"
    batch.mkdir()
    for name, var, goal in [("r1", "v1", True), ("r2", "v1", False)]:
        d = batch / name
        d.mkdir()
        (d / "meta.yaml").write_text(
            yaml.safe_dump(
                {"variant_name": var, "models": {"agent": "stub", "coach": "stub"}},
                sort_keys=False,
            ),
            encoding="utf-8",
        )
        (d / "summary.json").write_text(
            json.dumps(
                {
                    "goal_met": goal,
                    "work_done": 4 if goal else 1,
                    "totals": {"cost": 0.01, "input_tokens": 100, "output_tokens": 50},
                }
            ),
            encoding="utf-8",
        )
    (batch / "manifest.json").write_text(
        json.dumps({"runs": [{"path": "r1", "ok": True}, {"path": "r2", "ok": True}]}),
        encoding="utf-8",
    )
    report = analyse_batch(batch)
    assert report.exists()
    body = report.read_text(encoding="utf-8")
    assert "v1" in body
    assert "Goal rate" in body

    metrics = batch_metrics(batch)
    assert metrics["n_runs_with_summary"] == 2
    assert len(metrics["variants"]) == 1
    assert metrics["variants"][0]["name"] == "v1"
    assert metrics["variants"][0]["goal_rate"] == 0.5

    rj = write_results_json(batch)
    assert rj.exists()
    data = json.loads(rj.read_text(encoding="utf-8"))
    assert data["variants"][0]["goals_met"] == 1


def test_analyse_single_run_folder(tmp_path):
    run_dir = tmp_path / "run_abc"
    run_dir.mkdir()
    (run_dir / "meta.yaml").write_text(
        yaml.safe_dump(
            {"scenario_id": "s1", "models": {"agent": "m1", "coach": "m1"}},
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    (run_dir / "summary.json").write_text(
        json.dumps(
            {
                "run_id": "run_abc",
                "goal_met": True,
                "final_turn": 2,
                "work_done": 4,
                "aborted_stress": False,
                "final_vitals": {"a": {"stress": 10}},
                "org": {"happiness": 80},
                "totals": {"cost": 0.02, "input_tokens": 200, "output_tokens": 50},
            }
        ),
        encoding="utf-8",
    )
    snap = {
        "turn": 1,
        "world": {
            "characters": {
                "a": {"vitals": {"energy": 50, "motivation": 50, "stress": 40}},
            },
            "work_items": [{"state": "done"}, {"state": "doing"}],
            "org": {"delivery_progress": 50},
            "messages": [],
        },
    }
    (run_dir / "snapshots.jsonl").write_text(json.dumps(snap) + "\n", encoding="utf-8")
    (run_dir / "llm_calls.jsonl").write_text(
        json.dumps(
            {
                "turn": 1,
                "role": "agent",
                "character": "a",
                "model": "m",
                "usage": {"input_tokens": 10, "output_tokens": 5, "cost": 0.001},
                "latency_ms": 100,
            }
        )
        + "\n",
        encoding="utf-8",
    )
    report = analyse_batch(run_dir)
    body = report.read_text(encoding="utf-8")
    assert "Run analysis" in body
    assert "Vitals and work" in body
    assert "LLM calls" in body
    assert "**Goal met:**" in body

