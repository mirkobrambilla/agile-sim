"""Runner integration test with stub LLM client."""

import json
from pathlib import Path

from harness.runner import run_once
from harness.scenario import load_scenario

REPO = Path(__file__).resolve().parents[1]


class StubClient:
    def __init__(self, responses: list[str]) -> None:
        self._responses = list(responses)
        self._i = 0

    def chat_text(self, model, messages, temperature=0.7, max_tokens=4096):
        if self._i >= len(self._responses):
            raise RuntimeError("StubClient: no more scripted responses")
        r = self._responses[self._i]
        self._i += 1
        return r, {"input_tokens": 3, "output_tokens": 2, "cost": 0.0}


def _agent_json(cid: str) -> str:
    return json.dumps(
        {
            "narrative": f"{cid} ships value",
            "channel_posts": [
                {
                    "channel": "#team",
                    "content": f"Update from {cid}",
                    "parent_id": None,
                }
            ],
            "vital_self_report": {"stress": -1},
            "work_item_updates": [],
            "process_invocations": [],
        }
    )


def _coach_json() -> str:
    return json.dumps(
        {
            "narrative": "observe",
            "channel_posts": [],
            "vital_nudges": [],
            "process_invocations": [],
        }
    )


def test_run_once_writes_artifacts(tmp_path):
    bundle = load_scenario(REPO / "scenarios" / "two-devs-and-a-pm")
    bundle.scenario["goals"]["max_turns"] = 2
    seq: list[str] = []
    for _ in range(2):
        for cid in ["priya", "marcus", "lin"]:
            seq.append(_agent_json(cid))
        seq.append(_coach_json())

    stub = StubClient(seq)
    run_root = tmp_path / "run1"
    run_root.mkdir()

    summary = run_once(
        bundle,
        stub,
        agent_model="stub",
        coach_model="stub",
        run_root=run_root,
        seed=42,
    )

    assert (run_root / "timeline.jsonl").exists()
    assert (run_root / "summary.json").exists()
    assert stub._i == len(seq)
    assert "totals" in summary
    assert summary["totals"]["input_tokens"] > 0
