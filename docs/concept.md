# Concept

## What this is

`agile-sim` is a simulation app for studying how teams of people work together inside an organization. The user plays the role of a **coach**: they set up (or load) a scenario, watch it unfold turn-by-turn, can pause to inspect state, change parameters, and talk directly to any character in the simulation before letting it continue.

The simulated people and entities are AI agents. Each agent has its own personality, skills, goals, and forms its own opinionated view of what's happening. Non-human parts of the world (companies, teams, processes, market conditions) are also represented as agents or as simulated subsystems.

## Problem it tries to address

Coaching, process design, and management decisions usually have to be evaluated in real life, slowly, with confounding variables and no rewind button. There is no cheap, repeatable way to:

- See how a small change in process, role definition, or coaching intervention plays out across many turns.
- Explore "what if" variations of the same starting conditions.
- Practice coaching conversations with characters who have consistent, opinionated internal models.
- Generate concrete teaching examples (good and bad) that can be replayed and discussed.

`agile-sim` is meant to be a sandbox for these questions. It does not claim to predict reality — it is a tool for exploration, training, and structured thought experiments.

## Who it's for

- Coaches, managers, and team leads who want a sandbox to try out interventions.
- Trainers and educators who want generated, replayable case studies.
- Curious practitioners exploring how process and personality interact.

## Core ideas

### Scenarios

A scenario defines:

- The **setting** — company, industry, time pressure, external context.
- The **process and roles** in play (e.g. "two-team product org running scrum").
- The **characters** — each with personality, skills, goals, relationships.
- Other **entities** — teams, the company itself, processes, customers, vendors, market events.
- **Initial conditions** — the situation at turn 0.
- **Goal and exit conditions** — what counts as success, and what ends the run early (project cancelled, person quit, deadline missed, etc.).

Scenarios are reusable. A scenario can be browsed, edited, forked, and shared.

### The world ledger and the process engine

Two things sit between the agents and the runner.

The **world ledger** is the data store for everything structured: work items, capacity, commitments, relationships, vitals and metrics, channels, messages. It is plain records — no LLM, no rules, just the facts of the simulation. The coach inspects the ledger; agents reason from it; the engine writes to it.

The **process engine** is the rulebook and the active behavior on top of the ledger. It owns the rules of how work moves, who decides what, and what rituals must happen. It serves three roles:

- **Library** — agents can ask it questions: "what's our policy on X?", "do I need approval to do Y?", "when's the next planning ritual?". Reads are cheap and deterministic.
- **Gatekeeper** — when an agent wants to take a process-mediated action (escalate a decision, introduce new work, move someone between teams, change a deadline, request approval), the request goes through the engine. The engine validates against rules and either executes (writing to the ledger), queues (e.g. for approval), or rejects.
- **Scheduler** — fires scheduled events into the world: rituals come due, approvals time out, deadlines approach.

Alongside the engine sits a **process steward** — the PMO / delivery team / scrum master function. The engine is deterministic data and rules; the steward is an LLM-backed character that *operates* it: runs rituals, surfaces violations, nudges people, and is the natural counterpart for the coach to chat with about how the process is going. In a chaos scenario, the steward might be a minor or absent character and the rules minimal — that's fine, the engine just stays small.

The coach can change engine rules between turns (mandatory reviews, approval thresholds, ritual cadence, decision rights) as a first-class coaching action and watch the downstream effect on subsequent turns.

