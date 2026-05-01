# Simulation model

This doc covers *how* the simulation produces realistic-feeling behavior without modeling every ticket and meeting. It sits between [`concept.md`](concept.md) (what the app is) and [`architecture.md`](architecture.md) (how the system is built).

## The core problem

Two failure modes to avoid:

- **Too abstract.** Agents narrate generically ("the team had a tough sprint, mood is low"). The coach has nothing concrete to grip on. Runs feel interchangeable.
- **Too concrete.** Every ticket, every standup, every PR. Token cost explodes — and worse, LLMs are bad at low-level bookkeeping. They lose track and contradict themselves, so the "realism" you bought is fake.

The phenomena we care about — overload, conflicting goals, repeated work, decision disagreements — don't need fine grain to emerge. They need **structured state that both the agents and the coach can see**, plus **agents that interpret that state through their own personality and goals**.

## Two layers, divided by what LLMs are good at

### Structured ledger (the world ledger, deterministic)

Cheap, queryable, persistent. The "Jira + HR + calendar" of the simulation. Held in the **world ledger**. The process engine writes most of it (via validated `invoke`s); agents read it. It tracks:

- **Work items** — id, title, owner(s), state, estimate, actual effort to date, dependencies, blocked-by. Granularity is "the unit of work the scenario cares about" — for a feature team, an epic or story; not subtasks.
- **Per-person turn records** — per character per turn: capacity (modified by mood, illness, leave, events), planned commitments, delivered work. Overload is just `committed > capacity` over time, made visible.
- **Teams and org structure** — composition and reporting lines.
- **Relationships and history** — who has worked with whom, who clashed, who owes whom a favor. Cheap to store; makes emergent narrative possible.
- **Vitals and metrics** — numeric per-character/per-team/per-org values (energy, motivation, stress, cohesion, delivery progress, happiness, tech debt, …) drawn from a standard library and extensible per scenario. Updated by deterministic engine rules, bounded agent self-reports, and explicit events. Truth is in the ledger; agents see their own approximately and form opinions about others through interaction.

The process engine separately owns the **rules and pending behavior state** (approval queue, ritual schedule, decision rights). Rules are applied to the ledger; they are not the ledger.

This is the substrate the coach inspects. It's the same data agents reason from.

### Narrative layer (agents, LLM)

What LLMs are *good* at: judgment, mood, conversation, the unsaid. Per turn, each agent produces:

- A short narrative of what they did this turn, anchored to specific work items they touched.
- Their internal view: how they feel about it, what they think others think, what they're worried about.
- Statements/actions toward others.
- Optional process invocations (escalate, request approval, etc.).

**Anchoring rule.** Narrative claims should reference ledger entities (work items, people, rituals, approvals). Agents may be *wrong* about ledger state — great for politics — but they don't invent new entities. New work items, commitments, approvals all go through the engine via `invoke`. This keeps the structured world and the narrative world in sync without forcing the LLM to be a database.

## Variable turn duration

A turn is a unit of in-fiction time, not a fixed length. Each scenario declares its own duration:

- A 5-day workshop scenario: turn = half a day or a day.
- A quarter-long delivery scenario: turn = a sprint or a week.
- A year-long org-evolution scenario: turn = a month.

The engine's tick, capacity numbers, ritual cadence, and deadline calendar are all expressed in the scenario's time unit. The runner doesn't care what a turn "means"; it just runs the loop.

Scenarios may also allow the coach to **change turn duration mid-run** (e.g. zoom out from weekly to monthly once the situation is stable, or zoom in for a critical week). _(Open: whether v1 supports this.)_

## Detail comes from three places

The coach gets concrete, specific detail (not generic narration) from three sources:

1. **Per-turn narratives.** Agents narrate what they did this turn, anchored to ledger entities.
2. **Async channel threads.** Posts in persistent channels (DM / group / open) accumulate over turns; the coach can read any channel and watch ordinary chatter play out.
3. **Narrated event-channel transcripts.** When the engine opens an event channel (incident, planning meeting, important conversation), members contribute their intent and desired outcome in their normal per-turn output, and a narrator renders the whole exchange as a realistic transcript in a single call. This produces high-fidelity moments — meetings, incidents, decisions — without a parallel execution mode and without per-message LLM calls.

The coach can also DM any agent ("walk me through the standup", "why did you push back?") to dig further. The agent answers from memory.

### DM channels (`dm/<character_id>`) as first-class comms

**Direct messages** are a normal channel type with `type: dm`. The stable id is `dm/<character_id>` where `<character_id>` is the **participant character** (the non-coach side). Membership is implicit: the coach and that character only. Scenario YAML lists public/group/event channels (e.g. `#eng-pilot`); coach–person private threads are **not** repeated as duplicate `channels[]` rows — they are addressed by convention as `dm/<id>`.

Delivery, engagement modes, and timeline logging treat DMs like other channels: async posts, turn-skewed read receipts in the harness, and per-channel `coach_engagement` (typically `post` on DMs that exist for coaching).

**Harness (v1):** scenario `channels[].name` values (e.g. `#team`) are primary async channels. Private coach threads are addressed as `dm/<character_id>` and are not duplicated as separate YAML channel rows.

Together these cover what a separate "scenes" mechanism would offer. There is no parallel high-fidelity execution mode in v1; event-channel narration is the answer.

## Why this answers the realistic phenomena

- **Overload.** Ledger shows committed > capacity for N turns. Agents narrate the strain. Coach sees both the number and the human reaction.
- **Conflicting goals.** Agents have explicit goal fields. Same world state produces different narrated interpretations and different `invoke` requests. The engine surfaces process-mediated conflict; the resolver handles the rest.
- **Repeated work.** Two work items with overlapping descriptions across teams show up in the ledger. The steward (or a turn summarizer) can flag it.
- **Decision disagreements.** A pending approval has multiple interested parties; their per-agent narratives diverge; the coach can chat with each to dig in. No reconciliation needed — divergent views are kept and recorded.

## What we deliberately leave out (v1)

- Per-task or per-PR fidelity.
- A separate "scene" execution mode (event-channel narration covers it).
- Per-message LLM calls inside meetings (the narrator renders whole conversations in one call).
- Mid-run turn-duration changes (likely fine to add later).
- Letting agents invent ledger entities directly (everything goes through `invoke`).

These are all reasonable v2 additions if the simpler model proves limiting.

## Influences

The narrative-by-narrator pattern follows a "decide then dramatize" approach (the simulation determines outcomes; the narrator renders the dialogue). The memory model follows Park et al.'s Generative Agents (memory stream + periodic reflection). The split of structured ledger from narrative is closer to simulation games (Dwarf Fortress, Crusader Kings) than to autonomous-agent frameworks. See [`agentic-design.md`](agentic-design.md) for how these influences land in the agent runtime.
