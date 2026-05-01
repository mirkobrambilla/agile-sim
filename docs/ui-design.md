# UI design

How the app should look, feel, and behave. This doc covers the user interface only — for the underlying simulation see [`concept.md`](concept.md), [`simulation-model.md`](simulation-model.md), and [`architecture.md`](architecture.md).

## Goals and feel

The aesthetic is **early-2000s Japanese simulation game meets vintage MS Teams**. Pixel-art characters with expressive faces inside a chat-like business UI from the era. Think Persona's social-link panels and Princess Maker's stat screens, rendered as if they were a corporate communicator from 2003.

- **Game-like, not enterprise.** This is a sandbox; the UI should feel like a sim game, not a SaaS dashboard.
- **Pixel-art characters with mood expressions.** Each character has a small set of sprites (idle, happy, frustrated, overloaded, bored, etc.) that swap based on their current state. This is the single biggest readability win — at a glance you see who's struggling.
- **Vintage-Teams chat shell.** The chat / channel UI borrows the layout and chrome of early Microsoft Teams (or its ancestors): left channel rail, threaded messages with avatars and timestamps, light reactions on messages. Slightly boxy panels, modest gradients, readable sans type.
- **Coach is a participant.** No special "coach composer" panel — the coach types in the same channel input boxes as everyone else. Click an avatar → opens that character's DM channel. The coach feels like a member of the team (with extra powers).
- **Object-first, not form-first.** The user sees the *things* in the simulation (characters, teams, work items, channels, goals, rules) and clicks on them to inspect or edit.
- **Comfortable editing.** When the user wants to write prose — backstories, situation, scenario description — they get a real markdown editor with a full-screen toggle.

## Information architecture

Three top-level views.

### 1. Sim picker (entry view)

- A grid of **simulation cards**: name, short description, scenario tag, a small visual (cover image generated from the scenario).
- "New simulation" card to start fresh.
- Filters: by tag, by status (draft / runnable / archived).
- Clicking a card → opens it in the runner (or in scenario edit mode if it has no runs yet).

### 2. Scenario editor

The pre-run view of a simulation. All the things that *define* the scenario:

- Setting (free-text markdown).
- Characters (clickable cards → inspector for personality, role, backstory, sprite set, model selection).
- Teams and org structure.
- Channels (clickable list → inspector for type, members, coach engagement).
- Process rules (decision rights, gates, rituals).
- Vitals/metrics (defaults from the standard library; scenario can extend or override).
- Goal and exit conditions.
- Initial conditions (turn 0 world state, initial work items, starting vitals).
- Parameters.

Most of these are reachable by clicking the corresponding object. There is no "settings page" — the scenario *is* the editor.

### What's editable mid-run

Once a run has started, the rules change:

- **Locked** (read-only with a small 🔒 indicator and tooltip): initial conditions, starting vitals, character core profiles. These seeded turn 0; rewriting them retroactively would invalidate the run.
- **Editable, takes effect next turn**: process rules, scenario parameters, channel membership, channel coach-engagement modes, vitals (as a coach nudge), character model selection. Edits show a small "applied — takes effect at turn N+1" toast.
- **Editable freely** (UI / personal): which view is open, sprite preferences, dev panel state.

This rule keeps runs honest while letting the coach do all the in-fiction interventions that matter.

### 3. Runner (mission control)

Where most of the action happens once a sim is running. See "Layout" below.

There is also an implicit fourth: the **replay viewer**, which is just the runner in read-only mode scrubbing through past turns.

## Layout: the runner

