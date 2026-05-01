"""Optional LLM-as-judge over a completed run directory."""

from __future__ import annotations

import json
import re
from pathlib import Path

import yaml

from harness.runner import load_api_key


def _compact_timeline(timeline_path: Path, max_lines: int = 80) -> str:
    if not timeline_path.exists():
        return "(no timeline)"
    lines = timeline_path.read_text(encoding="utf-8").strip().splitlines()
    pick = lines[-max_lines:]
    return "\n".join(pick)


def judge_run(
    run_dir: Path,
    *,
    judge_model: str,
    secrets: Path | None = None,
) -> str:
    """Return markdown critique for a single run."""

    from harness.integrations.openrouter import OpenRouterClient

    run_dir = run_dir.resolve()
    summary = {}
    sp = run_dir / "summary.json"
    if sp.exists():
        summary = json.loads(sp.read_text(encoding="utf-8"))
    meta = {}
    mp = run_dir / "meta.yaml"
    if mp.exists():
        meta = yaml.safe_load(mp.read_text(encoding="utf-8")) or {}

    timeline_excerpt = _compact_timeline(run_dir / "timeline.jsonl")

    system = """You evaluate coaching quality in a fictional org simulation.
Score 1-5 where 5 = excellent coaching (timely, respectful of agency, aligned with stated best practices).
Name specific risks: e.g. over-coaching, public shame, ignoring blockers.
Output markdown with: ## Score, ## Strengths, ## Risks, ## Suggestions."""

    user = f"""## Run meta
{json.dumps(meta, indent=2)[:4000]}

## Summary
{json.dumps(summary, indent=2)[:4000]}

## Timeline excerpt (latest events)
{timeline_excerpt[:12000]}
"""

    client = OpenRouterClient(api_key=load_api_key(secrets))
    text, _usage = client.chat_text(
        model=judge_model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        temperature=0.3,
        max_tokens=1200,
    )
    return text.strip()


def judge_batch(
    batch_dir: Path,
    *,
    judge_model: str,
    secrets: Path | None = None,
    max_runs: int = 20,
) -> Path:
    """Write batch_dir/judge_report.md with per-run short critiques."""

    batch_dir = batch_dir.resolve()
    sections: list[str] = [f"# Judge report (`{judge_model}`)", ""]

    manifest_path = batch_dir / "manifest.json"
    paths: list[Path] = []
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        for run in manifest.get("runs") or []:
            if run.get("ok") and run.get("path"):
                paths.append(batch_dir / run["path"])
    else:
        paths = [p for p in batch_dir.iterdir() if p.is_dir() and (p / "summary.json").exists()]

    for i, rd in enumerate(paths[:max_runs]):
        try:
            body = judge_run(rd, judge_model=judge_model, secrets=secrets)
        except Exception as err:  # noqa: BLE001
            body = f"(judge failed: {err})"
        sections += [f"## Run `{rd.name}`", "", body, ""]

    out = batch_dir / "judge_report.md"
    out.write_text("\n".join(sections), encoding="utf-8")
    return out


def parse_score_from_judge_markdown(text: str) -> float | None:
    m = re.search(r"##\s*Score[^\n]*\n+\s*(\d+(?:\.\d+)?)", text, re.I)
    if m:
        try:
            return float(m.group(1))
        except ValueError:
            return None
    m2 = re.search(r"\*\*Score\*\*[:\s]+(\d+(?:\.\d+)?)", text, re.I)
    if m2:
        try:
            return float(m2.group(1))
        except ValueError:
            return None
    return None
