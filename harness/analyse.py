"""Summarise a batch directory or a single run directory into report.md."""

from __future__ import annotations

import json
import re
from collections import defaultdict
from pathlib import Path
from statistics import mean, pstdev
from typing import Any

import yaml


def load_meta(run_dir: Path) -> dict[str, Any]:
    p = run_dir / "meta.yaml"
    if p.exists():
        return yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    return {}


def load_summary(run_dir: Path) -> dict[str, Any] | None:
    p = run_dir / "summary.json"
    if not p.exists():
        return None
    return json.loads(p.read_text(encoding="utf-8"))


def _collect_run_rows(target: Path) -> list[dict[str, Any]]:
    """Rows for comparison tables: either one single run, manifest entries, or child run dirs."""

    rows: list[dict[str, Any]] = []
    if (target / "summary.json").exists():
        sub = batch_detail(target)
        if sub:
            rows.append(sub)
        return rows

    manifest_path = target / "manifest.json"
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        for run in manifest.get("runs") or []:
            path_key = run.get("path")
            if not path_key:
                continue
            sub = batch_detail(target / path_key)
            if sub:
                rows.append(sub)
        return rows

    for sub in sorted(target.iterdir()):
        if sub.is_dir():
            r = batch_detail(sub)
            if r:
                rows.append(r)
    return rows


def _load_snapshots_trajectory(run_dir: Path) -> list[dict[str, Any]]:
    path = run_dir / "snapshots.jsonl"
    if not path.exists():
        return []
    out: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
            out.append(rec)
        except json.JSONDecodeError:
            continue
    return out


def _load_llm_calls(run_dir: Path) -> list[dict[str, Any]]:
    path = run_dir / "llm_calls.jsonl"
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


def _append_single_run_detail(run_dir: Path, lines: list[str]) -> None:
    """Vitals-by-turn, work progress, LLM stats (single run folder only)."""

    snaps = _load_snapshots_trajectory(run_dir)
    if snaps:
        lines += ["## Vitals and work (end of each simulation turn)", ""]
        char_ids: list[str] = []
        first_world = (snaps[0].get("world") or {})
        chars = first_world.get("characters") or {}
        char_ids = sorted(chars.keys())
        header = "| Turn | " + " | ".join(
            f"{cid} E/M/S" for cid in char_ids
        )
        header += " | done | delivery % | msgs |"
        num_cols = 1 + len(char_ids) + 3
        sep = "|" + "|".join(["---"] * num_cols) + "|"
        lines.append(header)
        lines.append(sep)
        for s in snaps:
            turn = s.get("turn", "?")
            w = s.get("world") or {}
            ch = w.get("characters") or {}
            cells: list[str] = []
            for cid in char_ids:
                v = (ch.get(cid) or {}).get("vitals") or {}
                cells.append(
                    f"{v.get('energy', '?')}/{v.get('motivation', '?')}/{v.get('stress', '?')}"
                )
            wis = w.get("work_items") or []
            done = sum(1 for wi in wis if wi.get("state") == "done")
            dp = (w.get("org") or {}).get("delivery_progress", "?")
            nmsg = len(w.get("messages") or [])
            lines.append(
                f"| {turn} | " + " | ".join(cells) + f" | {done} | {dp} | {nmsg} |"
            )
        lines.append("")

    llm_rows = _load_llm_calls(run_dir)
    if llm_rows:
        lines += ["## LLM calls", ""]
        lines.append(f"- Total API calls: **{len(llm_rows)}**")
        by_role: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for r in llm_rows:
            by_role[str(r.get("role", "?"))].append(r)
        for role in sorted(by_role.keys()):
            xs = by_role[role]
            latencies = [int(x.get("latency_ms", 0) or 0) for x in xs]
            costs = []
            toks_in = 0
            toks_out = 0
            for x in xs:
                u = x.get("usage") or {}
                toks_in += int(u.get("input_tokens", 0) or 0)
                toks_out += int(u.get("output_tokens", 0) or 0)
                c = u.get("cost")
                if c is not None:
                    costs.append(float(c))
            lines.append(
                f"- **{role}**: {len(xs)} calls, "
                f"latency mean **{int(mean(latencies)) if latencies else 0}** ms, "
                f"tokens in/out **{toks_in}** / **{toks_out}**"
                + (
                    f", subtotal cost **{_fmt(sum(costs), 4)}** USD"
                    if costs
                    else ""
                )
            )
        slow = sorted(llm_rows, key=lambda x: int(x.get("latency_ms", 0) or 0), reverse=True)[:5]
        lines += ["", "Slowest calls:", ""]
        for r in slow:
            who = r.get("character") or r.get("role", "")
            lines.append(
                f"- turn **{r.get('turn')}** {who} @ {r.get('model', '')}: "
                f"**{r.get('latency_ms')}** ms"
            )
        lines.append("")

    summ = load_summary(run_dir)
    if summ:
        fv = summ.get("final_vitals") or {}
        lines += ["## Outcome (from summary.json)", ""]
        lines.append(f"- **Goal met:** {summ.get('goal_met')}")
        lines.append(f"- **Final turn:** {summ.get('final_turn')}")
        lines.append(f"- **Work items done:** {summ.get('work_done')}")
        lines.append(f"- **Aborted (stress):** {summ.get('aborted_stress')}")
        if fv:
            lines.append("- **Final vitals:**")
            for cid in sorted(fv.keys()):
                lines.append(f"  - `{cid}`: {fv[cid]}")
        org = summ.get("org") or {}
        if org:
            lines.append(f"- **Org:** {org}")
        lines.append("")


