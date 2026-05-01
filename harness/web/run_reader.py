"""Load finished run directories into structures for the web UI."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, Field

from harness.analyse import load_meta, load_summary
from harness.world import primary_team_channel


class UiMessage(BaseModel):
    id: str
    turn: int
    author: str
    channel: str
    content: str


class UiChannel(BaseModel):
    id: str
    label: str


class UiSnapshot(BaseModel):
    turn: int
    world: dict[str, Any] = Field(default_factory=dict)


class UiTimelineRow(BaseModel):
    kind: str
    raw: dict[str, Any] = Field(default_factory=dict)


class RunBundle(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    run_dir: Path
    url_path: str
    meta: dict[str, Any] = Field(default_factory=dict)
    summary: dict[str, Any] = Field(default_factory=dict)
    primary_channel: str = "#team"
    channels: list[UiChannel] = Field(default_factory=list)
    messages_by_channel: dict[str, list[UiMessage]] = Field(default_factory=dict)
    snapshots: list[UiSnapshot] = Field(default_factory=list)
    timeline: list[UiTimelineRow] = Field(default_factory=list)
    report_html: str | None = None
    comparison_html: str | None = None
    judge_html: str | None = None


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return rows


def _scenario_dict_from_meta(meta: dict[str, Any]) -> dict[str, Any]:
    sp = meta.get("scenario_path")
    if not sp:
        return {}
    p = Path(str(sp))
    if p.is_dir():
        p = p / "scenario.yaml"
    if not p.exists():
        return {}
    return yaml.safe_load(p.read_text(encoding="utf-8")) or {}


def _fmt_utc_mtime(mtime: float) -> str:
    return datetime.fromtimestamp(mtime, tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def scenario_display_from_dir(scenario_dir: str | Path | None) -> str:
    if not scenario_dir:
        return ""
    root = Path(str(scenario_dir))
    y = root / "scenario.yaml"
    if not y.exists():
        return root.name
    try:
        data = yaml.safe_load(y.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError):
        return root.name
    name = str(data.get("name") or "").strip()
    sid = str(data.get("id") or "").strip()
    if name and sid:
        return f"{name} ({sid})"
    return name or sid or root.name


def meta_scenario_display(meta: dict[str, Any]) -> str:
    scen = _scenario_dict_from_meta(meta)
    if scen.get("name") or scen.get("id"):
        name = str(scen.get("name") or "").strip()
        sid = str(scen.get("id") or "").strip()
        if name and sid:
            return f"{name} ({sid})"
        return name or sid
    return str(meta.get("scenario_id") or "").strip()


def build_picker_entries(
    runs_dir: Path,
    *,
    limit_batches: int = 100,
    limit_runs: int = 200,
) -> list[dict[str, Any]]:
    """Flat list of batches + single runs for the home picker, newest first."""

    runs_dir = runs_dir.resolve()
    entries: list[tuple[float, dict[str, Any]]] = []

    for path, name in list_batches(runs_dir, limit=limit_batches):
        mtime = path.stat().st_mtime
        try:
            man = json.loads((path / "manifest.json").read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            man = {}
        scen = scenario_display_from_dir(man.get("scenario_dir"))
        mf = man.get("matrix_file")
        matrix_name = Path(str(mf)).name if mf else ""
        n_ok = sum(1 for r in man.get("runs") or [] if r.get("path") and r.get("ok", True))
        sub = f"{n_ok} run{'s' if n_ok != 1 else ''}"
        if matrix_name:
            sub = f"{sub} · {matrix_name}"
        entries.append(
            (
                mtime,
                {
                    "kind": "batch",
                    "kind_label": "Experiment batch",
                    "title": name,
                    "href": f"/experiments/{name}",
                    "scenario": scen or "—",
                    "sub": sub,
                    "date": _fmt_utc_mtime(mtime),
                },
            )
        )

    for path, rel in list_runs(runs_dir, limit=limit_runs):
        meta = load_meta(path)
        mtime = path.stat().st_mtime
        summ = load_summary(path) or {}
        goal = summ.get("goal_met")
        sub = "Single run"
        if goal is not None:
            sub = f"{sub} · goal_met={goal}"
        entries.append(
            (
                mtime,
                {
                    "kind": "run",
                    "kind_label": "Single run",
                    "title": rel,
                    "href": f"/runs/{rel}",
                    "scenario": meta_scenario_display(meta) or "—",
                    "sub": sub,
                    "date": _fmt_utc_mtime(mtime),
                },
            )
        )

    entries.sort(key=lambda x: x[0], reverse=True)
    return [e[1] for e in entries]


def load_run(*, run_dir: Path, url_path: str, repo_root: Path | None = None) -> RunBundle:
    run_dir = run_dir.resolve()
    meta = load_meta(run_dir)
    summ = load_summary(run_dir) or {}
    scenario = _scenario_dict_from_meta(meta)
    primary = primary_team_channel(scenario) if scenario else "#team"

    msgs_raw = _load_jsonl(run_dir / "messages.jsonl")
    messages: list[UiMessage] = []
    seen_channels: set[str] = {primary}
    for r in msgs_raw:
        messages.append(
            UiMessage(
                id=str(r.get("id", "")),
                turn=int(r.get("turn", 0)),
                author=str(r.get("author", "")),
                channel=str(r.get("channel", primary)),
                content=str(r.get("content", "")),
            )
        )
        seen_channels.add(messages[-1].channel)

    for ch in scenario.get("channels") or []:
        name = str(ch.get("name", "")).strip()
        if name.startswith("#"):
            seen_channels.add(name)

    for cid in (scenario.get("characters") or []):
        cid_str = str(cid.get("id", ""))
        if cid_str:
            seen_channels.add(f"dm/{cid_str}")

    by_ch: dict[str, list[UiMessage]] = {c: [] for c in sorted(seen_channels)}
    for m in messages:
        if m.channel not in by_ch:
            by_ch[m.channel] = []
        by_ch[m.channel].append(m)

    channels = [UiChannel(id=c, label=c) for c in sorted(by_ch.keys())]

    snaps_raw = _load_jsonl(run_dir / "snapshots.jsonl")
    snapshots = [
        UiSnapshot(turn=int(r.get("turn", 0)), world=dict(r.get("world") or {}))
        for r in snaps_raw
    ]

    tl_raw = _load_jsonl(run_dir / "timeline.jsonl")
    timeline = [UiTimelineRow(kind=str(r.get("kind", "")), raw=r) for r in tl_raw]

    from harness.web.render import md_to_html

    report_html = None
    rp = run_dir / "report.md"
    if rp.exists():
        report_html = md_to_html(rp.read_text(encoding="utf-8"))
    cmp_html = None
    cp = run_dir / "comparison.md"
    if cp.exists():
        cmp_html = md_to_html(cp.read_text(encoding="utf-8"))
    j_html = None
    jp = run_dir / "judge_report.md"
    if jp.exists():
        j_html = md_to_html(jp.read_text(encoding="utf-8"))

    return RunBundle(
        run_dir=run_dir,
        url_path=url_path,
        meta=meta,
        summary=summ,
        primary_channel=primary,
        channels=channels,
        messages_by_channel=by_ch,
        snapshots=snapshots,
        timeline=timeline,
        report_html=report_html,
        comparison_html=cmp_html,
        judge_html=j_html,
    )


def list_runs(runs_dir: Path, *, limit: int = 200) -> list[tuple[Path, str]]:
    """(absolute_path, url_path) newest first for top-level runs with summary.json."""

    runs_dir = runs_dir.resolve()
    if not runs_dir.is_dir():
        return []
    out: list[tuple[float, Path, str]] = []
    for child in runs_dir.iterdir():
        if not child.is_dir():
            continue
        if not (child / "summary.json").exists() or (child / "manifest.json").exists():
            continue
        mtime = child.stat().st_mtime
        rel = child.name
        out.append((mtime, child, rel))
    out.sort(key=lambda x: x[0], reverse=True)
    return [(p, rel) for _, p, rel in out[:limit]]


def list_batches(runs_dir: Path, *, limit: int = 100) -> list[tuple[Path, str]]:
    runs_dir = runs_dir.resolve()
    if not runs_dir.is_dir():
        return []
    out: list[tuple[float, Path, str]] = []
    for child in runs_dir.iterdir():
        if not child.is_dir():
            continue
        if not (child / "manifest.json").exists():
            continue
        mtime = child.stat().st_mtime
        out.append((mtime, child, child.name))
    out.sort(key=lambda x: x[0], reverse=True)
    return [(p, name) for _, p, name in out[:limit]]
