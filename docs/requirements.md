# Requirements (draft)

This is a first pass. Items marked _(open)_ are placeholders pending a decision in [`concept.md`](concept.md) → "Open questions".

## Functional

### Scenarios

- F1. Users can browse a library of scenarios.
- F2. Users can create a new scenario from scratch or by forking an existing one.
- F3. A scenario captures: setting, process, roles, characters, entities (teams/company/process/external), initial conditions, goal, exit conditions, parameters.
- F4. Scenarios are persisted in a structured, human-readable format _(open: YAML vs JSON vs DB-only)_.
- F5. Scenarios can be edited freely until the first turn of a run is taken.
- F5a. Once a run has started, **initial / start conditions are immutable** for that run (initial world state, starting vitals, character core profiles used to seed turn 0). The UI shows these as locked. Other fields (process rules, parameters, channel membership, vital nudges) remain editable mid-run and take effect on the next turn.

### Agents (characters)

- F6. Each character in a scenario is backed by an agent with a stable identity within a run. Agents represent simulated people only; teams and the company are structural entries on the world ledger, not agents.
- F7. An agent maintains: profile (personality, skills, goals, relationships), private memory, and a current internal view of the situation.
- F8. Agents act through OpenRouter-hosted models. The model used per agent is configurable.
- F9. Agents can produce per turn, in a single LLM call: a narrative of what they did, statements/actions, async posts to persistent channels, process invocations, bounded self-reports on their own vitals, and one conversation contribution (intent / state / desired outcome) per active event channel they are a member of. Agents do not write the world ledger directly.

### Simulation runner

- F10. A run advances one turn at a time, on user command.
- F11. Each turn produces a recorded set of agent outputs and a resulting world state delta.
- F11a. A scenario declares its turn duration in in-fiction time (e.g. half-day, day, week, sprint, month). The runner is agnostic to the unit; capacity, ritual cadence, and deadlines are expressed in it. Turn duration is fixed at scenario start in v1.
- F12. The user can pause indefinitely between turns. There is no wall-clock pressure.
- F13. A run ends automatically when a defined goal is reached or any exit condition fires. The user can also end a run manually.
- F-G1. Scenario `goals` may include **`require_done_ids`**: a list of work-item **ids** that must all be in the `done` state before the goal is considered met (outcome-based success).
- F-G2. Scenario `goals` may include **`min_done_work_items`** (minimum count of done work items) and **`per_team_min_done`** (each non-empty team must have at least this many done items owned by a member). **Precedence:** when `require_done_ids` is non-empty, **`min_done_work_items` is not used** in goal evaluation (outcome ids are authoritative for the volume check). **`per_team_min_done` still applies** when set, after `require_done_ids` is satisfied. Stress caps (`max_stress_any`, etc.) apply regardless.

### Simulation fidelity

See [`simulation-model.md`](simulation-model.md) for the rationale.

- F-SF1. The world ledger holds structured state: work items, per-person turn records (capacity, planned commitments, delivered work), teams, relationships, vitals, metrics, and message history. The process engine writes to the ledger; agents read it via context-building and via engine `consult`.
- F-SF2. Agent outputs anchor to ledger entities. Agents may misinterpret ledger state, but they do not create new ledger entities directly — new work items, commitments, and approvals go through the engine via `invoke`.
- F-SF3. The coach can ask any agent for more detail about something the agent narrated ("walk me through the standup"). v1 does not have a separate "scene" mechanism — chat-on-demand covers it.

### Communication channels