def analyse_batch(batch_dir: Path, *, judge_path: Path | None = None) -> Path:
    batch_dir = batch_dir.resolve()
    rows = _collect_run_rows(batch_dir)
    judge_map = _judge_scores_by_run_name(batch_dir)
    for r in rows:
        pk = str(r.get("path") or "")
        if pk in judge_map:
            r["judge_score"] = judge_map[pk]

    by_variant: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for r in rows:
        vn = str(r.get("variant_name") or "default")
        by_variant[vn].append(r)

    is_single_run = (batch_dir / "summary.json").exists() and not (batch_dir / "manifest.json").exists()

    title = f"# Run analysis: `{batch_dir.name}`" if is_single_run else f"# Batch analysis: `{batch_dir.name}`"
    lines: list[str] = [
        title,
        "",
        f"Run folders scanned: **{len(rows)}** with `summary.json`.",
        "",
    ]

    if is_single_run:
        meta = load_meta(batch_dir)
        if meta:
            lines += ["## Meta", "", f"```yaml\n{yaml.safe_dump(meta, sort_keys=False).strip()}\n```", ""]

    for vname, items in sorted(by_variant.items()):
        goals = [1 if x.get("goal_met") else 0 for x in items]
        costs = [float(x.get("cost", 0) or 0) for x in items]
        tok_in = [int(x.get("input_tokens", 0) or 0) for x in items]
        tok_out = [int(x.get("output_tokens", 0) or 0) for x in items]
        work_done = [int(x.get("work_done", 0) or 0) for x in items]

        lines += [
            f"## Variant: `{vname}`",
            "",
            f"- Runs: {len(items)}",
            f"- Goal rate: {_rate(goals)} ({sum(goals)}/{len(items)})",
            f"- Work items done (mean ± stdev): {_fmt(mean(work_done), 2)} ± {_fmt(_pstdev(work_done), 2)}",
            f"- Cost USD (mean ± stdev): {_fmt(mean(costs), 4)} ± {_fmt(_pstdev(costs), 4)}",
            f"- Tokens in (mean): {int(mean(tok_in)) if tok_in else 0}",
            f"- Tokens out (mean): {int(mean(tok_out)) if tok_out else 0}",
            "",
        ]
        j_scores = [float(x["judge_score"]) for x in items if x.get("judge_score") is not None]
        if j_scores:
            lines.append(f"- Mean judge score: {_fmt(mean(j_scores), 2)} (n={len(j_scores)})")
            lines.append("")
        lines += [
            "| run | goal | work_done | cost | judge | agent_model |",
            "|-----|------|------------|------|-------|-------------|",
        ]
        for x in sorted(items, key=lambda z: z.get("path", "")):
            js = x.get("judge_score")
            js_s = _fmt(float(js), 2) if js is not None else ""
            lines.append(
                f"| `{x.get('path')}` | {x.get('goal_met')} | {x.get('work_done')} | "
                f"{_fmt(float(x.get('cost', 0) or 0), 4)} | {js_s} | {x.get('agent_model', '')} |"
            )
        lines.append("")

    if judge_path and judge_path.exists():
        lines += ["## Judge notes", "", judge_path.read_text(encoding="utf-8"), ""]

    if is_single_run:
        _append_single_run_detail(batch_dir, lines)

    out = batch_dir / "report.md"
    out.write_text("\n".join(lines), encoding="utf-8")
    return out


def batch_detail(run_dir: Path) -> dict[str, Any] | None:
    if not run_dir.is_dir():
        return None
    summ = load_summary(run_dir)
    if summ is None:
        return None
    meta = load_meta(run_dir)
    totals = summ.get("totals") or {}
    return {
        "path": run_dir.name,
        "variant_name": meta.get("variant_name"),
        "goal_met": summ.get("goal_met"),
        "aborted_stress": summ.get("aborted_stress"),
        "final_turn": summ.get("final_turn"),
        "work_done": summ.get("work_done"),
        "cost": totals.get("cost"),
        "input_tokens": totals.get("input_tokens"),
        "output_tokens": totals.get("output_tokens"),
        "agent_model": (meta.get("models") or {}).get("agent"),
        "coach_model": (meta.get("models") or {}).get("coach"),
        "coach_mode": meta.get("coach_mode"),
    }


def _rate(xs: list[int]) -> str:
    if not xs:
        return "n/a"
    return f"{100.0 * sum(xs) / len(xs):.1f}%"


def _fmt(x: float, nd: int) -> str:
    return f"{x:.{nd}f}"


