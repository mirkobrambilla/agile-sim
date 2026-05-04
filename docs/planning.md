# Planning

Living planning notes for `agile-sim`. Tracks current status against
[`concept.md`](concept.md), [`requirements.md`](requirements.md),
[`architecture.md`](architecture.md), [`agentic-design.md`](agentic-design.md),
[`simulation-model.md`](simulation-model.md), and [`ui-design.md`](ui-design.md).

Update this file when items move (status changes, decisions taken, new evidence).

## Status today

Headless harness plus a **web UI with both read-only replay and live, human-in-the-loop runs** (`harness/web`, `agile-harness serve`). The home page is a **run list** (picker): batches and standalone runs, newest first, with scenario label and UTC mtime; links open the experiment page or mission control. The experiments table remains at `/experiments`. Scenarios are browsable at `/scenarios` and `/scenarios/{slug}` with a **Make a copy** action and an in-app editor at `/scenarios/{slug}/edit`; live runs start from `/new`. CLI `agile-harness view` and runner URLs resolve batch/run slugs by exact name, unique prefix, or return an error that lists ambiguous matches (`harness/web/resolve.py`).

Live mode (`harness/web/run_session.py`) keeps a `RunSession` per active run: advance one turn at a time (`/runs/{id}/advance`), stream progress over SSE (`/events`), cancel mid-turn, post into channels as the coach, nudge a vital or scenario parameter (effective N+1), and write a coach reflection. Sessions persist to disk and rebuild from `meta.yaml` + last snapshot on app restart.

**Design docs:** foundations pass completed — process invocation allowlist (v1), best-practices merge rules, coach actor modes, DM as first-class channel, `require_done_ids` in requirements, and UI stoplight detail for outcome ids are reflected in `docs/*.md`.

| Plan area | Status | Notes |
|---|---|---|
| Scenario folder format (YAML + markdown) | done | `harness/scenario.py`, three scenarios in `scenarios/` |
| Scenario browse / view / copy (web) | done | `/scenarios`, `/scenarios/{slug}`, `POST /scenarios/{slug}/copy`, `POST /scenarios/{slug}/copy_and_edit` (`/fork` alias retained) |
| Scenario edit (web) | done | `/scenarios/{slug}/edit` with section navigation, setting markdown editor, character inspector, channel/team/work-item forms, goals + parameters editors, and YAML editors for process + best-practices |
| World ledger (work, vitals, msgs, teams) | partial | `harness/world.py`; no `PersonTurnRecord`, no relationships |
| Process engine (`consult` / `invoke` / `tick` / …) | partial | `harness/engine.py` logs allowlisted `process_invocations` to timeline; vocabulary documented in `architecture.md` / `requirements.md` F-PE2; ledger mutation still shallow; no validation, queueing, scheduler, or `edit` |
| Per-turn agent loop (single structured call) | done | `harness/agent.py` + Pydantic schemas |
| Coach loop with DM + team channel (autonomous) | done | `dm/<id>` + scenario channel; leadership-oriented system prompt |
| Channel `coach_engagement` (`post` / `read` / `none`) | done | Enforced in `harness/world.can_post` / `runner.apply_*`; `post_rejected` on timeline |
| Async messaging (mentions / threads / reactions) | partial | Channels work; `@mentions` parsed, surfaced in agent inbox as guaranteed delivery, and rendered as DM links in the channel view (F-CM5); threaded replies and reactions still not modelled |
| Click avatar → DM (F-CM14) | done | Avatars in channel view, roster, and vitals rail link to `dm/<id>` |
| Event channels + narrator pass | not built | One async channel + DMs only |
| Vitals & metrics with deterministic rules | partial | Self-report deltas, clamping, nudges, derived `delivery_progress` and `happiness`; no engine rules (e.g. overload→stress); no scenario-level vital definition overrides |
| Goals / exit conditions on vitals | done | Added `require_done_ids` for outcome-based wins |
| Best-practices library | done | Used in coach prompt and judge prompt |
| Replay (`timeline.jsonl` + snapshots) | done | All artifacts produced per run; turn-scrubber via `/at/<turn>` |
| Cost / usage tracking | done | `summary.json.totals` and `llm_calls.jsonl`; topbar chip + dev panel |
| Batch runner + matrix | done | `harness/batch.py` |
| End-of-run analysis (`report.md`, `judge_report.md`, `comparison.md`) | done | `harness/analyse.py`, `judge.py`, `pipeline.py` |
| End-of-sim summary view (F26) | partial | Outcome stoplight, character-arc cards, metric sparklines, reflection text are in the summary partial; **missing**: coaching-moment cards with helpful/mixed/harmful/neutral impact tags + best-practice-keyed alternatives, in-app full-screen Final Report with `.md` download |
| Web UI mission control (read mode) | done | FastAPI + Jinja + HTMX + Alpine; topbar, channels rail, kanban, roster, timeline, summary, vitals rail, inspector drawer; see `docs/web-conventions.md` |
| Live runs from the UI (start, advance, SSE, restore) | done | `/new`, `POST /runs`, `/runs/{id}/advance`, `/events`, `/cancel`; resumes after app restart via `RunSession.from_run_dir` |
| Coach actions in live mode (between turns) | partial | Channel post (`/coach/post`), vital nudge and parameter edit (`/edit/vital`, `/edit/parameter`), reflection (`/reflection`), skip-and-advance; scenario editor now applies lock semantics + `coach_edit` timeline rows for editable mid-run fields; **missing entirely**: event injection (F18), engine-rule edits (F19/F-PE7) |
| "Start new live run" CTA on home picker | not built | `/new` only reachable from inside the runner shell or by URL |
| Judge scores in `results.json` | done | Parsed from `judge_report.md` sections; `mean_judge_score` per variant and batch |
| Experiment judge default | done | `--judge auto`/`on`/`off` and `--no-judge`; auto when manifest run count ≤ `EXPERIMENT_AUTO_JUDGE_LIMIT` (default 12) |
| Hard USD cost caps (per run / per matrix) | deferred | Not implemented; tracking remains in summaries only |
| Sprite / expression system | partial | Deterministic vitals→expression mapping in `harness/web/sprites.py`; `assets/manifest.yaml` + `harness/assets.py` generator pipeline; renders in roster, channel headers, summary arcs; per-character set fallbacks via `char_<id>` then `default` |

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
  threads; agents may only post to their own DM. DMs are a **first-class** channel type in the model (`simulation-model.md`, `architecture.md`).
