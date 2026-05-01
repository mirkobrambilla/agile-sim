# Agentic design

How LLMs are used in this project: which loops exist, what their prompts look like, how memory is managed, how tools work, and what library we build on.

## Where LLMs run in this system

We have **four distinct LLM-using loops** and nothing else. The orchestrator drives all of them; none of them call each other.

1. **Per-turn agent loop** — one call per active character per simulation phase.
2. **Narrator loop** — one call per active event channel per turn.
3. **Coach chat loop** — one call per coach message during the coaching phase.
4. **Summary loop** — one call when a run ends, producing the end-of-simulation summary.

A turn with N agents and E active event channels = `N + E` LLM calls in the simulation phase. Coach chat adds a call per coach message during the coaching phase. End of run adds one summary call.

There are no autonomous loops — no agent decides to "run again" or "ask another agent something". The orchestrator dispatches each call, collects the structured result, and moves on.

## Loop 1: Per-turn agent

The dominant loop. Each character runs once per turn.

### Prompt structure

A single, well-stuffed prompt assembled by the orchestrator. The agent does not iteratively call tools mid-call; everything happens in one round-trip.

```
[system]
You are <display name> (<role>) in a simulated organization.
<personality, communication style, working preferences>
<core skills, weaknesses>
<private goals and concerns — may differ from stated ones>
Output format: <JSON schema for AgentTurnOutput>

[user / context]
## Current situation (turn <n>, <duration unit>)
<one-paragraph world summary derived from the ledger>

## Your state
- vitals: energy <x>, motivation <y>, stress <z>
- role: <role>
- teams you belong to: <...>
- work items you own: <list with state, estimate, actuals>

## Process digest
<deterministic summary of process rules and pending state that affect you:
 your decision rights, open approvals you're on, scheduled rituals you'd attend,
 deadlines you own>

## What you've heard since last turn
- direct mentions: <list>
- new messages in <#channel>: <recent messages, condensed>
- ...

## What the coach said (if any)
<coach DM transcript or coaching action targeting you>

## Active conversations you're part of this turn
- event channel <id> ("<name>"): <topic, who else is in it, opening prompt if any>
- ...

## Your memory
<recent observations (last K turns)>
<top-M relevant reflections>
```

### Output shape (structured)

```
AgentTurnOutput {
  narrative: str                                # short prose: what I did this turn
  channel_posts: [                              # async, persistent channels
    { channel: str, content: str, parent_id: str? }
  ]
  reactions: [                                  # 0–2 reactions on recently-seen messages
    { message_id: str, emoji: str }
  ]
  process_invocations: [                        # validated by engine
    { kind: str, args: object }
  ]
  vital_self_report: {                          # bounded ±N per turn
    energy?: int, motivation?: int, stress?: int, ...
  }
  event_contributions: [                        # one per active event channel
    { channel: str, intent: str, state: str, desired_outcome: str }
  ]
  internal_state_update: str?                   # optional belief/feeling shift,
                                                # appended to memory stream
}
```

The character's **expression** (idle / happy / frustrated / overloaded / bored / surprised / proud / sad) is *not* part of the agent's output — it is derived deterministically from the resulting vitals and recent context by a small rule table in the UI/orchestrator layer. This avoids spending a tokens-worth of decision on something we can compute, and keeps expression consistent with the underlying state.

The orchestrator is the only thing that interprets this output: it routes posts to comms, invocations to the engine, vital deltas to the ledger (clamped), contributions to the narrator queue, and appends `narrative` and `internal_state_update` to the agent's memory stream.

### Why a single call (not iterative tool calling)

Multi-step tool-calling loops (call → tool → call → tool → final) would let an agent ask "what's the policy on X?" mid-thought. That's seductive but adds latency, cost, and orchestration complexity. For our scale (potentially many agents per turn) and our preference for predictable cost, we instead **stuff a deterministic process digest into the prompt** and let the agent produce its full structured response in one shot. If the agent's response references something it doesn't have detail on, it can ask in narrative or post a question in a channel — the next turn will carry the answer.

This is a deliberate v1 simplification. We can selectively add bounded tool-calling later (e.g. up to 2 `consult` calls before the final structured response) for specific agent types. Not needed for v1.