- F-CM1. Channels are defined by the scenario. Supported types: **DM**, **group** (persistent), **open** (org-wide), and **event** (bound to a process event with a lifecycle: opened, active, archived).
- F-CM2. Agents may request creation of a new channel during a run only via `invoke` against the process engine; the engine decides whether to allow it based on scenario rules.
- F-CM3. Event channels are opened and closed by the process engine in response to scheduled or triggered events (e.g. ritual fires, incident declared). Membership for event channels is defined by the event.
- F-CM4. Each channel has a membership list. Agents only see messages in channels they are members of.
- F-CM5. Each agent has a display name and a handle. Messages support `@handle` mentions. A mention guarantees the message reaches the mentioned agent's next-turn context regardless of channel volume.
- F-CM6. During a turn, an agent may post zero or more messages to persistent channels (DM / group / open) it is a member of. Messages support threaded replies.
- F-CM7. Posts in persistent channels are delivered asynchronously: a message posted on turn N appears in recipients' context on turn N+1.
- F-CM7a. Conversations in event channels are **narrated within the same turn**. Each member of an active event channel contributes intent, current state, and desired outcome as part of their normal per-turn output. After all agents have run, the comms narrator renders the conversation as an ordered transcript (one LLM call per active event channel) and produces a structured outcome record. The transcript is posted to the channel; the structured outcome is applied to the ledger by the engine.
- F-CM7b. Narrated transcripts are visible to participants the same turn; non-participants see the messages on turn N+1 like any other.
- F-CM7c. The narrator should render disagreement honestly when participants' desired outcomes conflict, and reflect lack of resolution in the structured outcome.
- F-CM8. The coach is a participant in the comms layer. Per-channel **coach engagement mode** is declared by the scenario: `post` (read and post), `read` (observe only), or `none` (hidden from the coach).
- F-CM9. The coach's existing 1:1 chats with agents are implemented as scenario-defined DM channels with `post` engagement.
- F-CM10. The visibility taxonomy for coaching actions (private / observable / broadcast) is realized via channel choice: DM = private; group with bystanders = observable; open channel = broadcast.
- F-CM11. All messages, channel lifecycle events (open / close), membership changes, and message reactions are recorded on the run timeline and visible in the replay viewer.
- F-CM12. Messages support a small fixed set of emoji **reactions** (heart, thumbs-up, thinking, awkward, eyes, celebration). The coach reacts via the UI; agents may include up to two reactions per turn in their structured output.
- F-CM13. The coach posts in channels by typing in the channel's own input box (like any other member). There is no separate composer panel.
- F-CM14. Clicking a character avatar anywhere in the UI opens that character's DM channel. If the channel does not yet exist and the scenario allows it, comms creates it on first message.

### Character expressions

- F-EX1. Each character ships with a sprite set covering a fixed set of expression states: `idle`, `happy`, `frustrated`, `overloaded`, `bored`, `surprised`, `proud`, `sad`. Sprite source is scenario-defined (standard library or generated).
- F-EX2. The current expression for a character is **derived deterministically** from current vitals and recent context (last turn). No LLM call is involved. The default rule table is part of the standard vitals library; scenarios can override.
- F-EX3. The displayed sprite updates in real time when vitals change.

### Vitals and metrics

Naming convention: **vitals** = per character and per team; **metrics** = per organization. *"Vitals and metrics"* is the umbrella term.

- F-VM1. The world ledger maintains vitals per character and per team, and metrics at the organization level. All values are numeric.
- F-VM2. A **standard library** ships with the app and defines defaults: per-person (energy, motivation, stress), per-team (cohesion, capacity utilization), per-org (delivery progress, employee happiness, productivity, **quality**). "Quality" is the broader default for output health; software-specific scenarios may add or substitute "technical debt". Exact set is configurable; v1 list TBD.
- F-VM3. Scenarios may extend the library or override specific definitions.
- F-VM4. Vitals and metrics update from three sources: (a) deterministic engine rules during `tick`; (b) agent self-reporting at end of turn, bounded to a small per-turn delta; (c) explicit events and coach actions.
- F-VM5. The coach sees true values for all entities at any time.
- F-VM6. Agents know their own vitals approximately and form opinions about other agents' vitals through interaction. Agent prompts include the agent's own vitals; they do not include others'.
- F-VM7. Scenario `goal` and `exit_conditions` may reference vitals and metrics (e.g. "delivery progress = 100% AND avg motivation ≥ 50 AND tech debt ≤ 30"). Each criterion is rendered with **stoplight** status (🟢 on track / 🟡 at risk / 🔴 failing). When the goal is expressed via **`require_done_ids`** (see F-G1), the stoplight and inspector UI should surface **those ids** (and labels from the ledger), not only aggregate counts — so the coach sees which outcome rows (e.g. O1, O2) are still open.
- F-VM8. The runner UI shows current values with per-turn history (sparklines in the right rail, full **time-series graph** on inspection), and flags exit-condition thresholds.
- F-VM9. Per-turn snapshots are recorded on the run timeline.