def _pstdev(xs: list[float | int]) -> float:
    if len(xs) < 2:
        return 0.0
    return float(pstdev(xs))


def manifest_run_count(batch_dir: Path) -> int:
    mp = batch_dir / "manifest.json"
    if not mp.exists():
        return 0
    try:
        data = json.loads(mp.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return 0
    return len(data.get("runs") or [])


def _judge_scores_by_run_name(batch_dir: Path) -> dict[str, float]:
    """Map run folder name → score from judge_report.md sections."""

    from harness.judge import parse_score_from_judge_markdown

    jp = batch_dir / "judge_report.md"
    if not jp.exists():
        return {}
    text = jp.read_text(encoding="utf-8")
    out: dict[str, float] = {}
    header = re.compile(r"^## Run `([^`]+)`\s*$", re.M)
    matches = list(header.finditer(text))
    for i, m in enumerate(matches):
        name = m.group(1).strip()
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        body = text[start:end]
        sc = parse_score_from_judge_markdown(body)
        if sc is not None:
            out[name] = float(sc)
    return out


def batch_metrics(batch_dir: Path) -> dict[str, Any]:
    """Structured metrics for automation, results.json, and LLM synthesis."""

    batch_dir = batch_dir.resolve()
    judge_map = _judge_scores_by_run_name(batch_dir)
    rows = _collect_run_rows(batch_dir)
    for r in rows:
        pk = str(r.get("path") or "")
        if pk in judge_map:
            r["judge_score"] = judge_map[pk]
    by_variant: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for r in rows:
        vn = str(r.get("variant_name") or "default")
        by_variant[vn].append(r)

    variants: list[dict[str, Any]] = []
    for vname, items in sorted(by_variant.items()):
        goals = [bool(x.get("goal_met")) for x in items]
        aborts = [bool(x.get("aborted_stress")) for x in items]
        costs = [float(x.get("cost", 0) or 0) for x in items]
        work_done = [int(x.get("work_done", 0) or 0) for x in items]
        turns = [int(x.get("final_turn", 0) or 0) for x in items]
        judge_vals = [float(x["judge_score"]) for x in items if x.get("judge_score") is not None]
        mean_judge: float | None = float(mean(judge_vals)) if judge_vals else None
        variants.append(
            {
                "name": vname,
                "n_runs": len(items),
                "goals_met": sum(1 for g in goals if g),
                "goal_rate": (sum(1 for g in goals if g) / len(items)) if items else 0.0,
                "stress_abort_rate": (sum(1 for a in aborts if a) / len(items)) if items else 0.0,
                "mean_cost_usd": mean(costs) if costs else 0.0,
                "stdev_cost_usd": _pstdev(costs) if costs else 0.0,
                "mean_work_done": mean(work_done) if work_done else 0.0,
                "mean_final_turn": mean(turns) if turns else 0.0,
                "mean_judge_score": mean_judge,
                "runs": [
                    {
                        "path": x.get("path"),
                        "goal_met": x.get("goal_met"),
                        "aborted_stress": x.get("aborted_stress"),
                        "work_done": x.get("work_done"),
                        "final_turn": x.get("final_turn"),
                        "cost": x.get("cost"),
                        "coach_mode": x.get("coach_mode"),
                        "judge_score": x.get("judge_score"),
                    }
                    for x in sorted(items, key=lambda z: str(z.get("path", "")))
                ],
            }
        )

    all_judge = [float(r["judge_score"]) for r in rows if r.get("judge_score") is not None]
    mean_judge_overall: float | None = float(mean(all_judge)) if all_judge else None
    ok_manifest = True
    manifest_path = batch_dir / "manifest.json"
    manifest_slim: dict[str, Any] | None = None
    if manifest_path.exists():
        try:
            manifest_snapshot = json.loads(manifest_path.read_text(encoding="utf-8"))
            for run in manifest_snapshot.get("runs") or []:
                if not run.get("ok", True):
                    ok_manifest = False
            manifest_slim = {
                "batch_id": manifest_snapshot.get("batch_id"),
                "matrix_file": manifest_snapshot.get("matrix_file"),
                "scenario_dir": manifest_snapshot.get("scenario_dir"),
                "runs": [
                    {
                        "path": r.get("path"),
                        "ok": r.get("ok"),
                        "variant_name": r.get("variant_name"),
                        "error": r.get("error"),
                    }
                    for r in manifest_snapshot.get("runs") or []
                ],
            }
        except json.JSONDecodeError:
            manifest_slim = None
            ok_manifest = False

    return {
        "batch_dir": batch_dir.name,
        "n_runs_with_summary": len(rows),
        "mean_judge_score": mean_judge_overall,
        "all_manifest_runs_ok": ok_manifest,
        "variants": variants,
        "manifest": manifest_slim,
    }


def write_results_json(batch_dir: Path) -> Path:
    """Write batch_dir/results.json for scripting and dashboards."""

    batch_dir = batch_dir.resolve()
    payload = batch_metrics(batch_dir)
    out = batch_dir / "results.json"
    out.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    return out