## Loop 2: Narrator

Runs once per active event channel per turn, after all agents have produced their outputs.

### Prompt structure

```
[system]
You are the narrator of an organizational simulation. Render a realistic
conversation transcript for a Slack-style channel based on each participant's
contribution. Stay in each character's voice. Reflect disagreement honestly.

[user / context]
## Channel
<id>: <name>, type: event, opened on turn <n>, topic: <description>

## Participants
- @priya (Priya Shah, Senior Engineer, Team A) — voice: <one line from profile>
- @marcus (Marcus Chen, Engineer, Team B) — voice: <one line from profile>
- ...

## Contributions
<for each participant>
- @priya
  intent: get unblocked on the /users response shape
  state: frustrated, working overtime, stress 78
  desired_outcome: leave with the contract and a deadline I can hit

## Ledger context (relevant facts)
- integration work item is overdue by 2 days
- Marcus has not commented on the integration thread in 3 turns
- ...

## Engine constraints
- decision rights: Lin can approve scope changes; Sam can call meetings
- max conversation length: 8 messages

Output format: <JSON schema for NarrationResult>
```

### Output shape

```
NarrationResult {
  transcript: [
    { author_handle: str, content: str, parent_index: int? }
  ]
  structured_outcome: {
    decisions: [{ description: str, decided_by: str }],
    commitments: [{ who: str, what: str, by_when: str? }],
    unresolved: [str],
    summary: str
  }
}
```

The transcript is appended to the channel as `Message`s authored by the corresponding characters. The structured outcome is handed to the engine, which translates it into ledger writes (work-item status changes, new commitments, vital nudges if a participant got bulldozed, etc.).

### Why this works as one call

Once each participant has stated intent and desired outcome, the conversation's outcome space is small. The narrator's job is rendering, not deciding. We're trading "agents reason about each other in real time" for "agents declare what they brought, narrator dramatizes". This matches how humans actually remember meetings (you remember the gist and outcome, not exact dialogue) and is dramatically cheaper than per-message simulation.

## Loop 3: Coach chat

When the coach DMs an agent during the coaching phase, the agent must respond conversationally.

### Prompt structure

Per coach message:

```
[system]
You are <display name>, talking with the coach who is outside the simulation.
Be honest, in-character. The coach is a trusted outside observer; you can be
candid in DM. <personality, communication style>

[user / context]
## Your current state
<same as per-turn loop, condensed>

## Your memory
<recent observations + relevant reflections>

## This conversation so far
<prior coach-chat messages, full text>

## Coach's new message
<text>

Output format: { reply: str, internal_note: str? }
```

### Why a separate loop

Coach chat is interactive — the coach types, expects a quick reply, may type again. Wrapping it in the per-turn structured-output schema would be heavy and feel wrong. So coach chat uses a leaner prompt and a simple `{reply, internal_note?}` output.

### Memory consolidation

When the coaching phase ends, every coach-chat conversation that happened is **summarized into a single memory entry** for the agent ("the coach pushed me to admit I've been avoiding the integration conversation; I committed to raise it"). This summary is appended to the memory stream and influences the next per-turn call. We don't replay the raw transcript into the next turn's context — the summary is enough.

## Loop 4: Summary

Runs once when a run ends (goal met, exit condition fired, or coach ended manually). Produces the structured content for the end-of-sim summary view *and* the long-form Final Report (see `ui-design.md` → End-of-simulation summary).

### Prompt structure

```
[system]
You are writing a coaching debrief for an organizational simulation that just
ended. Be honest, specific, and useful. Some coach actions help; some hurt.
Name both. Reference characters by name and turns by number. Do not flatter.
Judge the coach's performance against the coaching best-practices library
provided. Where a moment went poorly (or could have gone better), name a
specific alternative drawn from those practices.

[user]
## Scenario
<setting, goal, exit conditions>

## How it ended
<which condition fired, on which turn, with what values>

## Run timeline (condensed)
<deterministic per-turn summary: who did what, what happened on the ledger,
 what coach actions were taken, vital deltas; one short paragraph per turn>

## Characters involved
<for each: name, role, starting and ending vitals, key moments>

## Coach actions taken
<chronological list: turn, kind, content, target>

## Coaching best-practices library
<global library + scenario additions, each: name, category, description>

Output format: <JSON schema for SummaryResult>
```