A familiar four-zone shape, like a vintage chat app:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ Top bar: <sim name>  · turn 12 / day  · 🟢 on track  · 💰 cost  · [advance] │
├───┬──────────────┬───────────────────────────────────┬──────────────────────┤
│   │              │                                   │                      │
│ A │  Left rail   │         Center stage              │   Right rail         │
│ p │              │                                   │                      │
│ p │  Channels    │  (whichever view is selected;    │  Goals (stoplight)   │
│   │  • #general  │   if a channel is selected, the  │  Vitals & metrics    │
│ r │  • #team-a   │   message input is at the bottom │  - sparklines        │
│ a │  • #team-b   │   of the channel itself, not     │  - per-team gauges   │
│ i │  • ⚡incident│   below the layout)              │  - org metrics       │
│ l │  • @priya    │                                   │  - alerts at         │
│   │  • @marcus   │                                   │    threshold         │
│ 🏠│              │                                   │                      │
│ ▶ │  Views       │                                   │ ─────────────────    │
│ ✎ │  • Kanban    │                                   │  📝 Reflection       │
│ ⚙ │  • Roster    │                                   │  (small scratchpad   │
│   │  • Timeline  │                                   │   for coach notes)   │
│   │  • Settings  │                                   │                      │
└───┴──────────────┴───────────────────────────────────┴──────────────────────┘
```

- The **app rail** (far-left, icons-only) is the top-level nav across the app: sim picker, runner, scenario editor, settings. Always visible. Reinforces the period-authentic chat-app feel and keeps the left rail focused on the current sim's channels and views.
- A small **reflection scratchpad** sits at the bottom of the right rail: free-text notes the coach can jot mid-run (observations, hypotheses, things to try). Persisted with the run; surfaced in the end-of-run summary as the coach's own pre-debrief notes.

Click any object anywhere in this layout (an avatar, a work-item card, a channel name in a message, a metric gauge) → opens an **inspector drawer** from the right that overlays the right rail. Drawers stack; closing one pops back to the previous.

The structure:

- The **top bar** carries identity, current turn, **goal stoplight** (🟢/🟡/🔴), cost meter, and the only universal action button (`advance turn`).
- The **left rail** is navigation: channels (primary, like Teams) and other views beneath.
- The **center stage** is the active view. When a **channel** is selected, the channel itself owns its message input — the coach types in the channel, like any other member. There is no separate composer panel.
- The **right rail** is the always-on goals + vitals + metrics dashboard.
- The **inspector drawer** opens from the right when an object is clicked; for editing or inspecting one thing at a time.

### Click an avatar = DM

A central interaction: clicking a character avatar anywhere (in a message, on a kanban card, in the roster, in the inspector) opens that character's **DM channel** in the center stage, scrolled to the latest. Coach can chat right there. This makes the coach feel like a member of the team rather than someone operating from a control panel.

If the coach has never DM'd that character before, the channel is created on first message (subject to scenario engagement-mode permissions).

### Center stage views

- **Channel view** — vintage-Teams style threaded list. Pixel avatar + author + content + reactions row + thread indicator. Timestamps in turn-units (`turn 12 · 14:30 sim time`). Narrated event-channel transcripts have a distinct border + "📣 transcript" badge so they read clearly as rendered conversations. Message input lives at the bottom of the channel.
- **Kanban view** — work items as **team-and-topic cards** (initiatives/epics, not individual tasks) in **4 columns**: `BACKLOG · DOING · DONE · PARKED`. Each column header shows a count (e.g. `DOING · 7`). The `PARKED` column collects anything blocked, cancelled, or in trouble — the place to scan for problems. Cards lead with the team band and topic title; owner avatars appear small (16–20px) in the corner with current expression. Cards show a brief state line (e.g. "in progress · 4 turns" or "parked: blocked by API gate"). Per-person headers above the board show their `committed / capacity` ratio with a load bar (stoplight colour).
- **Character roster** — grid of large pixel avatars showing current expressions. Name, role, top-line vital under each. Click → DM (consistent with the avatar-click rule).
- **Character profile** (full-screen, opens from the inspector "expand" affordance) — large character portrait (pixel art), backstory (markdown), goals, relationships graph, vitals time-series, recent narratives, recent memory snippets.
- **Timeline** — horizontal strip of turns. Each turn tick shows small icons for what happened (messages volume, rule changes, exit-condition warnings, vital shifts). Hover → tooltip summary. Click → loads the runner state at that turn (read-only replay).
- **Scenario editor** — same editor used pre-run, accessible mid-run for live tweaks. Locked fields show 🔒; editable fields show "applied — takes effect at turn N+1" on save.
- **Settings** — model tiers per agent role, cost limits, narrator settings, run metadata.

### Inspector drawer

Object-typed but consistent shape:

- Header: object icon (or pixel avatar) + name + small actions (edit, archive, expand to full-screen profile, etc.).
- Body: read view by default, edit view on click into a field. Edit view uses the right control for the field — markdown editor for prose, sliders/numeric inputs for vitals, multi-select for membership. Locked fields show 🔒 with a tooltip explaining why.
- Footer: "show in context" links (e.g. "view this character's channels", "open DM", "view this work item on the kanban").

Drawers should be roomy — at least 480px wide — because most editing happens here.

### Inspection: per-object views

What the drawer (or its expanded profile) shows for each kind of object:

- **Character** — pixel avatar in current expression, name + handle + role, vitals as bars + sparklines, current work items, recent channels, relationships, backstory (markdown), recent narrative snippets. Footer: open DM, view on kanban.
- **Team** — emblem, name, members (avatar grid), current `committed / capacity`, team vitals (cohesion, utilization), recent activity.
- **Work item** — title, owner avatar, state pill, estimate vs. actuals, dependencies and blocked-by chain, narrated mentions across turns, audit trail (state changes by turn).
- **Channel** — type icon, name, members, lifecycle status, coach engagement mode, message count by turn (mini chart), pinned context (for event channels: the bound process event and outcome).
- **Vital / metric** — label, current value, threshold markers from goals, **time-series chart** across all turns, breakdown of what changed it (rule fires, self-reports, coach nudges, narrator outcomes).
- **Goal / exit condition** — stoplight status (🟢/🟡/🔴). Each criterion expands to its target and current value. When the scenario uses **outcome work items** (`require_done_ids`), list each id with title (from ledger), state (pending / doing / done), and its own stoplight — not only a single "N done" aggregate. The read-only web prototype may show summary goal state only until the runner UI catches up.
- **Process rule** — definition, version history, things it currently gates, recent applications.
- **External party** (customer / vendor / exec): same as character but with a distinct outline marking them as outside the org.

## Design language

A small visual vocabulary applied consistently.

### Objects and their look

| Object | Look |
|---|---|
| **Character** | Pixel-art avatar (square, ~64×64) showing the character's current **expression** (idle / happy / frustrated / overloaded / bored / surprised / proud). Display name; `@handle` in muted text; an accent colour. |
| **Team** | A small pixel emblem (scenario-defined) + colour band; team name. JRPG-guild-crest energy. |
| **Work item** | A card with vintage-game UI chrome. Title, owner avatar (in current expression), state pill, estimate badge, optional ⚠️ overload tag. |
| **Channel** | `#name` for groups/open, `@handle` for DMs, ⚡ icon for event channels. Coach engagement mode in a small icon: ✏️ post, 👁 read-only. |
| **Message** | Avatar + author + content + reactions row. Mentions as pills. Narrated event transcripts have a distinct border + "📣 transcript" badge. |
| **Vital** | Horizontal bar with label, value, threshold markers; colour shifts when near a threshold. Sparkline below. Click to see full time-series. |
| **Metric (org)** | A small gauge or bar with stoplight colour. Sparkline. Click for time-series + breakdown. |
| **Goal / exit condition** | Pinned at the top of the right rail with **stoplight** status: 🟢 on track / 🟡 at risk / 🔴 failing. Each criterion expands to show its target and current value. For **outcome-based goals** (`require_done_ids`), show **each required work item id** (e.g. O1, O2) with title, column/state, and per-item stoplight — not only a rolled-up count. |
| **Process rule** | A card in the rules list; tap to inspect. Versioning shown as a small revision count. |
| **External party** | Same as character but with a distinct frame (e.g. dashed pixel border) so it reads as outside the org. |

