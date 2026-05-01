"""CLI entry: run, batch, matrix, analyse, judge."""

from __future__ import annotations

import json
import os
from pathlib import Path

import click
from rich.console import Console

from harness.analyse import analyse_batch
from harness.batch import run_batch, run_matrix
from harness.judge import judge_batch
from harness.pipeline import run_experiment
from harness.runner import dispatch_run

console = Console()


@click.group()
def main() -> None:
    """Agile-sim headless harness."""


@main.command("run")
@click.argument("scenario_dir", type=click.Path(exists=True, file_okay=False, path_type=Path))
@click.option("--out", type=click.Path(path_type=Path), default=Path("runs"))
@click.option("--model", "agent_model", default="google/gemini-3-flash-preview", show_default=True)
@click.option("--coach-model", default=None, help="Defaults to --model")
@click.option(
    "--coach-mode",
    type=click.Choice(["llm", "none", "preset"], case_sensitive=False),
    default=None,
    help="Coach: llm (each turn), none, or preset YAML. Default: scenario harness.coach_mode or llm.",
)
@click.option(
    "--coach-preset",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    default=None,
    help="YAML preset for --coach-mode preset (overrides scenario harness.coach_preset_file).",
)
@click.option("--seed", type=int, default=None)
@click.option("--secrets", type=click.Path(path_type=Path), default=None)
@click.option(
    "-v",
    "--verbose",
    is_flag=True,
    help="Print run progress (turns, agent/coach calls) to stderr.",
)
def cmd_run(
    scenario_dir: Path,
    out: Path,
    agent_model: str,
    coach_model: str | None,
    coach_mode: str | None,
    coach_preset: Path | None,
    seed: int | None,
    secrets: Path | None,
    verbose: bool,
) -> None:
    out.mkdir(parents=True, exist_ok=True)
    summary = dispatch_run(
        scenario_dir.resolve(),
        out=out.resolve(),
        agent_model=agent_model,
        coach_model=coach_model,
        seed=seed,
        secrets=secrets,
        coach_mode_cli=coach_mode,
        coach_preset_cli=coach_preset,
        verbose=verbose,
    )
    console.print(json.dumps(summary, indent=2))
    run_name = str(summary.get("run_id") or "").strip()
    if run_name:
        console.print(
            f"[dim]View in browser:[/dim] [cyan]agile-harness view runs/{run_name}[/cyan] "
            f"(after [cyan]agile-harness serve[/cyan])",
        )


@main.command("batch")
@click.argument("scenario_dir", type=click.Path(exists=True, file_okay=False, path_type=Path))
@click.option("--out", type=click.Path(path_type=Path), default=Path("runs"))
@click.option("--runs", type=int, required=True)
@click.option("--model", "agent_model", default="google/gemini-3-flash-preview", show_default=True)
@click.option("--coach-model", default=None)
@click.option("--concurrency", type=int, default=3, show_default=True)
@click.option("--seed-base", type=int, default=None)
@click.option("--secrets", type=click.Path(path_type=Path), default=None)
@click.option(
    "--coach-mode",
    type=click.Choice(["llm", "none", "preset"], case_sensitive=False),
    default=None,
)
@click.option(
    "--coach-preset",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    default=None,
)
@click.option(
    "-v",
    "--verbose",
    is_flag=True,
    help="Print each run's progress to stderr (prefix shows batch job index).",
)
def cmd_batch(
    scenario_dir: Path,
    out: Path,
    runs: int,
    agent_model: str,
    coach_model: str | None,
    concurrency: int,
    seed_base: int | None,
    secrets: Path | None,
    coach_mode: str | None,
    coach_preset: Path | None,
    verbose: bool,
) -> None:
    out.mkdir(parents=True, exist_ok=True)
    batch_root = run_batch(
        scenario_dir.resolve(),
        out=out.resolve(),
        runs=runs,
        agent_model=agent_model,
        coach_model=coach_model,
        concurrency=concurrency,
        seed_base=seed_base,
        secrets=secrets,
        coach_mode_cli=coach_mode,
        coach_preset_cli=coach_preset,
        verbose=verbose,
    )
    console.print(f"Batch complete: [bold]{batch_root}[/bold]")
    console.print(
        "[dim]Experiment summary:[/dim] [cyan]agile-harness experiment …[/cyan] · "
        "[dim]serve:[/dim] [cyan]agile-harness serve[/cyan]",
    )


