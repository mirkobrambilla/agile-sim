from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest
from starlette.testclient import TestClient

from harness.scenario import load_scenario
from harness.web.app import create_app
from harness.web.run_session import RunSession

REPO = Path(__file__).resolve().parents[1]
SCENARIOS_ROOT = REPO / "scenarios"


class StubClient:
    def __init__(self, responses: list[str]) -> None:
        self._responses = list(responses)
        self._i = 0

    def chat_text(self, model, messages, temperature=0.7, max_tokens=4096):
        if self._i >= len(self._responses):
            raise RuntimeError("no more responses")
        r = self._responses[self._i]
        self._i += 1
        return r, {"input_tokens": 1, "output_tokens": 1, "cost": 0.0}


def _agent(cid: str, channel: str) -> str:
    return json.dumps(
        {
            "narrative": f"smoke-{cid}",
            "channel_posts": [{"channel": channel, "content": f"smoke-{cid}", "parent_id": None}],
            "vital_self_report": {},
            "work_item_updates": [],
            "process_invocations": [],
        }
    )


def _coach() -> str:
    return json.dumps(
        {"narrative": "coach", "channel_posts": [], "vital_nudges": [], "process_invocations": []}
    )


def _scenario_dirs() -> list[Path]:
    out: list[Path] = []
    for p in sorted(SCENARIOS_ROOT.iterdir()):
        if p.is_dir() and (p / "scenario.yaml").is_file():
            out.append(p)
    return out


@pytest.mark.parametrize("scenario_dir", _scenario_dirs())
def test_scenario_one_turn_smoke(tmp_path: Path, scenario_dir: Path) -> None:
    bundle = load_scenario(scenario_dir)
    order = [str(c.get("id", "")) for c in (bundle.scenario.get("characters") or []) if c.get("id")]
    if not order:
        pytest.skip(f"known issue: no characters in {scenario_dir.name}")

    seq: list[str] = []
    primary_channel = str(((bundle.scenario.get("channels") or [{}])[0]).get("name") or "#team")
    for cid in order:
        seq.append(_agent(cid, primary_channel))
    seq.append(_coach())

    sess = RunSession.start(
        scenario_dir=bundle.path,
        runs_dir=tmp_path,
        agent_model="stub",
        coach_model="stub",
        coach_mode_cli="llm",
        coach_preset_cli=None,
        secrets=None,
        client=StubClient(seq),
        seed=None,
    )
    asyncio.run(sess.advance())

    for name in ("messages.jsonl", "snapshots.jsonl", "timeline.jsonl", "summary.json"):
        p = sess.run_root / name
        assert p.is_file(), f"missing {name} for {scenario_dir.name}"
        assert p.stat().st_size > 0, f"empty {name} for {scenario_dir.name}"

    app = create_app(runs_dir=tmp_path)
    c = TestClient(app)
    r = c.get(f"/runs/{sess.run_root.name}")
    assert r.status_code == 200
