"""FastAPI app: read-only mission control + experiments."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from jinja2 import Environment, FileSystemLoader, select_autoescape

from harness.analyse import batch_metrics, load_meta
from harness.web.render import md_to_html
from harness.web.resolve import (
    ResolvedBatch,
    ResolvedRun,
    resolve_slug_under_runs,
    run_url_path,
)
from harness.web.run_reader import build_picker_entries, list_batches, list_runs, load_run


def _runs_dir_kw(runs_dir: Path | None) -> Path:
    if runs_dir is not None:
        return runs_dir.resolve()
    return Path(os.environ.get("AGILE_SIM_RUNS_DIR", "runs")).resolve()


def create_app(*, runs_dir: Path | None = None) -> FastAPI:
    runs_dir = _runs_dir_kw(runs_dir)
    pkg = Path(__file__).resolve().parent
    templates_dir = pkg / "templates"
    static_dir = pkg / "static"

    jinja = Environment(
        loader=FileSystemLoader(str(templates_dir)),
        autoescape=select_autoescape(["html", "xml"]),
    )
    jinja.filters["tojson"] = lambda v: json.dumps(v, indent=2, default=str, ensure_ascii=False)

    app = FastAPI(title="agile-sim harness", version="0.1")

    if static_dir.is_dir():
        app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

    def render(name: str, request: Request, **ctx: Any) -> HTMLResponse:
        tpl = jinja.get_template(name)
        html = tpl.render(request=request, **ctx)
        return HTMLResponse(html)

    def _require_resolved_run(run_path: str) -> ResolvedRun:
        r, amb = resolve_slug_under_runs(runs_dir=runs_dir, slug=run_path)
        if amb:
            raise HTTPException(
                status_code=404,
                detail=f"Ambiguous path prefix; use full name. Matches: {', '.join(amb[:15])}",
            )
        if isinstance(r, ResolvedBatch):
            raise HTTPException(
                status_code=404,
                detail="This URL is an experiment batch, not a single run. Use /experiments/<batch_id>.",
            )
        if not isinstance(r, ResolvedRun):
            raise HTTPException(status_code=404, detail="Run not found")
        return r

    @app.get("/", response_class=HTMLResponse)
    async def home(request: Request) -> HTMLResponse:
        picker_items = build_picker_entries(runs_dir)
        return render(
            "picker.html",
            request,
            runs_dir=str(runs_dir),
            picker_items=picker_items,
        )

    @app.get("/experiments", response_class=HTMLResponse)
    async def experiments_index(request: Request) -> HTMLResponse:
        batches = list_batches(runs_dir)
        rows = []
        for p, name in batches:
            try:
                m = batch_metrics(p)
            except Exception:  # noqa: BLE001
                m = None
            rows.append({"name": name, "path": str(p), "metrics": m})
        return render("experiments_index.html", request, batches=rows)

    @app.get("/experiments/{batch_id}", response_class=HTMLResponse)
    async def experiment_detail(request: Request, batch_id: str) -> HTMLResponse:
        bd = runs_dir / batch_id
        if not bd.is_dir() or not (bd / "manifest.json").exists():
            raise HTTPException(status_code=404, detail="batch not found")
        metrics = batch_metrics(bd)
        rep = bd / "report.md"
        cmp = bd / "comparison.md"
        judge = bd / "judge_report.md"
        report_html = md_to_html(rep.read_text(encoding="utf-8")) if rep.exists() else None
        cmp_html = md_to_html(cmp.read_text(encoding="utf-8")) if cmp.exists() else None
        judge_html = md_to_html(judge.read_text(encoding="utf-8")) if judge.exists() else None
        return render(
            "experiment.html",
            request,
            batch_id=batch_id,
            metrics=metrics,
            report_html=report_html,
            comparison_html=cmp_html,
            judge_html=judge_html,
        )

    @app.get("/runs/{run_path:path}/at/{turn}", response_class=HTMLResponse)
    async def runner_at_turn(request: Request, run_path: str, turn: int) -> HTMLResponse:
        return _runner_page(request, run_path, turn=turn)

    @app.get("/runs/{run_path:path}", response_class=HTMLResponse)
    async def runner(request: Request, run_path: str) -> HTMLResponse:
        return _runner_page(request, run_path, turn=None)

    def _runner_page(
        request: Request, run_path: str, *, turn: int | None
    ) -> HTMLResponse | RedirectResponse:
        r, ambiguous = resolve_slug_under_runs(runs_dir=runs_dir, slug=run_path)
        if ambiguous:
            opts = ", ".join(ambiguous[:20])
            more = f" (+{len(ambiguous) - 20} more)" if len(ambiguous) > 20 else ""
            raise HTTPException(
                status_code=404,
                detail=(
                    f"More than one folder under runs/ starts with {run_path!r}: {opts}{more}. "
                    "Use the full directory name (for example batch_…Z). "
                    "For a batch overview, open /experiments/<that name>."
                ),
            )
        if isinstance(r, ResolvedBatch):
            return RedirectResponse(
                url=f"/experiments/{r.batch_dir.name}",
                status_code=307,
            )
        if not isinstance(r, ResolvedRun):
            raise HTTPException(
                status_code=404,
                detail=(
                    f"No run or batch at runs/{run_path!r}. "
                    "Open http://127.0.0.1:8765/ to pick a folder, or use the full batch/run id."
                ),
            )
        url_p = run_url_path(runs_dir=runs_dir, run_dir=r.run_dir)
        bundle = load_run(run_dir=r.run_dir, url_path=url_p)
        eff_turn = turn
        if eff_turn is None:
            eff_turn = int(bundle.summary.get("final_turn") or 0) or 1
        snap_world = _snapshot_at(bundle, eff_turn)
        goal_status = _goal_stoplight(bundle.summary)
        max_turn = max(1, int(bundle.summary.get("final_turn") or 0) or 1)
        return render(
            "runner.html",
            request,
            bundle=bundle,
            effective_turn=eff_turn,
            max_turn=max_turn,
            snap_world=snap_world,
            goal_status=goal_status,
            channel_query=request.query_params.get("channel", bundle.primary_channel),
        )

    @app.get("/partials/run/{run_path:path}/channel", response_class=HTMLResponse)
    async def partial_channel(request: Request, run_path: str) -> HTMLResponse:
        ch = request.query_params.get("channel", "")
        turn_s = request.query_params.get("turn")
        turn = int(turn_s) if turn_s and turn_s.isdigit() else None
        r = _require_resolved_run(run_path)
        bundle = load_run(run_dir=r.run_dir, url_path=run_url_path(runs_dir=runs_dir, run_dir=r.run_dir))
        if not ch:
            ch = bundle.primary_channel
        msgs = bundle.messages_by_channel.get(ch, [])
        return render("partials/channel_view.html", request, bundle=bundle, channel=ch, messages=msgs, effective_turn=turn)

    @app.get("/partials/run/{run_path:path}/kanban", response_class=HTMLResponse)
    async def partial_kanban(request: Request, run_path: str) -> HTMLResponse:
        turn_s = request.query_params.get("turn")
        turn = int(turn_s) if turn_s and turn_s.isdigit() else None
        r = _require_resolved_run(run_path)
        bundle = load_run(run_dir=r.run_dir, url_path=run_url_path(runs_dir=runs_dir, run_dir=r.run_dir))
        world = _snapshot_at(bundle, turn) or {}
        items = world.get("work_items") or []
        cols = {"backlog": [], "doing": [], "done": [], "parked": []}
        for wi in items:
            st = str(wi.get("state", "backlog")).lower()
            if st in cols:
                cols[st].append(wi)
        return render("partials/kanban.html", request, bundle=bundle, columns=cols, effective_turn=turn)

    @app.get("/partials/run/{run_path:path}/timeline", response_class=HTMLResponse)
    async def partial_timeline(request: Request, run_path: str) -> HTMLResponse:
        r = _require_resolved_run(run_path)
        bundle = load_run(run_dir=r.run_dir, url_path=run_url_path(runs_dir=runs_dir, run_dir=r.run_dir))
        return render("partials/timeline.html", request, bundle=bundle)

    @app.get("/partials/run/{run_path:path}/summary", response_class=HTMLResponse)
    async def partial_summary(request: Request, run_path: str) -> HTMLResponse:
        r = _require_resolved_run(run_path)
        bundle = load_run(run_dir=r.run_dir, url_path=run_url_path(runs_dir=runs_dir, run_dir=r.run_dir))
        return render("partials/summary.html", request, bundle=bundle)

    @app.get("/partials/run/{run_path:path}/vitals", response_class=HTMLResponse)
    async def partial_vitals(request: Request, run_path: str) -> HTMLResponse:
        turn_s = request.query_params.get("turn")
        turn = int(turn_s) if turn_s and turn_s.isdigit() else None
        r = _require_resolved_run(run_path)
        bundle = load_run(run_dir=r.run_dir, url_path=run_url_path(runs_dir=runs_dir, run_dir=r.run_dir))
        world = _snapshot_at(bundle, turn) or {}
        chars = world.get("characters") or {}
        return render("partials/vitals_rail.html", request, bundle=bundle, characters=chars, effective_turn=turn)

    @app.get("/partials/run/{run_path:path}/goals", response_class=HTMLResponse)
    async def partial_goals(request: Request, run_path: str) -> HTMLResponse:
        r = _require_resolved_run(run_path)
        bundle = load_run(run_dir=r.run_dir, url_path=run_url_path(runs_dir=runs_dir, run_dir=r.run_dir))
        return render("partials/goals_panel.html", request, bundle=bundle, goal_status=_goal_stoplight(bundle.summary))

    return app


def _snapshot_at(bundle: Any, turn: int | None) -> dict[str, Any] | None:
    if turn is None:
        if bundle.snapshots:
            return bundle.snapshots[-1].world
        return {}
    for s in reversed(bundle.snapshots):
        if s.turn <= turn:
            return s.world
    return bundle.snapshots[0].world if bundle.snapshots else {}


def _goal_stoplight(summary: dict[str, Any]) -> str:
    if summary.get("aborted_stress"):
        return "fail"
    if summary.get("goal_met"):
        return "ok"
    return "warn"