@main.command("matrix")
@click.argument("matrix_file", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option("--out", type=click.Path(path_type=Path), default=Path("runs"))
@click.option(
    "--scenario",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    default=None,
    help="Override scenario_dir in matrix file",
)
@click.option("--secrets", type=click.Path(path_type=Path), default=None)
@click.option(
    "-v",
    "--verbose",
    is_flag=True,
    help="Print each variant run's progress to stderr.",
)
def cmd_matrix(
    matrix_file: Path,
    out: Path,
    scenario: Path | None,
    secrets: Path | None,
    verbose: bool,
) -> None:
    out.mkdir(parents=True, exist_ok=True)
    batch_root = run_matrix(
        matrix_file.resolve(),
        out=out.resolve(),
        scenario_override=scenario.resolve() if scenario else None,
        secrets=secrets,
        verbose=verbose,
    )
    console.print(f"Matrix batch: [bold]{batch_root}[/bold]")
    console.print("[dim]Then:[/dim] [cyan]agile-harness experiment <matrix.yaml>[/cyan]")


EXPERIMENT_JUDGE_DEFAULT_MODEL = "google/gemini-3-flash-preview"


@main.command("experiment")
@click.argument("matrix_file", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option("--out", type=click.Path(path_type=Path), default=Path("runs"))
@click.option(
    "--scenario",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    default=None,
    help="Override scenario_dir in matrix file",
)
@click.option("--secrets", type=click.Path(path_type=Path), default=None)
@click.option(
    "-v",
    "--verbose",
    is_flag=True,
    help="Print matrix run progress to stderr.",
)
@click.option(
    "--judge",
    "judge_cli",
    type=click.Choice(["auto", "on", "off"], case_sensitive=False),
    default="auto",
    show_default=True,
    help="Judge runs: auto when batch has ≤ EXPERIMENT_AUTO_JUDGE_LIMIT runs (default 12).",
)
@click.option(
    "--no-judge",
    is_flag=True,
    help="Skip judge (--judge off).",
)
@click.option(
    "--judge-model",
    default=EXPERIMENT_JUDGE_DEFAULT_MODEL,
    show_default=True,
)
@click.option("--max-judge-runs", type=int, default=20, show_default=True)
@click.option(
    "--llm-summary/--no-llm-summary",
    default=True,
    help="One LLM call to write comparison.md from metrics + report (+ judge if run).",
)
@click.option(
    "--summary-model",
    default=None,
    help="Model for comparison.md (default: same as --judge-model).",
)
def cmd_experiment(
    matrix_file: Path,
    out: Path,
    scenario: Path | None,
    secrets: Path | None,
    verbose: bool,
    judge_cli: str,
    no_judge: bool,
    judge_model: str,
    max_judge_runs: int,
    llm_summary: bool,
    summary_model: str | None,
) -> None:
    """Run matrix → results.json → report.md; optionally judge + LLM comparison.md."""

    if no_judge and judge_cli != "auto":
        raise click.UsageError("Use either --no-judge or set --judge, not both.")
    judge_opt: bool | None
    if no_judge:
        judge_opt = False
    elif judge_cli == "auto":
        judge_opt = None
    elif judge_cli == "on":
        judge_opt = True
    else:
        judge_opt = False

    out.mkdir(parents=True, exist_ok=True)
    result = run_experiment(
        matrix_file.resolve(),
        out=out.resolve(),
        scenario_override=scenario.resolve() if scenario else None,
        secrets=secrets,
        verbose=verbose,
        with_judge=judge_opt,
        judge_model=judge_model,
        max_judge_runs=max_judge_runs,
        llm_summary=llm_summary,
        summary_model=summary_model,
    )
    root = result["batch_root"]
    console.print(f"Batch: [bold]{root}[/bold]")
    console.print(f"  metrics: [cyan]{result['results_json']}[/cyan]")
    console.print(f"  report:  [cyan]{result['report']}[/cyan]")
    if result.get("judge_report"):
        console.print(f"  judge:   [cyan]{result['judge_report']}[/cyan]")
    if result.get("comparison"):
        console.print(f"  compare: [cyan]{result['comparison']}[/cyan]")
    elif not llm_summary:
        console.print("  compare: (skipped; use --llm-summary to enable)")
    batch_name = Path(str(result["batch_root"])).name
    console.print(
        f"[dim]Mission control:[/dim] [cyan]agile-harness view runs/{batch_name}/<run_id>[/cyan] · "
        f"[cyan]http://127.0.0.1:8765/experiments/{batch_name}[/cyan]",
    )


@main.command("serve")
@click.option(
    "--runs-dir",
    type=click.Path(path_type=Path),
    default=None,
    help="Finished runs root (default: env AGILE_SIM_RUNS_DIR or ./runs).",
)
@click.option("--host", default="127.0.0.1", show_default=True)
@click.option("--port", type=int, default=8765, show_default=True)
@click.option("--reload", is_flag=True, help="Dev autoreload.")
def cmd_serve(runs_dir: Path | None, host: str, port: int, reload: bool) -> None:
    """Serve the read-only web UI over HTTP."""

    if runs_dir is not None:
        os.environ["AGILE_SIM_RUNS_DIR"] = str(runs_dir.expanduser().resolve())

    import uvicorn

    if reload:
        uvicorn.run(
            "harness.web.app:create_app",
            factory=True,
            host=host,
            port=port,
            reload=True,
        )
    else:
        from harness.web.app import create_app

        rd = Path(os.environ.get("AGILE_SIM_RUNS_DIR", "runs")).resolve()
        uvicorn.run(create_app(runs_dir=rd), host=host, port=port)


@main.command("view")
@click.argument("pathish", required=False)
@click.option("--runs-dir", type=click.Path(path_type=Path), default=None)
@click.option("--port", type=int, default=8765, show_default=True)
@click.option(
    "--open",
    "open_browser",
    is_flag=True,
    help="Open the URL in the default browser (requires agile-harness serve already running).",
)
def cmd_view(
    pathish: str | None, runs_dir: Path | None, port: int, open_browser: bool
) -> None:
    """Print a URL for a path under the runs directory (exits immediately; does not start the server)."""

    rd = Path(os.environ.get("AGILE_SIM_RUNS_DIR", "runs")).resolve()
    if runs_dir is not None:
        rd = runs_dir.expanduser().resolve()
        os.environ["AGILE_SIM_RUNS_DIR"] = str(rd)

    base = f"http://127.0.0.1:{port}"
    if not pathish or not pathish.strip():
        url = f"{base}/"
        console.print(url)
        if open_browser:
            import webbrowser

            webbrowser.open(url)
        console.print(
            "[dim]This command only prints a URL. Start the UI with[/dim] "
            "[cyan]agile-harness serve[/cyan][dim], then open the link above.[/dim]",
        )
        return

    p = pathish.strip().replace("\\", "/")
    if p.startswith("runs/"):
        p = p[len("runs/") :]
    p = p.strip("/")

    from harness.web.resolve import ResolvedRun, ResolvedBatch, resolve_slug_under_runs, run_url_path

    resolved, ambiguous = resolve_slug_under_runs(runs_dir=rd, slug=p)
    if ambiguous:
        console.print(
            f"[yellow]More than one folder matches prefix {p!r}:[/yellow] "
            + ", ".join(ambiguous[:15])
        )
        console.print("[dim]Use the full directory name in the URL.[/dim]")
        return
    if isinstance(resolved, ResolvedBatch):
        url = f"{base}/experiments/{resolved.batch_dir.name}"
    elif isinstance(resolved, ResolvedRun):
        rel = run_url_path(runs_dir=rd, run_dir=resolved.run_dir)
        url = f"{base}/runs/{rel}"
    else:
        url = f"{base}/runs/{p}"

    console.print(url)
    if open_browser:
        import webbrowser

        webbrowser.open(url)
    console.print(
        "[dim]This command only prints a URL. Start the UI with[/dim] "
        "[cyan]agile-harness serve[/cyan][dim], then open the link above "
        "(or pass[/dim] [cyan]--open[/cyan][dim]).[/dim]",
    )


@main.command("analyse")
@click.argument("batch_dir", type=click.Path(exists=True, file_okay=False, path_type=Path))
@click.option("--judge-report", type=click.Path(path_type=Path), default=None)
def cmd_analyse(batch_dir: Path, judge_report: Path | None) -> None:
    rep = analyse_batch(batch_dir.resolve(), judge_path=judge_report.resolve() if judge_report else None)
    console.print(f"Wrote [bold]{rep}[/bold]")


@main.command("judge")
@click.argument("batch_dir", type=click.Path(exists=True, file_okay=False, path_type=Path))
@click.option("--model", "judge_model", default="google/gemini-3-flash-preview", show_default=True)
@click.option("--secrets", type=click.Path(path_type=Path), default=None)
@click.option("--max-runs", type=int, default=20, show_default=True)
def cmd_judge(batch_dir: Path, judge_model: str, secrets: Path | None, max_runs: int) -> None:
    out = judge_batch(
        batch_dir.resolve(),
        judge_model=judge_model,
        secrets=secrets,
        max_runs=max_runs,
    )
    console.print(f"Wrote [bold]{out}[/bold]")


@main.group("assets")
def assets_grp() -> None:
    """Generate UI images from assets/manifest.yaml via OpenRouter."""


@assets_grp.command("list")
@click.option(
    "--manifest",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    default=None,
    help="Defaults to assets/manifest.yaml",
)
def cmd_assets_list(manifest: Path | None) -> None:
    from harness.assets import load_manifest, list_status

    root = Path(__file__).resolve().parents[1]
    m = load_manifest(manifest or (root / "assets" / "manifest.yaml"))
    for row in list_status(m, root=root):
        status = "cached" if row["cached"] else ("stale" if row["stale"] else "missing")
        console.print(
            f"[{status:7}] {row['set']}/{row['item']:30} {row['path']}",
        )


@assets_grp.command("generate")
@click.option(
    "--manifest",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    default=None,
)
@click.option("--set", "set_id", default=None, help="Only this set id (e.g. default)")
@click.option(
    "--item",
    "item_ref",
    default=None,
    help="Single item SET/item_id (e.g. default/happy)",
)
@click.option("--force", is_flag=True, help="Ignore hash cache")
@click.option("--dry-run", is_flag=True, help="Print jobs only; no API calls")
@click.option("--secrets", type=click.Path(path_type=Path), default=None)
def cmd_assets_generate(
    manifest: Path | None,
    set_id: str | None,
    item_ref: str | None,
    force: bool,
    dry_run: bool,
    secrets: Path | None,
) -> None:
    from harness.assets import filter_jobs, load_manifest, plan_jobs, run_jobs
    from harness.integrations.openrouter import OpenRouterClient
    from harness.runner import load_api_key

    root = Path(__file__).resolve().parents[1]
    man_path = manifest or (root / "assets" / "manifest.yaml")
    m = load_manifest(man_path)
    jobs = plan_jobs(m, root=root)
    jobs = filter_jobs(jobs, set_id=set_id, item_ref=item_ref)
    if not jobs:
        console.print("[yellow]No jobs matched filters.[/yellow]")
        raise SystemExit(1)

    if dry_run:
        client = None
    else:
        key = load_api_key(secrets)
        client = OpenRouterClient(api_key=key)

    rep = run_jobs(
        jobs,
        client,
        force=force,
        dry_run=dry_run,
        on_progress=lambda msg: console.print(f"[dim]{msg}[/dim]"),
    )
    console.print(
        f"planned={rep.planned} skipped={rep.skipped} generated={rep.generated} "
        f"would={rep.would_generate} failed={rep.failed}",
    )
    for e in rep.errors:
        console.print(f"[red]{e}[/red]")
    if rep.failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