### Character expressions

Each character ships with a small **sprite set** of expressions:

- `idle` (default)
- `happy`
- `frustrated`
- `overloaded` (high stress / over-capacity)
- `bored` (low motivation / low stimulation)
- `surprised`
- `proud`
- `sad`

Expressions are **derived deterministically from vitals and recent context** (no extra LLM call). A simple rule table:

```
stress > 80                → overloaded
motivation < 25            → bored
recent vital_self_report
   contains negative shift → frustrated or sad
recent commitment shipped  → proud
just received a mention    → surprised (briefly)
otherwise                  → idle
```

The exact mapping is tunable per scenario; defaults ship with the standard library. The sprite swaps in real time as the right rail's vitals update.

### Reactions on messages

A small set of emoji reactions, kept tight to feel period-appropriate:

- ❤️ heart
- 👍 thumbs-up
- 🤔 thinking
- 😅 awkward
- 👀 eyes
- 🎉 celebration

Reactions are stored on messages. The coach reacts by clicking; characters may include reactions in their per-turn output (one or two, not many) when something genuinely lands or stings. Reactions are a low-cost social signal that helps the coach read the room without scrolling.

### Stoplight semantics

Used wherever a "is this on track?" judgement is helpful:

- 🟢 **on track** — within target band; no action needed.
- 🟡 **at risk** — drifting toward a threshold; warrants attention.
- 🔴 **failing** — threshold breached; goal/exit condition is failing.