This separation keeps the runner domain-agnostic (it doesn't need to know what "approval" means), the ledger dumb (it just stores), and the engine focused (rules and validation only).

### Agents (characters)

Every agent is a **character** — a simulated person: an engineer, a manager, the customer, an exec, the process steward. Each agent holds:

- A persistent identity (name, handle, role, background).
- A personality and skill profile.
- Private goals and concerns (which may differ from stated ones).
- A memory of what it has experienced so far in the run.
- Its own opinionated interpretation of the current situation.

Teams and the company are *not* agents — they are structural entities in the world ledger, made up of characters. The "team's view" emerges from its members' views. The "company decision" is made by whoever has decision rights. This keeps the agent abstraction simple and matches how real orgs actually work.

### Turns

The simulation advances in **turns**, alternating between simulation and coaching. A turn represents a unit of in-fiction time defined by the scenario — half a day in a 5-day workshop, a sprint in a quarter-long delivery scenario, a month in a year-long org-evolution scenario. The runner is agnostic to what a turn means; the scenario decides.

Each turn cycle:

1. **Simulate** — agents act on the current state of the world; their process actions are validated by the engine and applied to the ledger; messages flow through comms; outcomes are recorded.
2. **Coach** — control returns to the user. They inspect, talk to characters, intervene in the world, or just observe. Every action is appended to the run timeline.
3. **Carry forward** — coach actions delivered to the affected agents as part of their context for the next turn.
4. **Advance** — the next turn runs, and the cycle repeats.

A run ends when a goal is reached or an exit condition fires.

### Fidelity: structured ledger + narrative

To stay realistic without modeling every ticket and meeting, the simulation splits responsibility:

- The **world ledger** holds structured, queryable state — work items, capacity, commitments, relationships, process state, vitals.
- **Agents** produce a narrative layer per turn — what they did, how they feel, what they think — anchored to ledger entities. New work, new commitments, new approvals all go through the engine via `invoke`; agents don't write to the ledger directly.

This way, phenomena like overload (committed > capacity), repeated work (overlapping items across teams), and conflicting decisions (multiple parties on a pending approval) emerge from structured state, while the *human* texture stays in the narrative layer where LLMs are actually good. For more detail on this split, see [`simulation-model.md`](simulation-model.md).

### Communication channels

Every simulation has a set of **comms channels** — Slack/Teams-style spaces where agents talk to each other. **Channels are defined by the scenario**, which keeps runs controllable and lets scenario authors direct the action. Agents can request a new channel during a run, but only as an `invoke` against the process engine, which decides whether to allow it based on scenario rules.

Channel types:

- **DM** — 1:1, between any two participants (including the coach).
- **Group** — small, named, persistent (e.g. `team-alpha`).
- **Open** — org-wide (e.g. `general`, `engineering`).
- **Event** — bound to a process event with a lifecycle: opens when triggered, has membership defined by the event, closes/archives when done. Examples: an incident channel for a production outage, a quarterly planning channel that exists only during planning, a "meeting" channel for an important conversation. The process engine opens and closes event channels via its scheduler.

The chat is meant to feel **familiar**. Each agent has a display name ("Priya Shah") and a handle (`@priya`). Messages support `@handle` mentions; mentioning someone guarantees the message reaches them on the next turn, the way real chat directs attention.

**Coach engagement is per-channel**, declared by the scenario:

- `post` — coach can read and post.
- `read` — coach can read but not post (observe-only).
- `none` — channel is hidden from the coach (useful for scenarios where the coach is meant to learn something happened only by inference).

In the **current harness**, posting to a declared `#` channel with `coach_engagement` of `read` or `none` is rejected for everyone (agents and coach); those modes are observation-only. Direct messages use `dm/<character_id>` and allow the owner character and the coach only.

Defaults are scenario-defined; a typical scenario will give the coach `post` on DMs with key characters and on `general`, `read` on team channels, and `none` on a private exec backchannel.

Channels carry two distinct kinds of activity:

- **Posts** in persistent channels (DM / group / open) are **asynchronous**. An agent posts during turn N; recipients see the post as part of their context on turn N+1. Threads play out over multiple turns, which matches how real org chat works at any reasonable turn cadence.
- **Conversations** in event channels are **narrated within the turn**. When an event channel is active (an incident, a planning meeting, an important conversation), each member contributes their intent and desired outcome as part of their normal per-turn output, and a single **narrator pass** then renders the whole exchange as a realistic transcript and posts it to the channel. The conversation is fully visible to participants the same turn; non-participants see it on turn N+1 like any other message. This costs one narrator call per active event channel and avoids spinning up many micro-LLM-calls to simulate dialogue message-by-message.

Threads — async or narrated — are first-class artifacts. The coach reads channels (subject to engagement mode), scrubs through threads turn-by-turn, and uses them as evidence for what to coach next.

This mechanism unifies a few things we already had:

- The **coach's 1:1 chat** with an agent is just a scenario-defined DM channel between the coach and that agent.
- **Visibility** of coaching actions ("private / observable / broadcast") reduces to channel choice.
- Information asymmetry — who knows what — emerges naturally from membership.

### Vitals and metrics

To make outcomes legible — and to make coaching trade-offs visible — every run tracks structured **vitals** (per character and per team) and **metrics** (per organization) on the world ledger.

- **Vitals** — energy, motivation, stress (per character); cohesion, capacity utilization (per team).
- **Metrics** — delivery progress against goal, employee happiness (avg of person motivation), productivity, technical debt, customer satisfaction (per organization).

A small **standard library** ships with the app and provides sensible defaults so most scenarios don't have to define their own. Scenarios can **extend** the library (add a custom vital like "engagement") or **override** specific definitions (e.g. tweak how stress is computed). This keeps semantics consistent across scenarios without forcing every author to re-invent the basics.

Vitals and metrics update from three sources, in priority order:

1. **Deterministic engine rules** — cheap, consistent. "If committed exceeds capacity for two turns, energy drops." Defined as part of the standard library or by the scenario.
2. **Agent self-reporting** — at end of turn each agent may propose a small bounded delta on its own vitals based on what happened narratively. The bound (±N) prevents the LLM from yo-yoing values run-to-run.
3. **Explicit events and coaching actions** — scenario events or coach actions can set values directly.

**Visibility is asymmetric.** The coach sees true values (god mode). Agents know their *own* vitals approximately and form opinions about others through interaction. So the coach can spot "Bob seems fine to his team, but his stress is at 90" — the kind of insight a real coach gets from sitting outside the situation.

This connects directly to scenario design: **goals and exit conditions can be expressed in terms of vitals and metrics**. A scenario isn't just "ship feature X by date Y" — it can be "ship feature X by date Y *while* keeping team motivation above 50 *and* tech debt below 30". This makes trade-offs legible: a coach who drives delivery by burning the team out will hit the delivery goal but fail the run, the same way a real org would learn that lesson the hard way.

### Coach interaction (the core loop)

The end-of-turn interaction is the heart of the app. The simulation runs so the user has something concrete to react to; the value is in what they do between turns.

The user is not a character inside the simulation by default. They are an outside coach. At the end of every turn they can:

- **Inspect** — see what happened, what each agent thinks, where things are stuck.
- **Coach** — open a 1:1 chat with any agent (or group) to give advice, ask questions, challenge assumptions, set expectations, reframe a situation.
- **Intervene in the world** — change a process, reassign work, inject an event, adjust a parameter (deadline pressure, scope, staffing, etc.).
- **Do nothing** — let the situation play out and see what the agents do unprompted.

Whatever the user does between turns is recorded on the run timeline and routed to the affected agents. On the next turn, those agents receive it as part of their context — a remembered conversation with the coach, a new directive from "management", a changed environmental fact — and behave accordingly. The agent decides how to interpret and act on the advice based on its own personality, skills, and goals; coaching is influence, not direct control.

Coaching visibility is determined by which channel the coach posts in (DM = private, group = observed, open = broadcast). No separate visibility flag.

This loop — **observe → coach → run a turn → observe again** — is the practice surface. A scenario is essentially a structured excuse to put the user in interesting coaching moments.

### Coaching best practices

The simulation can teach better when it knows what "good coaching" looks like. A **coaching best-practices library** captures principles the simulation uses when generating end-of-run analysis — which patterns the coach applied well, which were missed, and what alternative approaches might have helped at consequential moments.

Two layers:

- **Global library** — ships with the app, editable in global config. A curated set of cross-context principles ("address blockers within 2 turns of identification", "use private DM for course-correction before public callouts", "watch for unilateral commitments made under pressure", etc.).
- **Scenario additions** — scenarios can extend or override the global library with practices specific to their context (an agile-delivery scenario might add "never skip retros"; a workshop scenario might add "rotate facilitators to spread psychological load").

Each entry is short, named, and has a category and description. The library is consulted by the summary/final-report generation only; it does not constrain how agents behave during the run. This separation matters: the simulation produces what it produces; the analysis judges it against principles a coach is trying to learn.

The library is editable so coaches and trainers can tune what they want the simulation to reinforce. The same scenario judged against two different best-practices libraries will produce two different debriefs — useful for teaching different schools of thought.

### Generated visuals

Avatars, backgrounds, and scene visuals are generated through vision-capable models on OpenRouter, so each scenario has a distinct look without manual asset work.

### Replays and summaries

Every run is captured in a structured, machine-readable format (turns, agent states, events, user interventions). Past runs can be:

- Replayed step-by-step.
- Summarized into a narrative or coaching report.
- Diffed against other runs of the same scenario (e.g. "what did changing X do?").

## Interface

A web UI with two main modules:

1. **Scenario module** — browse, create, edit, fork scenarios.
2. **Runner module** — a "mission control" view of an active run:
   - Timeline of turns and events.
   - Current tasks and blockers.
   - Character roster with status, mood, and current focus.
   - State inspectors for teams, processes, and the company.
   - Per-agent chat panel for coaching.
   - Parameter controls.

## Non-goals (for now)

- Predictive accuracy about real organizations.
- Multiplayer / multiple simultaneous coaches.
- Realtime continuous simulation — turn-based is the model.
- Running fully offline — depends on OpenRouter for model access.

## Open questions

Genuinely undecided. (Several earlier questions have been resolved by the model converging — see commit history.)

- **Agent reasoning model.** Single LLM call per agent per turn, or a richer loop (perceive → reflect → act, à la Park et al.)?
- **Coachability.** Is influence a per-agent trait, or emergent from personality/skills? Should agents be allowed to ignore the coach? How is that modeled?
- **Disagreement in narrated conversations.** When two participants' desired outcomes conflict (e.g. one wants a commitment, the other wants to defer), how does the narrator handle it? Default: render the disagreement honestly and let the structured outcome reflect "no agreement reached", with downstream effects on the ledger.
- **Process engine v1 vocabulary.** Confirm the minimum rule set: roles, decision rights, approval gates, scheduled rituals, work-item state machine. What else, what's deferred?
- **Memory growth.** How much per-agent memory is kept, and how is it summarized as runs get long? Likely: memory stream + periodic reflection (Park et al.).
- **Mid-run turn-duration changes.** Allow the coach to switch cadence mid-run, or fix at scenario start in v1?
- **Determinism / reproducibility.** Are runs reproducible from a seed, or inherently stochastic?
- **Cost control.** Per-turn token budgets, model tier per agent role, or both?
- **Scenario authoring UX.** How much is form-based vs. prompt-based vs. YAML-like?
- **Standard library scope.** Which vitals and metrics ship as defaults in v1? Suggest: energy, motivation, stress (person); cohesion, capacity utilization (team); delivery progress, employee happiness, productivity, tech debt (org).
- **Self-report delta bound.** Per-turn cap on agent self-reported vital changes (suggest ±10 on a 0–100 scale).
