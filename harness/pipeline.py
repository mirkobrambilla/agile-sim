"""One-shot experiment pipeline: matrix → metrics JSON → optional judge → report → optional LLM comparison."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from harness.analyse import analyse_batch, batch_metrics, manifest_run_count, write_results_json
from harness.batch import run_matrix
from harness.judge import judge_batch
from harness.runner import load_api_key


def synthesize_comparison(
    batch_dir: Path,
    *,
    model: str,
    secrets: Path | None = None,
    max_report_chars: int = 14_000,
    max_judge_chars: int = 10_000,
) -> Path:
    """Single LLM call: interpret quantitative report (+ judge text if present)."""

    from harness.integrations.openrouter import OpenRouterClient

    batch_dir = batch_dir.resolve()
    rep_path = batch_dir / "report.md"
    if not rep_path.exists():
        raise FileNotFoundError(f"Missing {rep_path}; run analyse first")
    report = rep_path.read_text(encoding="utf-8")
    metrics = batch_metrics(batch_dir)
    judge_text = ""
    jp = batch_dir / "judge_report.md"
    if jp.exists():
        judge_text = jp.read_text(encoding="utf-8")[:max_judge_chars]

    system = """You compare experimental variants from a multi-agent org simulation harness.
Write clear, scannable markdown for engineers. No marketing tone.
Use bullets and short tables where helpful. If data is thin (n=1), say so explicitly."""

    user_parts = [
        "## Structured metrics\n```json\n",
        json.dumps(metrics, indent=2, default=str)[:8000],
        "\n```\n\n## Quantitative report (markdown)\n\n",
        report[:max_report_chars],
    ]
    if judge_text:
        user_parts.extend(["\n\n## Per-run judge critiques (excerpt)\n\n", judge_text])
    user_parts.append(
        "\n\n---\nProduce a **Comparison** with:\n"
        "1. **Executive summary** (5–8 bullets)\n"
        "2. **Variant ranking** — goal rate, stress-abort rate, mean cost, caveats\n"
        "3. **Patterns** — what differed between variants (coaching style, stress, work_done)\n"
        "4. **Next experiments** — 2–4 concrete suggestions\n"
    )
    user = "".join(user_parts)

    client = OpenRouterClient(api_key=load_api_key(secrets))
    text, _usage = client.chat_text(
        model=model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        temperature=0.35,
        max_tokens=1800,
    )
    out = batch_dir / "comparison.md"
    out.write_text(text.strip() + "\n", encoding="utf-8")
    return out


def run_experiment(
    matrix_file: Path,
    *,
    out: Path = Path("runs"),
    scenario_override: Path | None = None,
    secrets: Path | None = None,
    verbose: bool = False,
    with_judge: bool | None = None,
    judge_model: str = "google/gemma-4-26b-a4b-it:free",
    max_judge_runs: int = 20,
    llm_summary: bool = True,
    summary_model: str | None = None,
    experiment_auto_judge_limit: int | None = None,
) -> dict[str, Any]:
    """Run matrix, write results.json, optional judge, report.md, optional comparison.md."""

    out = out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    lim = (
        experiment_auto_judge_limit
        if experiment_auto_judge_limit is not None
        else int(os.environ.get("EXPERIMENT_AUTO_JUDGE_LIMIT", "12"))
    )
    batch_root = run_matrix(
        matrix_file.resolve(),
        out=out,
        scenario_override=scenario_override.resolve() if scenario_override else None,
        secrets=secrets,
        verbose=verbose,
    )
    write_results_json(batch_root)

    n_sched = manifest_run_count(batch_root)
    if with_judge is True:
        do_judge = True
    elif with_judge is False:
        do_judge = False
    else:
        do_judge = n_sched <= lim

    judge_path: Path | None = None
    if do_judge:
        judge_path = judge_batch(
            batch_root,
            judge_model=judge_model,
            secrets=secrets,
            max_runs=max_judge_runs,
        )

    report_path = analyse_batch(batch_root, judge_path=judge_path)

    write_results_json(batch_root)

    comparison_path: Path | None = None
    if llm_summary:
        model = summary_model or judge_model
        comparison_path = synthesize_comparison(
            batch_root,
            model=model,
            secrets=secrets,
        )

    return {
        "batch_root": batch_root,
        "results_json": batch_root / "results.json",
        "report": report_path,
        "judge_report": judge_path,
        "comparison": comparison_path,
    }