Goal/exit panels, per-team load headers, and big org metrics use these. Same three colours, same meaning, everywhere.

### Colour, type, density

- **Palette**: vintage-Teams base (cool blues, light greys, white) with bright accent colours from a JRPG palette (warm reds, golds, teals) used for characters, teams, and stoplight states. High-saturation but used sparingly.
- **Type**: one readable sans for UI (era-appropriate, e.g. something Verdana-ish) plus a small bitmap/pixel font for HUD-style indicators (vital values, turn counter). Mono for the dev/debug panel and markdown editor.
- **Density**: roomy by default. The right rail is the densest surface; channels are spacious like Teams.

## Interaction patterns

- **Click an avatar = DM.** Anywhere an avatar appears (message author, kanban card owner, roster, inspector header, profile), single-click opens that character's DM channel. The drawer-style inspector for a character is reached from the roster's expand affordance or from a keyboard shortcut, not from clicking the avatar.
- **Click-to-inspect (non-avatar objects).** Clicking a work item, channel, vital, goal, or rule opens its inspector drawer. Single click is non-destructive — read view first.
- **Click-to-edit inline.** Inside the drawer, fields show their value; clicking enters edit mode. `Esc` cancels, `⌘/Ctrl-Enter` saves. No "Edit" buttons cluttering read views. Locked fields don't enter edit mode (and explain why on hover).
- **Type in the channel, like a member.** No separate composer. Each channel view has its own input at the bottom; the coach just types and posts. `@handle` autocomplete from the scenario's characters.
- **React with one click.** Hover a message → reaction picker fades in. Click an emoji to react.
- **Markdown everywhere prose lives.** Backstory, situation, scenario description, channel posts, agent narratives. Single markdown editor component (e.g. EasyMDE) used everywhere, with a full-screen toggle for serious writing.
- **Hover for quick info.** Hovering a character avatar shows a small tooltip (name, role, current expression-derived mood, top-line vitals).
- **Keyboard.** `J/K` (or arrows) to step turns in the timeline view; `/` to focus the active channel input; `?` for shortcut help; `D` toggles the dev panel. Power users will want these early.
- **Mid-run edits feel natural** within the bounds of what's editable (see "What's editable mid-run" above). Saved edits show a small "applied — takes effect at turn N+1" toast.

## Timeline and step-back

The timeline view is the traceability surface. A single horizontal strip:

- Each turn is a tick. Larger ticks for "important" turns (exit-condition warnings, big vital shifts, rule changes, narrated event channels resolved).
- Hover a tick → tooltip summary ("turn 12 · integration incident resolved · Priya stress -10").
- Click a tick → runner switches to a **read-only view** of the state at that turn. All views (channels, kanban, vitals) reflect that point in time. A clear "viewing turn 8 (live: turn 12)" banner appears with a "return to live" button.

Step-back is for **understanding what happened**, not for forking history. Branching is out of scope for v1.

## End-of-simulation summary

When a run ends — because a goal is met, an exit condition fires, or the coach ends it manually — the runner enters an **end state**. The center stage switches to a dedicated **summary view** by default. The left rail, channels, kanban, timeline, and inspectors remain available so the coach can keep exploring; the summary is just the new "home".

The summary is generated once at run end via a single LLM call (see `agentic-design.md` → Summary loop) that consumes the run timeline and produces structured output. It is then rendered as a series of clearly-separated sections.

### Sections

**1. Outcome banner**
A bold headline at the top:

- ✅ "Goal reached: integration delivered on time with motivation above target."
- ⚠️ "Partial: integration delivered, but tech debt exceeded threshold."
- ❌ "Run ended: lead engineer quit (turn 14)."

Stoplight chips for each goal/exit criterion with their final value. When criteria include **`require_done_ids`**, chips or a sub-list should name each outcome id and its final state (done / not).

**2. Narrative summary**
3–5 paragraphs of generated prose: the arc of the run, the turning points, what worked and what didn't. Written as a coaching report, not a play-by-play. The coach's actions are central to this narrative.

