from __future__ import annotations

import json
from pathlib import Path

from starlette.testclient import TestClient

from harness.scenario import load_scenario
from harness.web.app import create_app
from harness.web.run_session import SESSIONS, RunSession


class StubClient:
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


def test_sse_open_and_cancel(tmp_path: Path) -> None:
    repo = Path(__file__).resolve().parents[1]
    bundle = load_scenario(repo / "scenarios" / "two-devs-and-a-pm")
    sess = RunSession.start(
        scenario_dir=bundle.path,
        runs_dir=tmp_path,
        agent_model="stub",
        coach_model="stub",
        coach_mode_cli="llm",
        coach_preset_cli=None,
        secrets=None,
        client=StubClient(),
        seed=None,
    )
    key = sess.run_root.name
    SESSIONS[key] = sess
    app = create_app(runs_dir=tmp_path)
    c = TestClient(app)

    res = c.post(f"/runs/{key}/cancel")
    assert res.status_code == 200
    sess.events.put_nowait({"kind": "advance_cancelled", "turn": 1})
    with c.stream("GET", f"/runs/{key}/events") as stream:
        text = "".join(stream.iter_text())
        assert "advance_cancelled" in text
    SESSIONS.pop(key, None)