### Process engine

- F-PE1. Every scenario includes a process engine definition, even if minimal (chaos = a near-empty rule set).
- F-PE2. The engine holds: roles and decision rights, approval gates, scheduled rituals, work-item state machine, and arbitrary named rules. **v1 harness:** agents and coach may emit `process_invocations` in structured output; [`harness/engine.py`](../harness/engine.py) records **allowlisted** kinds on the run timeline as `process_invocation` rows; other kinds emit `process_invocation_unhandled`. Allowlist for v1: `consult`, `invoke`, `tick`, `request_approval`, `change_deadline`, `edit_ritual`, `set_gate`. Execution of rules (validate, queue, ledger mutation) remains shallow until process engine v1 deepens.
- F-PE3. Any agent can issue a **consult** query against the engine ("what's the policy on X?", "do I need approval for Y?", "when is the next ritual?") and receive a deterministic, structured answer.
- F-PE4. Any agent can issue an **invoke** request to take a process-mediated action: escalate a decision, request approval, introduce new work, move a person between teams, change a deadline, schedule/cancel a ritual. The engine validates against rules and either executes, queues, or rejects with a reason.
- F-PE5. The engine emits scheduled events into the world (ritual due, approval pending, deadline approaching) which appear in the next turn's per-agent context.
- F-PE6. A scenario may include a **process steward** agent (PMO / delivery / scrum master function) that operates the engine — runs rituals, surfaces violations, communicates rule changes. Optional per scenario.
- F-PE7. The coach can change engine rules between turns via engine `edit`. Changes are versioned with the run timeline.
- F-PE8. All consults, invokes, and rule changes are recorded on the run timeline.

### Coaching (between-turn interaction)

This is the primary interaction surface. The simulation runs in order to give the user something to coach. Coach actions go through the same APIs agents use, with `author = coach`. The coach is treated as a participant in the comms layer, not a separate operator.

- F14. After every turn, the coach enters a coaching phase before the next turn can run.
- F15. The coach posts in channels by typing in the channel's input box (see F-CM13). DM channels with individual characters are the equivalent of "1:1 coaching chat" and are reached by clicking the character's avatar (see F-CM14).
- F16. The coach can address multiple characters at once by posting in a group or open channel.
- F17. The coach can change scenario parameters between turns (e.g. deadline, scope, staffing, pressure) within the bounds of F5a.
- F18. The coach can inject events between turns (e.g. "customer escalates", "person calls in sick"). Event injection is implemented as an engine `invoke` with `author = coach`.
- F19. The coach can change process rules between turns (introduce a standup, redefine ownership) via engine `edit`. (See F-PE7.)
- F20. Every coach action is appended to the run timeline as a `TimelineEvent` with `author = coach`.
- F21. On the next turn, affected agents receive relevant coach actions as part of their context. The agent decides how to interpret and act on them; coaching influences but does not directly control behavior.
- F22. Coaching visibility is determined by channel choice (DM = private, group = observed, open = broadcast). See F-CM10.
- F23. The coach can skip the coaching phase ("do nothing, advance") to observe agents acting unprompted.

### Coaching best practices

- F-BP1. A **coaching best-practices library** is part of the app: a list of named, categorized principles with short descriptions.
- F-BP2. The library has a **global** layer (editable in global config, ships with sensible defaults) and a **scenario-additions** layer (scenarios may add or override entries **by `id`**). Merge: start from global; scenario entry with matching `id` **replaces** the global row; scenario entries with new `id`s are **appended**.
- F-BP3. The library is consumed by the Summary loop (see [`agentic-design.md`](agentic-design.md)) and is *not* used during simulation — agents are not constrained by it.
- F-BP4. The Final Report assesses the coach's run against the merged library: which practices were applied well, partially applied, missed, or violated.
- F-BP5. Editing the library and re-running the summary on a completed run produces a fresh report; the prior report is preserved as a snapshot.