**3. Coaching moments**
A horizontal scroll of cards. Each card represents one intervention the coach made (a DM thread, a rule edit, a parameter change, a vital nudge) judged to have had visible downstream effect — **positive, negative, or mixed**. Coaching practice requires honest mirrors; a moment where a well-intentioned nudge made things worse is at least as instructive as a win. Each card shows:

- Turn number and a one-line description ("turn 6 · Coach DMed Marcus about Priya's blocker").
- An **impact tag**: 🟢 helpful, 🟡 mixed, 🔴 harmful. Determined by the Summary loop based on downstream vital and ledger changes.
- Before/after on the most relevant vital(s) for the affected character(s).
- A short generated assessment, candid about both intent and effect ("Pushed Marcus publicly in #integration; he complied but his motivation dropped 20 points and his next-turn narrative shows resentment. Privately in DM might have served better.").
- "Show in timeline" link that jumps to the relevant turns.

This is the heart of the summary for coaching practice — it's where the coach learns what they did that mattered, for better or worse.

**4. Character arcs**
A grid of cards, one per significant character. Each card shows:

- The character's pixel portrait at start (left) and end (right), so expression changes are visible.
- Their starting and ending vitals, with sparklines between them.
- A one-line generated arc ("Started motivated, became overloaded by turn 8, recovered after the coach reassigned scope.").
- "View profile" link.

**5. Metrics over time**
Charts of the goal-relevant vitals/metrics across all turns, with vertical markers for each coaching action. The visual story of the run.

**6. Run stats**
A small row with: total turns, in-fiction duration, total cost, total messages, total agent calls. For the curious and for cost analysis.

**7. Coach reflection (optional)**
A free-text markdown area: "What did you learn?". Saved with the run, available on later replay. Prompts the coach to capture their own takeaway, which is often more valuable than the AI's assessment.

**8. Final report (deeper analysis, document view)**
Below the dashboard sections sits a long-form **Final Report** rendered as a markdown document. This is the deeper analysis a coach would want to read carefully — generated against the **coaching best-practices library** (see [`concept.md`](concept.md) → Coaching best practices). It includes:

- An honest assessment of how the coach performed, written as a debrief: what worked, what missed, what to try next time.
- Per-best-practice judgement: which patterns the coach applied well, which were missed or violated.
- **Suggested alternatives** at key moments — for the most consequential coaching moments (helpful and harmful), the report names a different approach that the best-practices library suggests would have plausibly worked better.
- A short "what to practise next" recommendation — 2–3 concrete patterns the coach could deliberately try in the next run.

The report has its own **document view** ("Open as document") that renders the markdown full-screen for comfortable reading, with a `📥 Download .md` action. The summary's data model includes the report's markdown so it's persisted with the run and not regenerated unless asked.

**9. Next actions**
Buttons / links at the bottom:

- ↺ **Replay step-by-step** (jumps to turn 1 in step-back mode).
- 🆕 **Run again** (creates a new run from the same scenario, fresh state).
- 📄 **Open Final Report** (full-screen document view).
- 📥 **Download report** (markdown).
- 🔙 **Back to sim picker**.

### Generation

The summary and the final report are generated together by the Summary loop when the run ends. Both are persisted; either can be re-generated on demand (e.g. after the best-practices library is tuned), with the original preserved as a snapshot. Costs are recorded under the run's totals.

If the summary call fails or is skipped (e.g. no API access), the UI shows the dashboard sections populated from deterministic data only — outcome banner, character arcs (vitals only, no generated narrative), metrics charts, run stats — and the Final Report section displays a "not generated" notice with a retry button.



A toggle (e.g. `D`) opens a dev panel:

- **Prompt inspector** — for any agent, see the exact prompt sent on any turn and the raw response. Diff between turns.
- **Cost & latency** — per turn, per agent, per call. Running totals and projections.
- **Engine trace** — every consult/invoke and its result, ordered.
- **Memory inspection** — current memory stream for any agent, including reflections, with importance scores.

This panel should not be hidden behind a menu — `D` toggle and it's there. It is essential for tuning.

## Frontend stack

Goals: avoid npm hell, stay lightweight, lean on browser-native HTML, reach for components only when needed.

### Recommendation: **HTMX + Alpine.js + Tailwind CSS**, served from FastAPI templates

