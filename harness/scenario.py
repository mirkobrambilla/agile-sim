"""Load scenario folders (YAML + markdown) into a bundle object."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


@dataclass
class ScenarioBundle:
    """Resolved scenario content for the harness."""

    path: Path
    scenario: dict[str, Any]
    setting_text: str
    character_bodies: dict[str, str] = field(default_factory=dict)
    best_practices: list[dict[str, Any]] = field(default_factory=list)
    process: dict[str, Any] = field(default_factory=dict)


@dataclass
class ScenarioMeta:
    slug: str
    id: str
    name: str
    description: str
    path: Path
    characters_count: int
    channels_count: int
    cover_url: str | None = None


def list_scenarios(root: Path | str) -> list[ScenarioMeta]:
    base = Path(root).resolve()
    if not base.is_dir():
        return []
    out: list[ScenarioMeta] = []
    for p in sorted(base.iterdir()):
        if not p.is_dir():
            continue
        y = p / "scenario.yaml"
        if not y.is_file():
            continue
        raw = yaml.safe_load(y.read_text(encoding="utf-8")) or {}
        sid = str(raw.get("id") or p.name).strip()
        name = str(raw.get("name") or sid or p.name).strip()
        desc = str(raw.get("description") or "").strip()
        cover_name = f"{sid}.png"
        cover_url = f"/static/covers/{cover_name}" if cover_name else None
        out.append(
            ScenarioMeta(
                slug=p.name,
                id=sid,
                name=name,
                description=desc,
                path=p,
                characters_count=len(raw.get("characters") or []),
                channels_count=len(raw.get("channels") or []),
                cover_url=cover_url,
            )
        )
    return out


def load_scenario(scenario_dir: Path | str) -> ScenarioBundle:
    root = Path(scenario_dir).resolve()
    if not root.is_dir():
        raise FileNotFoundError(f"Not a directory: {root}")

    main = root / "scenario.yaml"
    if not main.exists():
        raise FileNotFoundError(f"Missing {main}")

    scenario = yaml.safe_load(main.read_text(encoding="utf-8")) or {}

    setting_rel = scenario.get("setting_file", "setting.md")
    setting_path = root / setting_rel
    setting_text = setting_path.read_text(encoding="utf-8") if setting_path.exists() else ""

    bodies: dict[str, str] = {}
    for ch in scenario.get("characters") or []:
        cid = str(ch["id"])
        rel = ch.get("markdown_file") or f"characters/{cid}.md"
        p = root / rel
        bodies[cid] = p.read_text(encoding="utf-8") if p.exists() else ""

    bp: list[dict[str, Any]] = []
    bp_rel = scenario.get("best_practices_file", "best_practices.yaml")
    bp_path = root / bp_rel
    if bp_path.exists():
        raw = yaml.safe_load(bp_path.read_text(encoding="utf-8")) or {}
        bp = list(raw.get("practices") or [])

    process_path = root / "process.yaml"
    process: dict[str, Any] = {}
    if process_path.exists():
        process = yaml.safe_load(process_path.read_text(encoding="utf-8")) or {}

    return ScenarioBundle(
        path=root,
        scenario=scenario,
        setting_text=setting_text,
        character_bodies=bodies,
        best_practices=bp,
        process=process,
    )