### Output shape

```
SummaryResult {
  outcome: { kind: "success" | "partial" | "failure",
             headline: str,
             criteria_status: [{ name: str, status: "met" | "near" | "failed",
                                 final_value: number | str }] }

  narrative: str                              # 3–5 paragraphs of coaching prose

  coaching_moments: [
    { turn: int, summary: str,
      impact: "helpful" | "harmful" | "mixed" | "neutral",
      affected_characters: [str],
      relevant_vitals: [{ name: str, before: number, after: number }],
      assessment: str,                        # candid; names what worked or didn't
      alternative: str? }                     # optional: a different approach
                                              #   suggested by the best-practices
                                              #   library
  ]

  character_arcs: [
    { character: str, arc: str,
      starting_state: str, ending_state: str }
  ]

  best_practices_assessment: [                # one entry per best practice the
                                              #   coach plausibly engaged with
    { practice_id: str,
      verdict: "applied_well" | "partially_applied" | "missed" | "violated",
      evidence: str }
  ]

  final_report_markdown: str                  # the long-form deeper-analysis
                                              #   document, ~600–1500 words
                                              #   suitable for direct rendering
                                              #   and download

  what_to_practise_next: [str]                # 2–3 short recommendations
}
```

The orchestrator layers this over the deterministic data the UI also has access to (vital snapshots, message counts, costs) to render the full summary view. The `final_report_markdown` is rendered both inside the dashboard's "Final Report" section and as a standalone document view.

### Cost and failure mode

This is one large-context call — the entire run timeline plus the best-practices library goes in. It is the most expensive single call in a run, but happens at most once. The output is sized to keep the report rich without being unbounded. If it fails, the summary view falls back to its deterministic-only mode (see `ui-design.md`); a "retry generation" affordance is available.

## Memory and compression

Following Park et al. (Generative Agents) with adjustments for our turn cadence.

### Per-agent memory stream

Append-only sequence of entries:

```
MemoryEntry {
  turn: int
  kind: "observation" | "reflection" | "coach_chat_summary" | "narrative"
  content: str
  importance: float          # 0..1, set on creation
  embedding: vector?         # for retrieval (lazy; only if memory grows large)
}
```

Sources of entries:

- **Observation** — written each turn from the agent's perceived inputs (delivered messages, ledger changes that affected them, narrated transcripts they were in). Generated deterministically, not by an LLM, with importance scored heuristically (mentions, vital changes, work-item changes → higher).
- **Narrative** — the `narrative` field of the agent's per-turn output.
- **Reflection** — periodic synthesis (see below).
- **Coach chat summary** — one entry per coach-chat conversation in the prior coaching phase.

### Recent window

The last K turns of memory are always included verbatim in the per-turn prompt (suggested K = 5 for a sprint-cadence scenario, K = 10 for a workshop-cadence). Cheap and keeps recency strong.

### Reflections

Every R turns, or when memory size exceeds a budget, run a **reflection** LLM call per agent:

```
[system]
You are reflecting on your recent experience. Read the memories below and
write 3–5 short higher-level insights about what is happening, who you are
becoming, and what you should pay attention to.

[user]
<recent + retrieved memories>
```

The reflection's output is parsed into individual `reflection` entries with high importance and added to the stream. Reflections are themselves retrievable, so future reflections can build on past ones (the Park et al. trick).

This is the **only** other source of LLM cost beyond the three main loops, and it's bounded — one call per agent per R turns.

### Retrieval

When building a per-turn prompt, the orchestrator selects:

- The recent window (verbatim).
- The top-M reflections, ranked by importance × recency-decay × relevance-to-current-situation. v1 can do simple recency + importance and skip embeddings entirely. Add embeddings if/when needed.

### Compression