- **HTMX** — server-rendered HTML with declarative swaps. The backend (FastAPI/Jinja) returns HTML fragments; HTMX swaps them into the page. Pairs naturally with our Python backend; no API+SPA split needed. SSE/WebSocket via `hx-ext="sse"` for live turn progress and streaming.
- **Alpine.js** — small reactive layer for client-side interactivity (drawer open/close, dropdowns, inline edit toggles, modals). About 15kb. Plays well with HTMX-swapped content.
- **Tailwind CSS** — utility-first styling. Available as a single standalone CLI binary (no Node required) or via CDN for prototyping.
- **No build step required for prototyping.** Everything can come from CDN. For production, the Tailwind CLI binary handles the only build.

### Small vanilla libraries we'll add as needed

- **EasyMDE** or **SimpleMDE** — markdown editor with preview and full-screen.
- **SortableJS** — drag-and-drop for the kanban.
- **Apache ECharts** (or **Chart.js**) — sparklines, gauges, progress bars beyond what CSS gives us.
- **TomSelect** or similar — `@handle` autocomplete in channel inputs.

All of these are vanilla JS, distributed as single files, no npm required.

### What we're not using and why

- **React / Vue / Svelte** — full SPA frameworks pull in npm, build pipelines, and a state-management problem. We don't need that to render dashboards and chat threads; HTMX gives us most of it for free.
- **Vite / Webpack / esbuild** — same reasoning. The Tailwind CLI is the only "build" step.
- **Component libraries (Radix, shadcn, Material)** — bring framework + ecosystem dependencies. We can roll the small set of components we need (drawer, modal, dropdown, tabs) on Alpine + Tailwind in a couple hundred lines total.

This means our `architecture.md`'s "React + Vite" line is replaced; updated below in the architecture changes.

## Mockup approach

Three stages, each cheaper than the last to throw away.

1. **Wireframes (now, in this doc).** ASCII / markdown sketches for layout. Already partly done above. Cheap to revise. Useful for arguing about structure.
2. **Generated visual mockups (next step).** Use a vision model to generate 3–5 illustrative screenshots: the runner with channel view, the kanban view, the inspector drawer, the timeline. These set the *aesthetic* — colour palette, type, lo-fi feel — without committing code. Easy to iterate on by re-prompting.
3. **Real HTML/CSS prototypes (after aesthetic is set).** Build the actual screens in the actual stack (HTMX+Alpine+Tailwind), wired to mock data. This *is* the start of the frontend; nothing is throwaway. Before any backend integration, we can have a clickable static prototype.

For the visual mockups, the model needs concrete prompts. A starter direction:

> "Screenshot of a 2003-era business chat application (vintage Microsoft Teams aesthetic) being used as the UI for a Japanese simulation game. Three-panel layout: left rail with channel list (`#general`, `#team-a`, `⚡incident-integration-d12`, `@priya`, `@marcus`); center showing a chat thread with **pixel-art character portraits** (32×32 sprites, JRPG style à la Persona / Princess Maker) as avatars next to each message; one character looks frustrated, another looks proud; messages have small emoji reaction rows underneath; right rail with goal stoplight (🟢), team vital bars and sparklines. Top bar shows 'turn 12' and an `advance turn` button. Cool blue/grey UI chrome with bright JRPG-palette accents on character art."

Variants needed: kanban view (work item cards with pixel-avatar owners), character profile (large pixel portrait + backstory + vitals time-series), inspector drawer over the channel view, timeline strip, and the sim picker.

I'd suggest generating one or two of these next, iterating on style, then moving to HTML.

## Open questions

- **Sprite production.** Generate per-character via vision model at scenario creation (most distinctive but slow/costly), or curate a small **standard sprite library** of pixel characters that scenarios assign to roles (instant, consistent, more genuinely retro)? Hybrid is plausible: ship a starter library; allow generated overrides per character.
- **Sprite resolution and frames.** 32×32, 48×48, or 64×64? Number of expressions per character (suggest 6–8 to start; can grow). Whether expressions are independent images or a single sprite sheet.
- **Expression rule defaults.** Confirm the default mapping from vitals to expression. Easy to tune later but worth a baseline.
- **Reaction set.** Confirm the six reactions, or trim/extend.
- **Ambient sound / animation.** Vintage games had bleeps and sprite idle animations. Probably no audio in v1; a tiny idle sway on avatars could add a lot of life cheaply. Worth deciding before sprite production.
- **Backgrounds.** Do channels / character profiles have pixel-art backgrounds (office, meeting room, server room) or just flat panels? More charm with backgrounds, more art to make.