- **Outcome-based goals** via `goals.require_done_ids` co-exist with
  `min_done_work_items` and `per_team_min_done`. When `require_done_ids` is
  set, `min_done_work_items` is ignored for goal evaluation; `per_team_min_done` may still apply (see `requirements.md` F-G1/F-G2).
- **Coach actor** — the same comms/process APIs apply whether the coach is a **human user** (between-turn UI), an **autonomous LLM**, or a **scripted preset** (`author = coach`).
- **Coaching best-practices merge** — global library plus scenario file: scenario entry **replaces** global when `id` matches; new `id`s **append** (`concept.md`, F-BP2).
- **Process invocation allowlist (v1 harness)** — kinds recorded on the timeline: `consult`, `invoke`, `tick`, `request_approval`, `change_deadline`, `edit_ritual`, `set_gate`; other kinds → `process_invocation_unhandled`. Deeper kinds and execution deferred (`architecture.md`, F-PE2).
- **Coachability (v1)** — no separate scalar trait; receptiveness is **emergent** from personality and context (`concept.md`, `agentic-design.md`).
- **Default agent and judge model** is `google/gemini-3-flash-preview`.
- Single LLM call per agent per turn (no tool-calling loop) stays for v1.
- `seed_base` is treated as a label, not a reproducibility guarantee.

## Decisions still open

- Mid-run turn-duration changes — deferred; scenario/fix at start for now (`requirements.md` F11a).
- Hard USD cost cap per run (and per matrix) — deferred; tracking in summaries only.

## Doc updates queued

_Cleared._ Last foundations sync: see `concept.md`, `architecture.md`, `simulation-model.md`, `requirements.md`, `ui-design.md`, `agentic-design.md`.

## Next steps

Ordered roughly by payoff. Single-letter ids match the discussion notes.

### A. Process engine v1 (deeper rules)

Allowlist and logging are **documented**; next implementation work extends `harness/engine.py` beyond timeline recording: validate invocations against scenario rules, maintain pending approvals / ritual queue, mutate ledger for allowed actions. Once `invoke` for one or two kinds (e.g. `change_deadline`, `request_approval`) round-trips end-to-end, `edit` for rule changes (F19/F-PE7) becomes the natural next slice. Update `architecture.md` and `simulation-model.md` as behaviour hardens.

### B. Comms hardening

`@handle` mentions (F-CM5) and click-avatar→DM (F-CM14) are **done**. Mentions are parsed against scenario character ids, force-injected into the mentioned agent's next-turn context regardless of channel volume, and rendered in the channel view as links that open the target's DM. Click-avatar→DM works in the channel view, roster, and vitals rail.

Remaining comms work in this lane: threaded replies (F-CM6), reactions (F-CM12), and ad-hoc channel creation via engine `invoke` (F-CM2).

### C. Event channels + narrator pass

Add the `event` channel type with a lifecycle (open/active/archived), per-member contribution slot in agent output, and a single narrator LLM call per active event channel that renders the transcript and a structured outcome (F-CM7a–c).

### D. Live coach surface — fill the gaps

UI controls for vital nudges (the API endpoint exists but is not wired into a template), event injection (F18, implemented as engine `invoke` with `author = coach`), and engine-rule edits (F19/F-PE7). Add a visible "Start a new live run" CTA on `/`.

### E. End-of-sim summary completeness (F26c/d)

Coaching-moment cards with `helpful`/`mixed`/`harmful`/`neutral` impact tags and best-practice-keyed alternatives; full-screen Final Report doc view with `.md` download.

### F. Ledger gaps

Add `PersonTurnRecord` (capacity / planned / delivered per character per turn) and `Relationship` records. Without `PersonTurnRecord`, deterministic vital rules like "committed > capacity → stress +" cannot fire — so this unblocks F-VM4(a).

### G. Run discovery (done — follow-ups)

Home picker + resolver reduce friction when many batches live under `runs/`. Further work: filters (scenario, date range), search, pinned favourites.

### H. Cost controls (if needed)

Per-run / per-matrix USD caps (not in tree yet).

### I. Sprite / expression system polish

Deterministic mapping and per-character set lookup are in place. Remaining: per-character generated sets in scenarios beyond `default`, wire expressions everywhere a character renders (currently roster / channel header / summary arcs), and surface the per-character sprite set picker in the scenario view.

## Out of scope right now

- Multi-user collaboration.
- Realtime / continuous simulation.
- Mobile-first UI.
- Predictive accuracy claims about real organizations.
