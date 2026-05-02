from __future__ import annotations

from pathlib import Path

import yaml
from starlette.testclient import TestClient

from harness.scenario import list_scenarios
from harness.web.app import create_app


def test_scenarios_list_view_and_fork(tmp_path: Path) -> None:
    scenarios_root = tmp_path / "scenarios"
    src = scenarios_root / "two-devs-and-a-pm"
    src.mkdir(parents=True, exist_ok=True)
    (src / "scenario.yaml").write_text(
        yaml.safe_dump(
            {
                "id": "two-devs-and-a-pm",
                "name": "Two devs and a PM",
                "channels": [{"name": "#team"}],
                "characters": [{"id": "a"}],
                "goals": {"max_turns": 2},
            }
        ),
        encoding="utf-8",
    )
    (src / "setting.md").write_text("hello", encoding="utf-8")
    app = create_app(runs_dir=tmp_path, scenarios_dir=scenarios_root)
    c = TestClient(app)
    r1 = c.get("/scenarios")
    assert r1.status_code == 200

    r2 = c.get("/scenarios/two-devs-and-a-pm")
    assert r2.status_code == 200

    r3 = c.post("/scenarios/two-devs-and-a-pm/fork", follow_redirects=False)
    assert r3.status_code in (302, 303)
    loc = r3.headers.get("location", "")
    assert "/scenarios/two-devs-and-a-pm__fork-" in loc
    metas = list_scenarios(scenarios_root)
    assert metas and metas[0].id == "two-devs-and-a-pm"