### Replay and inspection

- F24. Every run is saved as a stream of `TimelineEvent`s plus periodic ledger snapshots. Replay is playing back the timeline.
- F25. Both completed and in-progress runs can be **stepped back** to view state at any prior turn (read-only). Branching/forking past states is out of scope for v1.
- F26. When a run ends (goal met, exit condition fired, or coach ended manually), the runner displays an **end-of-simulation summary** view containing: outcome banner with stoplight per criterion, narrative coaching report, coaching-moments cards with before/after vitals **and impact tag (helpful / mixed / harmful)**, character-arc cards (starting vs ending portrait + vitals), metrics-over-time charts, run stats, optional coach-reflection text area, and a **Final Report** section (long-form deeper analysis judged against the coaching best-practices library). See [`ui-design.md`](ui-design.md) → End-of-simulation summary.
- F26a. The narrative, coaching-moment impact tags, alternatives, and Final Report are generated via a single LLM call (the Summary loop). If the call fails, the summary view falls back to its deterministic sections only and offers a retry.
- F26b. The Final Report renders as a markdown document with a full-screen "document view" and a download as `.md` action.
- F26c. Coaching moments include actions judged to have made things worse, not just better. The impact tag is `helpful`, `harmful`, `mixed`, or `neutral`.
- F26d. Where a moment is judged harmful or mixed, the Summary loop may suggest a specific **alternative approach** drawn from the best-practices library.
- F27. Two runs of the same scenario can be compared at a high level — particularly to contrast different coaching approaches _(stretch)_.

### Visuals

- F28. Avatars and key scene/background images are generated via OpenRouter vision models when a scenario is created or first run.
- F29. Generated visuals are cached and reused across turns of the same run.

### Web UI

- F30. Scenario module: browse, view, create, edit, fork.
- F31. Runner module ("mission control") — see [`ui-design.md`](ui-design.md) for the full spec. At minimum:
  - Top bar: sim name, current turn, **goal stoplight**, cost meter, advance-turn button.
  - Left rail: channels (primary) + views (kanban, roster, timeline, settings).
  - Center stage: the active view. Channel views own their own message input (no separate composer).
  - Right rail: goals (stoplight), vitals & metrics with sparklines.
  - Inspector drawer: opens from the right when a non-avatar object is clicked.
  - Pixel-art avatars with current expression rendered everywhere a character appears.
- F31a. Kanban view: 4 columns (`BACKLOG`, `DOING`, `DONE`, `PARKED`) with item counts in the header. Cards represent **team-and-topic initiatives** (not individual tasks); avatar appears small in the corner; parked-reason shown when applicable. Per-person headers above the board show committed/capacity load with stoplight bar.
- F32. Replay viewer: scrub through past runs, see state at any turn, see what coaching was given and how the next turn responded.

## Non-functional

- N1. Single-user app for v1. No auth model beyond local/single-tenant.
- N2. All model calls go through OpenRouter; no direct vendor SDKs.
- N3. Per-run cost should be inspectable (tokens used, approximate USD).
- N4. A run should be resumable across app restarts.
- N5. Scenario and run data should be portable (export / import).
- N6. Turn execution should be cancellable mid-flight.
- N7. UI should remain responsive while a turn is computing (turn work runs server-side, UI streams progress).

## Out of scope (v1)

- Multi-user collaboration.
- Real-time / continuous simulation.
- Mobile-first UI.
- Fine-tuned or self-hosted models.
- Formal validation against real organizational data.

## Constraints and assumptions

- OpenRouter is the only model provider integration in v1.
- Web UI only (no desktop/native client).
- English-only content in v1.
- Costs and latency are dominated by model calls; the runtime itself is not perf-critical.
