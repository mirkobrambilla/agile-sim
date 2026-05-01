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


def scenario_from_bundle_meta(meta: dict[str, Any]) -> dict[str, Any]:
    """Public: load scenario YAML dict referenced by run meta."""

    return _scenario_dict_from_meta(meta)


def vitals_history_for_character(
    bundle: RunBundle, char_id: str, vital: str
) -> list[tuple[int, int]]:
    """(turn, value) pairs from snapshots."""

    out: list[tuple[int, int]] = []
    cid = str(char_id)
    for s in bundle.snapshots:
        chars = (s.world or {}).get("characters") or {}
        ch = chars.get(cid)
        if ch is None and cid in chars:
            ch = chars[cid]
        if not isinstance(ch, dict):
            continue
        v = (ch.get("vitals") or {}).get(vital)
        if v is None:
            continue
        try:
            out.append((int(s.turn), int(v)))
        except (TypeError, ValueError):
            continue
    return out


def recent_posts_for_character(
    bundle: RunBundle, char_id: str, *, limit: int = 8
) -> list[UiMessage]:
    """Messages in this character's DM thread plus any channel posts they authored."""

    cid = str(char_id)
    buf: list[UiMessage] = []
    dm = f"dm/{cid}"
    for ch, msgs in bundle.messages_by_channel.items():
        if ch == dm:
            buf.extend(msgs)
            continue
        for m in msgs:
            if m.author == cid:
                buf.append(m)
    buf.sort(key=lambda x: (x.turn, x.id))
    return buf[-limit:]


def agent_narrative_snippets(bundle: RunBundle, char_id: str, *, limit: int = 12) -> list[dict[str, Any]]:
    """Recent agent_turn narrative lines for a character."""

    cid = str(char_id)
    buf: list[dict[str, Any]] = []
    for row in bundle.timeline:
        if row.kind != "agent_turn":
            continue
        if str(row.raw.get("character") or "") != cid:
            continue
        buf.append(
            {
                "turn": row.raw.get("turn"),
                "narrative": row.raw.get("narrative") or "",
            }
        )
    return buf[-limit:]


def work_item_timeline_events(bundle: RunBundle, work_item_id: str) -> list[dict[str, Any]]:
    """Rows from timeline agent_turn entries touching this work item id."""

    wid = str(work_item_id)
    rows: list[dict[str, Any]] = []
    for row in bundle.timeline:
        if row.kind != "agent_turn":
            continue
        raw = row.raw
        for wu in raw.get("work_updates") or []:
            iid = str(wu.get("id") or wu.get("work_item_id") or "")
            if iid == wid:
                rows.append(
                    {
                        "turn": raw.get("turn"),
                        "character": raw.get("character"),
                        "update": wu,
                    }
                )
    return rows


def channel_meta_for(
    bundle: RunBundle, channel: str, scenario: dict[str, Any]
) -> dict[str, Any]:
    ch = channel.strip()
    members: list[str] = []
    engagement = "post"
    if ch.startswith("dm/"):
        owner = ch[3:].strip()
        members = ["coach", owner] if owner else ["coach"]
    else:
        for cdef in scenario.get("channels") or []:
            name = str(cdef.get("name", "")).strip()
            if name == ch:
                members = [str(x) for x in (cdef.get("member_ids") or [])]
                engagement = str(cdef.get("coach_engagement") or "post")
                break
    n_msgs = len(bundle.messages_by_channel.get(ch, []))
    return {"channel": ch, "members": members, "coach_engagement": engagement, "message_count": n_msgs}


def svg_sparkline(values: list[int], *, width: int = 120, height: int = 28) -> str:
    """Minimal SVG polyline; color via currentColor in CSS."""

    if not values:
        return ""
    w, h = width, height
    lo, hi = min(values), max(values)
    if hi == lo:
        hi = lo + 1
    pts: list[str] = []
    for i, v in enumerate(values):
        x = 2 + (i / max(1, len(values) - 1)) * (w - 4)
        y = h - 3 - (v - lo) / (hi - lo) * (h - 6)
        pts.append(f"{x:.1f},{y:.1f}")
    pstr = " ".join(pts)
    return (
        f'<svg class="vital-spark-svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" '
        'xmlns="http://www.w3.org/2000/svg" aria-hidden="true">'
        f'<polyline fill="none" stroke="currentColor" stroke-width="1.5" points="{pstr}"/>'
        "</svg>"
    )


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
