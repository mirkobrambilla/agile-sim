# Planning

Living planning notes for `agile-sim`. Tracks current status against
[`concept.md`](concept.md), [`requirements.md`](requirements.md),
[`architecture.md`](architecture.md), [`agentic-design.md`](agentic-design.md),
[`simulation-model.md`](simulation-model.md), and [`ui-design.md`](ui-design.md).

Update this file when items move (status changes, decisions taken, new evidence).

## Status today

Headless harness plus **read-only web UI** (`harness/web`, `agile-harness serve`).
The home page is a **run list** (picker): batches and standalone runs, newest first, with scenario label and UTC mtime; links open the experiment page or mission control. The experiments table remains at `/experiments`. CLI `agile-harness view` and runner URLs resolve batch/run slugs by exact name, unique prefix, or return an error that lists ambiguous matches (`harness/web/resolve.py`).

| Plan area | Status | Notes |
|---|---|---|
| Scenario folder format (YAML + markdown) | done | `harness/scenario.py`, three scenarios in `scenarios/` |
| World ledger (work, vitals, msgs, teams) | partial | `harness/world.py`; no `PersonTurnRecord`, no relationships |
| Process engine (`consult` / `invoke` / `tick` / …) | partial | `harness/engine.py` logs structured `process_invocations` to timeline; rule execution still minimal (v1 hook) |
| Per-turn agent loop (single structured call) | done | `harness/agent.py` + Pydantic schemas |
| Coach loop with DM + team channel | done | `dm/<id>` + scenario channel; leadership-oriented system prompt |
| Channel `coach_engagement` (`post` / `read` / `none`) | done | Enforced in `harness/world.can_post` / `runner.apply_*`; `post_rejected` on timeline |
| Async messaging (mentions / threads / reactions) | partial | Channels work; `@mentions`, threads, reactions not modelled |
| Event channels + narrator pass | not built | One async channel + DMs only |
| Vitals & metrics with deterministic rules | partial | Self-report deltas, clamping, nudges, derived `delivery_progress` and `happiness`; no engine rules (e.g. overload→stress) |
| Goals / exit conditions on vitals | done | Added `require_done_ids` for outcome-based wins |
| Best-practices library | done | Used in coach prompt and judge prompt |
| Replay (`timeline.jsonl` + snapshots) | done | All artifacts produced per run |
| Cost / usage tracking | done | `summary.json.totals` and `llm_calls.jsonl` |
| Batch runner + matrix | done | `harness/batch.py` |
| End-of-run analysis (`report.md`, `judge_report.md`, `comparison.md`) | done | `harness/analyse.py`, `judge.py`, `pipeline.py` |
| Web UI (mission control, experiments) | partial | FastAPI + Jinja + HTMX + Alpine; home run picker + experiments index + nested batch routes; see `docs/web-conventions.md` — read-only |
| Judge scores in `results.json` | done | Parsed from `judge_report.md` sections; `mean_judge_score` per variant and batch |
| Experiment judge default | done | `--judge auto|on|off` and `--no-judge`; auto when manifest run count ≤ `EXPERIMENT_AUTO_JUDGE_LIMIT` (default 12) |
| Hard USD cost caps (per run / per matrix) | deferred | Not implemented; tracking remains in summaries only |
| Sprite/expression system | not started | Deterministic mapping possible from current vitals |
| Coaching during a run (human-in-the-loop, between turns) | not built | Current "coach" is an autonomous LLM; the user is a scenario/experiment author |

## Insights from runs so far

Evidence comes from `runs/batch_20260501T174001Z` (priority-conflict scenario,
n = 10 per variant).

- Coaching the **system** (priorities, retro norms) instead of the **tickets** changed
  outcomes: `llm_coach` reached the goal **10/10** with **0** stress aborts;
  `no_coach` reached it **6/10** with **40%** stress aborts. Same agent model and
  seeds.
- The coach used both `dm/lia` (rehearsing the ask) and `#eng-pilot` (framing,
  norms) as designed.
- Outcome-based goals (`require_done_ids: [O1, O2]`) prevent "winning" by
  burning down delivery noise (D1/D2). Without that, the earlier matrix taught
  the coach a scrum-master pattern that backfired.
- Coach mode roughly **+1.7×** input tokens (51k vs 29k mean). Mechanism: one
  extra LLM call per turn + slightly longer runs; no hidden context injection.
- `work_done` is the wrong success metric for leadership scenarios. The
  judgement now sits in `goal_met` plus the targeted outcome items.

## Decisions taken

- **DM channel convention `dm/<character_id>`** for private coach<->person
  threads; agents may only post to their own DM.
- **Outcome-based goals** via `goals.require_done_ids` co-exist with
  `min_done_work_items` and `per_team_min_done`. When `require_done_ids` is
  set, `min_done_work_items` is ignored.
- **Default agent and judge model** is `google/gemini-3-flash-preview`.
- Single LLM call per agent per turn (no tool-calling loop) stays for v1.
- `seed_base` is treated as a label, not a reproducibility guarantee.

## Decisions still open

- Process engine v1 vocabulary and minimum rule set.
- Coachability as an explicit per-character trait vs emergent from personality.
- Mid-run turn-duration changes (likely fine to defer).
- Scenario `best_practices.yaml` precedence vs a global file.
- Hard cost cap per run (and per matrix) before the web UI lands (**deferred**).

## Doc updates queued

These follow from the decisions above and from running real experiments.

- `concept.md` and `architecture.md`: state that the **coach can be a human
  user, an autonomous LLM, or a scripted preset** — all use the same channel
  APIs with `author = coach`.
- `simulation-model.md` and `architecture.md`: add **DM (`dm/<id>`) as a
  first-class channel type** for the coach<->person thread.
- `requirements.md`: add `goals.require_done_ids` next to `min_done_work_items`
  and `per_team_min_done`.
- `ui-design.md`: goal stoplight should render **specific outcome work items**
  (e.g. O1, O2), not only counts — web UI still uses summary stoplight only.

## Next steps

Ordered roughly by payoff. Single-letter ids match the discussion notes.

### A. Process engine v1 (deeper rules)

Extend `harness/engine.py` beyond timeline logging: roles, gates, deadlines, rituals.
Update `architecture.md` and `simulation-model.md` as behaviour hardens.

### B. Engagement and channels (follow-on)

More than one autonomous coach; membership matrices; richer channel types.

### C–D. Web UI (follow-on)

Live runs, editing, sprite system; polish mission control per `ui-design.md`. **Done for discoverability:** flat run list on `/`, slug resolution for `view` / deep links.

### C′. Run discovery (done)

Home picker + resolver reduce friction when many batches live under `runs/`. Further work: filters (scenario, date range), search, pinned favourites.

### E. Cost controls (if needed)

Per-run / per-matrix USD caps (not in tree yet).

### F. Standard library for vitals + expressions

Small rule table so the UI can render expressions before the sprite system exists.

## Out of scope right now

- Multi-user collaboration.
- Realtime / continuous simulation.
- Mobile-first UI.
- Predictive accuracy claims about real organizations.
