"""FastAPI app: read-only mission control + experiments."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from jinja2 import Environment, FileSystemLoader, select_autoescape

from harness.analyse import batch_metrics, load_meta
from harness.runner import load_api_key
from harness.web.render import md_to_html
from harness.web.resolve import (
    ResolvedBatch,
    ResolvedRun,
    resolve_slug_under_runs,
    run_url_path,
)
from harness.web.run_reader import (
    agent_narrative_snippets,
    build_picker_entries,
    channel_meta_for,
    list_batches,
    list_runs,
    load_run,
    recent_posts_for_character,
    scenario_from_bundle_meta,
    svg_sparkline,
    vitals_history_for_character,
    work_item_timeline_events,
)
from harness.web.run_session import SESSIONS, RunSession


def _runs_dir_kw(runs_dir: Path | None) -> Path:
    if runs_dir is not None:
        return runs_dir.resolve()
    return Path(os.environ.get("AGILE_SIM_RUNS_DIR", "runs")).resolve()


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _safe_scenario_dir(repo: Path, slug: str) -> Path:
    base = (repo / "scenarios").resolve()
    cand = (base / slug.strip()).resolve()
    try:
        cand.relative_to(base)
    except ValueError as err:
        raise HTTPException(status_code=400, detail="invalid scenario path") from err
    if not cand.is_dir() or not (cand / "scenario.yaml").is_file():
        raise HTTPException(status_code=404, detail="scenario not found")
    return cand


def _list_scenario_slugs(repo: Path) -> list[dict[str, str]]:
    root = repo / "scenarios"
    if not root.is_dir():
        return []
    rows: list[dict[str, str]] = []
    for p in sorted(root.iterdir()):
        if p.is_dir() and (p / "scenario.yaml").is_file():
            rows.append({"slug": p.name, "id": p.name})
    return rows


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


def _runner_ctx(
    bundle: Any,
    snap_world: dict[str, Any] | None,
    goal_status: str,
    eff_turn: int,
    max_turn: int,
) -> dict[str, Any]:
    from harness.web.sprites import character_meta_by_id, expression_from_vitals, sprite_url

    scen = scenario_from_bundle_meta(bundle.meta)
    char_meta = character_meta_by_id(scen)
    snap = snap_world or {}
    wis = snap.get("work_items") or []
    by_id = {str(wi.get("id")): wi for wi in wis}
    goals_cfg = scen.get("goals") or {}
    req_ids = list(goals_cfg.get("require_done_ids") or [])
    goal_rows: list[dict[str, Any]] = []
    for rid in req_ids:
        rid_s = str(rid)
        wi = by_id.get(rid_s, {})
        st = str(wi.get("state") or "—").lower()
        sl = "ok" if st == "done" else "warn"
        goal_rows.append(
            {
                "id": rid_s,
                "title": str(wi.get("title") or rid_s),
                "state": st,
                "stoplight": sl,
            }
        )
    live_turn = max(1, int(bundle.summary.get("final_turn") or 0) or 1)
    team_members: dict[str, list[str]] = {}
    for tm in scen.get("teams") or []:
        tid = str(tm.get("id", ""))
        if tid:
            team_members[tid] = [str(x) for x in (tm.get("member_ids") or [])]
    return {
        "char_meta": char_meta,
        "scenario": scen,
        "goal_rows": goal_rows,
        "require_done_ids": req_ids,
        "work_done_count": sum(1 for w in wis if str(w.get("state")).lower() == "done"),
        "work_total": len(wis),
        "live_turn": live_turn,
        "viewing_replay": eff_turn != live_turn,
        "max_turn_ui": max_turn,
        "sprite_set": "default",
        "expression_from_vitals": expression_from_vitals,
        "sprite_url": sprite_url,
        "team_members": team_members,
        "primary_team_channel": bundle.primary_channel,
    }


def _vitals_spark_map(bundle: Any, chars: dict[str, Any]) -> dict[str, dict[str, str]]:
    out: dict[str, dict[str, str]] = {}
    for cid in chars:
        c = str(cid)
        hist_e = [v for _, v in vitals_history_for_character(bundle, c, "energy")]
        hist_m = [v for _, v in vitals_history_for_character(bundle, c, "motivation")]
        hist_s = [v for _, v in vitals_history_for_character(bundle, c, "stress")]
        out[c] = {
            "energy": svg_sparkline(hist_e) if hist_e else "",
            "motivation": svg_sparkline(hist_m) if hist_m else "",
            "stress": svg_sparkline(hist_s) if hist_s else "",
        }
    return out


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

        live_sess: RunSession | None = SESSIONS.get(url_p)
        summ_early = bundle.summary or {}
        if live_sess is None and summ_early.get("live_session"):
            try:
                from harness.integrations.openrouter import OpenRouterClient
                from harness.runner import load_api_key

                live_sess = RunSession.from_run_dir(
                    run_root=r.run_dir,
                    client=OpenRouterClient(api_key=load_api_key(None)),
                )
                if not live_sess.finished:
                    SESSIONS[url_p] = live_sess
                else:
                    live_sess = None
            except (FileNotFoundError, OSError, ValueError, TypeError):
                live_sess = None

        active_live = live_sess is not None and not live_sess.finished

        if active_live:
            assert live_sess is not None
            max_turn = max(1, int(live_sess.world.max_turns))
            head_turn = (
                max(1, live_sess.last_completed_turn) if live_sess.last_completed_turn else 1
            )
            eff_turn = head_turn if turn is None else int(turn)
            eff_turn = max(1, min(eff_turn, max_turn, head_turn))
            snap_world = _snapshot_at(bundle, eff_turn)
            if not snap_world and live_sess.last_completed_turn == 0:
                snap_world = live_sess.world.snapshot()
            elif not snap_world:
                snap_world = live_sess.world.snapshot()
            goal_status = _goal_stoplight(bundle.summary)
            rc = _runner_ctx(bundle, snap_world, goal_status, eff_turn, max_turn)
            rc["live_turn"] = head_turn
            rc["viewing_replay"] = eff_turn != head_turn
            ctx = {
                "bundle": bundle,
                "effective_turn": eff_turn,
                "max_turn": max_turn,
                "snap_world": snap_world,
                "goal_status": goal_status,
                "channel_query": request.query_params.get("channel", bundle.primary_channel),
                "vitals_sparks": _vitals_spark_map(
                    bundle, (snap_world or {}).get("characters") or {}
                ),
                **rc,
                "live_session": True,
                "session_coach_mode": live_sess.coach_mode,
                "run_url_path": url_p,
            }
        elif live_sess is not None and live_sess.finished:
            eff_turn = turn
            if eff_turn is None:
                eff_turn = int(bundle.summary.get("final_turn") or 0) or 1
            snap_world = _snapshot_at(bundle, eff_turn)
            goal_status = _goal_stoplight(bundle.summary)
            max_turn = max(1, int(bundle.summary.get("final_turn") or 0) or 1)
            ctx = {
                "bundle": bundle,
                "effective_turn": eff_turn,
                "max_turn": max_turn,
                "snap_world": snap_world,
                "goal_status": goal_status,
                "channel_query": request.query_params.get("channel", bundle.primary_channel),
                "vitals_sparks": _vitals_spark_map(
                    bundle, (snap_world or {}).get("characters") or {}
                ),
                **_runner_ctx(bundle, snap_world, goal_status, eff_turn, max_turn),
                "live_session": False,
                "session_coach_mode": live_sess.coach_mode,
                "run_url_path": url_p,
            }
        else:
            eff_turn = turn
            if eff_turn is None:
                eff_turn = int(bundle.summary.get("final_turn") or 0) or 1
            snap_world = _snapshot_at(bundle, eff_turn)
            goal_status = _goal_stoplight(bundle.summary)
            max_turn = max(1, int(bundle.summary.get("final_turn") or 0) or 1)
            ctx = {
                "bundle": bundle,
                "effective_turn": eff_turn,
                "max_turn": max_turn,
                "snap_world": snap_world,
                "goal_status": goal_status,
                "channel_query": request.query_params.get("channel", bundle.primary_channel),
                "vitals_sparks": _vitals_spark_map(
                    bundle, (snap_world or {}).get("characters") or {}
                ),
                **_runner_ctx(bundle, snap_world, goal_status, eff_turn, max_turn),
                "live_session": False,
                "session_coach_mode": (bundle.meta or {}).get("coach_mode") or "",
                "run_url_path": url_p,
            }
        return render("runner.html", request, **ctx)

    @app.get("/new", response_class=HTMLResponse)
    async def new_run_form(request: Request) -> HTMLResponse:
        repo = _repo_root()
        return render(
            "new_run.html",
            request,
            scenarios=_list_scenario_slugs(repo),
            runs_dir=str(runs_dir),
        )

    @app.post("/runs")
    async def start_live_run(
        request: Request,
        scenario_slug: str = Form(...),
        agent_model: str = Form("stub"),
        coach_model: str = Form(""),
        coach_mode: str = Form("llm"),
    ) -> RedirectResponse:
        repo = _repo_root()
        scen = _safe_scenario_dir(repo, scenario_slug)
        try:
            from harness.integrations.openrouter import OpenRouterClient

            client = OpenRouterClient(api_key=load_api_key(None))
        except (FileNotFoundError, ValueError, OSError) as err:
            raise HTTPException(
                status_code=500,
                detail="Need secrets.yaml with openrouter_api_key to start a live run.",
            ) from err
        cm = coach_model.strip() or None
        sess = RunSession.start(
            scenario_dir=scen,
            runs_dir=runs_dir,
            agent_model=agent_model.strip() or "stub",
            coach_model=cm,
            coach_mode_cli=coach_mode.strip().lower(),
            coach_preset_cli=None,
            secrets=None,
            client=client,
            seed=None,
        )
        url_p = run_url_path(runs_dir=runs_dir, run_dir=sess.run_root)
        SESSIONS[url_p] = sess
        return RedirectResponse(url=f"/runs/{url_p}", status_code=303)

    @app.post("/runs/{run_path:path}/advance", response_class=HTMLResponse)
    async def live_advance(request: Request, run_path: str) -> HTMLResponse:
        r = _require_resolved_run(run_path)
        url_p = run_url_path(runs_dir=runs_dir, run_dir=r.run_dir)
        sess = SESSIONS.get(url_p)
        if sess is None:
            raise HTTPException(status_code=404, detail="no active live session")
        await sess.advance()
        bundle = load_run(run_dir=r.run_dir, url_path=url_p)
        channel = bundle.primary_channel
        live_sess = SESSIONS.get(url_p)
        active = live_sess is not None and not live_sess.finished
        head_turn = (
            max(1, live_sess.last_completed_turn) if live_sess and live_sess.last_completed_turn else 1
        )
        if live_sess and live_sess.last_completed_turn == 0:
            head_turn = 1
        max_t = live_sess.world.max_turns if live_sess else 1
        snap = _snapshot_at(bundle, head_turn) or (
            live_sess.world.snapshot()
            if live_sess and live_sess.last_completed_turn == 0
            else {}
        )
        gs = _goal_stoplight(bundle.summary)
        rc = _runner_ctx(bundle, snap, gs, head_turn, max_t)
        sparks = _vitals_spark_map(bundle, (snap or {}).get("characters") or {})
        goals_html = jinja.get_template("partials/goals_panel.html").render(
            request=request,
            bundle=bundle,
            **rc,
            goal_status=gs,
            effective_turn=head_turn,
        )
        vitals_html = jinja.get_template("partials/vitals_rail.html").render(
            request=request,
            bundle=bundle,
            **rc,
            characters=(snap or {}).get("characters") or {},
            effective_turn=head_turn,
            vitals_sparks=sparks,
        )
        msgs = bundle.messages_by_channel.get(channel, [])
        channel_html = jinja.get_template("partials/channel_view.html").render(
            request=request,
            bundle=bundle,
            **rc,
            channel=channel,
            messages=msgs,
            effective_turn=head_turn,
            snap_world=snap,
            live_session=active,
            session_coach_mode=live_sess.coach_mode if live_sess else "",
        )
        oob = (
            f'<div id="goals-panel" hx-swap-oob="true">{goals_html}</div>'
            f'<div id="vitals-rail" hx-swap-oob="true">{vitals_html}</div>'
            f'<div id="center-stage" hx-swap-oob="true">{channel_html}</div>'
        )
        return HTMLResponse(oob)

    @app.post("/runs/{run_path:path}/coach/post", response_class=HTMLResponse)
    async def live_coach_post(
        request: Request,
        run_path: str,
        channel: str = Form(...),
        content: str = Form(...),
    ) -> HTMLResponse:
        r = _require_resolved_run(run_path)
        url_p = run_url_path(runs_dir=runs_dir, run_dir=r.run_dir)
        sess = SESSIONS.get(url_p)
        if sess is None or sess.finished:
            raise HTTPException(status_code=400, detail="no active live session")
        if sess.coach_mode != "human":
            raise HTTPException(status_code=400, detail="coach post only when coach_mode=human")
        sess.coach_post(channel=channel, content=content, author="coach")
        bundle = load_run(run_dir=r.run_dir, url_path=url_p)
        ch = channel.strip() or bundle.primary_channel
        head_turn = max(1, sess.last_completed_turn) if sess.last_completed_turn else 1
        max_t = sess.world.max_turns
        snap = _snapshot_at(bundle, head_turn) or sess.world.snapshot()
        gs = _goal_stoplight(bundle.summary)
        rc = _runner_ctx(bundle, snap, gs, head_turn, max_t)
        msgs = bundle.messages_by_channel.get(ch, [])
        channel_html = jinja.get_template("partials/channel_view.html").render(
            request=request,
            bundle=bundle,
            **rc,
            channel=ch,
            messages=msgs,
            effective_turn=head_turn,
            snap_world=snap,
            live_session=True,
            session_coach_mode=sess.coach_mode,
        )
        return HTMLResponse(channel_html)

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
        eff = turn if turn is not None else max(1, int(bundle.summary.get("final_turn") or 0) or 1)
        max_t = max(1, int(bundle.summary.get("final_turn") or 0) or 1)
        gs = _goal_stoplight(bundle.summary)
        rc = _runner_ctx(bundle, world, gs, eff, max_t)
        ctx = {**rc, "bundle": bundle, "columns": cols, "effective_turn": eff, "snap_world": world}
        return render("partials/kanban.html", request, **ctx)

    @app.get("/partials/run/{run_path:path}/timeline", response_class=HTMLResponse)
    async def partial_timeline(request: Request, run_path: str) -> HTMLResponse:
        r = _require_resolved_run(run_path)
        bundle = load_run(run_dir=r.run_dir, url_path=run_url_path(runs_dir=runs_dir, run_dir=r.run_dir))
        turn_s = request.query_params.get("turn")
        turn = int(turn_s) if turn_s and turn_s.isdigit() else None
        eff = turn if turn is not None else max(1, int(bundle.summary.get("final_turn") or 0) or 1)
        turn_ticks = sorted(
            {
                int(row.raw["turn"])
                for row in bundle.timeline
                if row.kind == "turn_start" and row.raw.get("turn") is not None
            }
        )
        return render(
            "partials/timeline.html",
            request,
            bundle=bundle,
            url_path=run_url_path(runs_dir=runs_dir, run_dir=r.run_dir),
            turn_ticks=turn_ticks,
            effective_turn=eff,
        )

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
        eff = turn if turn is not None else max(1, int(bundle.summary.get("final_turn") or 0) or 1)
        max_t = max(1, int(bundle.summary.get("final_turn") or 0) or 1)
        gs = _goal_stoplight(bundle.summary)
        rc = _runner_ctx(bundle, world, gs, eff, max_t)
        sparks = _vitals_spark_map(bundle, chars)
        ctx = {**rc, "bundle": bundle, "characters": chars, "effective_turn": eff, "vitals_sparks": sparks}
        return render("partials/vitals_rail.html", request, **ctx)

    @app.get("/partials/run/{run_path:path}/goals", response_class=HTMLResponse)
    async def partial_goals(request: Request, run_path: str) -> HTMLResponse:
        r = _require_resolved_run(run_path)
        bundle = load_run(run_dir=r.run_dir, url_path=run_url_path(runs_dir=runs_dir, run_dir=r.run_dir))
        turn_s = request.query_params.get("turn")
        turn = int(turn_s) if turn_s and turn_s.isdigit() else None
        world = _snapshot_at(bundle, turn) or {}
        eff = turn if turn is not None else max(1, int(bundle.summary.get("final_turn") or 0) or 1)
        max_t = max(1, int(bundle.summary.get("final_turn") or 0) or 1)
        gs = _goal_stoplight(bundle.summary)
        rc = _runner_ctx(bundle, world, gs, eff, max_t)
        ctx = {**rc, "bundle": bundle, "goal_status": gs, "effective_turn": eff}
        return render("partials/goals_panel.html", request, **ctx)

    @app.get("/partials/run/{run_path:path}/roster", response_class=HTMLResponse)
    async def partial_roster(request: Request, run_path: str) -> HTMLResponse:
        turn_s = request.query_params.get("turn")
        turn = int(turn_s) if turn_s and turn_s.isdigit() else None
        r = _require_resolved_run(run_path)
        bundle = load_run(run_dir=r.run_dir, url_path=run_url_path(runs_dir=runs_dir, run_dir=r.run_dir))
        world = _snapshot_at(bundle, turn) or {}
        chars = world.get("characters") or {}
        eff = turn if turn is not None else max(1, int(bundle.summary.get("final_turn") or 0) or 1)
        max_t = max(1, int(bundle.summary.get("final_turn") or 0) or 1)
        gs = _goal_stoplight(bundle.summary)
        rc = _runner_ctx(bundle, world, gs, eff, max_t)
        sparks = _vitals_spark_map(bundle, chars)
        ctx = {
            **rc,
            "bundle": bundle,
            "characters": chars,
            "effective_turn": eff,
            "vitals_sparks": sparks,
        }
        return render("partials/roster.html", request, **ctx)

    @app.get(
        "/partials/run/{run_path:path}/inspector/character/{cid}",
        response_class=HTMLResponse,
    )
    async def partial_inspector_character(request: Request, run_path: str, cid: str) -> HTMLResponse:
        turn_s = request.query_params.get("turn")
        turn = int(turn_s) if turn_s and turn_s.isdigit() else None
        r = _require_resolved_run(run_path)
        bundle = load_run(run_dir=r.run_dir, url_path=run_url_path(runs_dir=runs_dir, run_dir=r.run_dir))
        world = _snapshot_at(bundle, turn) or {}
        eff = turn if turn is not None else max(1, int(bundle.summary.get("final_turn") or 0) or 1)
        max_t = max(1, int(bundle.summary.get("final_turn") or 0) or 1)
        gs = _goal_stoplight(bundle.summary)
        rc = _runner_ctx(bundle, world, gs, eff, max_t)
        ch = (world.get("characters") or {}).get(cid, {})
        narr = agent_narrative_snippets(bundle, cid)
        posts = recent_posts_for_character(bundle, cid)
        ctx = {
            **rc,
            "bundle": bundle,
            "inspect_cid": cid,
            "inspect_character": ch,
            "inspect_narratives": narr,
            "inspect_recent_posts": posts,
            "effective_turn": eff,
        }
        return render("partials/inspector_character.html", request, **ctx)

    @app.get(
        "/partials/run/{run_path:path}/inspector/work_item/{wid}",
        response_class=HTMLResponse,
    )
    async def partial_inspector_work_item(request: Request, run_path: str, wid: str) -> HTMLResponse:
        turn_s = request.query_params.get("turn")
        turn = int(turn_s) if turn_s and turn_s.isdigit() else None
        r = _require_resolved_run(run_path)
        bundle = load_run(run_dir=r.run_dir, url_path=run_url_path(runs_dir=runs_dir, run_dir=r.run_dir))
        world = _snapshot_at(bundle, turn) or {}
        eff = turn if turn is not None else max(1, int(bundle.summary.get("final_turn") or 0) or 1)
        max_t = max(1, int(bundle.summary.get("final_turn") or 0) or 1)
        gs = _goal_stoplight(bundle.summary)
        rc = _runner_ctx(bundle, world, gs, eff, max_t)
        wi = None
        for w in world.get("work_items") or []:
            if str(w.get("id")) == str(wid):
                wi = w
                break
        ev = work_item_timeline_events(bundle, wid)
        ctx = {
            **rc,
            "bundle": bundle,
            "inspect_wi": wi,
            "inspect_wi_id": wid,
            "inspect_wi_events": ev,
            "effective_turn": eff,
        }
        return render("partials/inspector_work_item.html", request, **ctx)

    @app.get("/partials/run/{run_path:path}/inspector/channel", response_class=HTMLResponse)
    async def partial_inspector_channel(request: Request, run_path: str) -> HTMLResponse:
        ch = request.query_params.get("channel", "")
        turn_s = request.query_params.get("turn")
        turn = int(turn_s) if turn_s and turn_s.isdigit() else None
        r = _require_resolved_run(run_path)
        bundle = load_run(run_dir=r.run_dir, url_path=run_url_path(runs_dir=runs_dir, run_dir=r.run_dir))
        world = _snapshot_at(bundle, turn) or {}
        eff = turn if turn is not None else max(1, int(bundle.summary.get("final_turn") or 0) or 1)
        max_t = max(1, int(bundle.summary.get("final_turn") or 0) or 1)
        gs = _goal_stoplight(bundle.summary)
        rc = _runner_ctx(bundle, world, gs, eff, max_t)
        scen = rc.get("scenario") or {}
        meta = channel_meta_for(bundle, ch, scen)
        ctx = {**rc, "bundle": bundle, "inspect_channel": ch, "channel_inspector_meta": meta, "effective_turn": eff}
        return render("partials/inspector_channel.html", request, **ctx)

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
        eff = turn if turn is not None else max(1, int(bundle.summary.get("final_turn") or 0) or 1)
        max_t = max(1, int(bundle.summary.get("final_turn") or 0) or 1)
        snap = _snapshot_at(bundle, turn) or {}
        gs = _goal_stoplight(bundle.summary)
        rc = _runner_ctx(bundle, snap, gs, eff, max_t)
        url_px = run_url_path(runs_dir=runs_dir, run_dir=r.run_dir)
        ls = SESSIONS.get(url_px)
        active_live = ls is not None and not ls.finished
        ctx = {
            **rc,
            "bundle": bundle,
            "channel": ch,
            "messages": msgs,
            "effective_turn": eff,
            "snap_world": snap,
            "live_session": active_live,
            "session_coach_mode": ls.coach_mode if ls else "",
        }
        return render("partials/channel_view.html", request, **ctx)

    return app