When memory exceeds a per-agent budget (say 200 entries), oldest non-reflection entries are batch-summarized via one LLM call into a single condensed observation, which replaces them. Reflections are preserved (they're already condensed insight). This is rare in practice — most runs won't hit the budget.

## Tools (in our terms)

We deliberately do not use mid-call tool calling in v1. What other systems call "tools" we model as **structured output fields** that the orchestrator interprets and dispatches:

- `consult(query)` — implicit. The deterministic process digest in the prompt covers most of what an agent would consult about. If an agent needs more, it says so in narrative or asks in a channel; the answer arrives next turn.
- `invoke(action)` — appears as entries in `process_invocations`. The engine validates and applies them after the agent call returns.
- `post(channel, content)` — appears as entries in `channel_posts`.

When we need the LLM's mid-call agency (rare, e.g. an agent asking "what does the engine say about X" before deciding), we'll add bounded tool calling — at most 2 `consult` calls before forcing a structured final response. Out of scope for v1.

## Library choice

### Recommendation: PydanticAI + OpenRouter + Langfuse

- **PydanticAI** as the agent primitive. We define one `Agent` per agent type (character, narrator, reflection, coach-chat). Each gets a typed input model and a typed output model (the structured shapes above). PydanticAI handles prompt assembly, structured output parsing/validation, retries on schema failures, and provider abstraction. It does not impose orchestration; we keep our turn loop.
- **OpenRouter** as the model provider. PydanticAI supports OpenAI-compatible endpoints, which OpenRouter exposes. Per-agent model selection is straightforward (`gpt-4o-mini` for background characters, `gpt-4o` or `claude-sonnet` for focal ones, `claude-opus` or `gpt-4o` for the narrator).
- **Langfuse** for observability. Wraps every model call; gives us per-run cost, per-agent cost, latency, prompt/response inspection, and replay-ready traces. Self-hostable.

### What we explicitly do not adopt

- **CrewAI / AutoGen / CAMEL / LangGraph.** All four are designed for autonomous multi-agent task execution. We have one explicit turn loop, deterministic dispatching, no autonomous handoff, no code execution, no emergent group chat. These frameworks would force us to either embrace their orchestration (giving up control of our turn semantics) or fight it. The widely-quoted advice from practitioners — "don't let the framework own your architecture" — applies directly.
- **Mid-call tool-use loops.** Adds latency and cost for marginal benefit at our scale. We may revisit per-agent type later.

### Lighter alternatives if PydanticAI feels heavy

- **Plain `openai` SDK + `instructor`** — slightly thinner; same idea, less framework. Reasonable fallback if PydanticAI causes friction.
- **Roll our own** — also fine; the agent layer is not large.

## Cost shape

A turn with N active characters and E active event channels:

- N agent calls (one per character).
- E narrator calls.
- 0 to N reflection calls (only if any agent's reflection cadence triggers this turn).
- During the coaching phase: ~1 call per coach message.

A typical sprint-cadence turn with 6 characters and 1 active event channel = 7 simulation calls + however many coach messages. That's the predictable, bounded shape we wanted.

## What this means for the agent runtime

- One PydanticAI `Agent` definition per role: `CharacterAgent`, `NarratorAgent`, `ReflectionAgent`, `CoachChatAgent`, `SummaryAgent`. Each is a small file: a system prompt template, an input schema, an output schema.
- The orchestrator (our code) holds the turn lifecycle, builds inputs, dispatches calls, applies outputs.
- Memory is ours — a small module that owns the stream, retrieval, and reflection scheduling.
- Langfuse wraps the OpenRouter client globally; no per-call instrumentation needed.

The agent runtime, in lines of code, is probably small. The interesting code is everywhere except the agent runtime: the engine, the ledger, the narrator wiring, the comms delivery, the coaching UX. That's the right shape.

## Open questions specific to agentic design

- **Reflection cadence (R).** Suggest every 3–5 turns at sprint cadence; every 1–2 weeks of in-fiction time at workshop cadence. Confirm.
- **Importance scoring.** Heuristic in v1 (mentions, vital changes, work-item changes); learned later if needed.
- **When to introduce embeddings.** Probably not v1. Recency + importance is enough until memory grows past ~50 entries per agent.
- **Per-agent model tiering.** Which roles get which model? Suggest: narrator gets the strongest available model (it determines transcript quality); focal characters get strong; background characters get cheap; reflection can use cheap.
- **Bounded tool calling for select agents.** Worth revisiting once we have v1 running and see whether agents are reaching for unavailable detail.
