# Web UI conventions

Mission-control, scenario-editor, and experiments UI. Stack: **FastAPI**, **Jinja2**, **HTMX**, **Alpine.js** (CDN), **Tailwind CSS** (standalone CLI build), and vendored **EasyMDE** for markdown editing.

Everything here is the source of truth for `harness/web/` templates, static assets, and JS.

## Layout and files

```text
harness/web/
  app.py              # FastAPI create_app
  run_reader.py       # load runs/batches from disk → Pydantic models
  resolve.py          # classify paths → URL for agile-harness view
  render.py           # markdown → HTML
  static/
    css/
      tokens.css      # :root design tokens only
      components.css  # @layer components (domain-prefixed classes)
      _input.css      # Tailwind entry (@import tokens, @tailwind …, components)
      app.css         # built output (gitignored; tests may drop a placeholder)
    js/
      runner-shell.js
      …
  templates/
    base.html
    …
tailwind.config.js    # repo root (or harness/web/)
scripts/build_css.sh
```

## CSS rules

1. **Tokens first** — colours, spacing scale, typography, radii, shadows live as CSS custom properties in [`harness/web/static/css/tokens.css`](../harness/web/static/css/tokens.css). Templates and `components.css` reference `var(--…)`; never hard-code hex in HTML.
2. **No inline `style=`** and **no `<style>` blocks** in templates.
3. **Tailwind** — use utilities for layout (`flex`, `grid`, `gap-*`, responsive). Theme in `tailwind.config.js` maps Tailwind tokens to the CSS variables in `tokens.css`.
4. **Component classes** — `kebab-case`, **domain prefix** (`msg-`, `kanban-`, `vital-`, `topbar-`, `rail-`). Use a component class when **≥ 3** repeating property pairs; otherwise utilities only. Inner elements: BEM-lite (`__author`, `--coach`).

## Alpine.js

Follow the same patterns as a small-Alpine + server-rendered app:

- **Named factory per component** in `static/js/<name>.js` returning a plain object. Example: `function runnerShell() { return { currentView: 'channels', … }; }`
- **Scope with `x-data="runnerShell()"`** on the shell. Swapped HTMX fragments use `x-data` on their root if they need local state.
- **No globals** except the factory names. No `onclick=`. No `document.createElement` for UI.
- **Modifiers**: `@click.outside`, `@keydown.escape.window`, `@submit.prevent`, `.debounce`.
- **HTMX + Alpine**: long-lived state on the **shell** (`runnerShell` or `Alpine.store('runner', …)`). Partials returned by HTMX should not own global state.

## Naming

| Kind | Convention |
|------|------------|
| Template files | `snake_case.html` partials under `templates/partials/` |
| HTMX target ids | stable, prefixed: `#channel-view`, `#kanban-view` |
| Routes | `/` (run list), `/runs/{run_id}`, `/runs/{batch_id}/{run_id}`, `/experiments`, `/experiments/{batch_id}` |
| CSS classes | `domain-thing`, `domain-thing--modifier`, `domain-thing__part` |
| Alpine factories | `camelCase()` |

## a11y

Focus states on interactive controls (`focus-visible:ring` or component equivalents). Channels/Vitals labels must be readable in the right rail.

## Scenario editor conventions

- Route surface:
  - `/scenarios/{slug}/edit` is the single editor shell.
  - `/partials/scenario/{slug}/section/{section}` serves center-stage section swaps.
  - Object edits are `POST /scenarios/{slug}/edit/*` and return the updated partial HTML.
- Markdown fields (`setting.md`, character backstory) use EasyMDE on `<textarea data-easymde="markdown">`.
- YAML fields (`process.yaml`, `best_practices.yaml`) stay plain textareas. On parse errors, return HTTP 422 and render a line-marked preview with `.yaml-error-line`.
- Mid-run lock model:
  - Locked: initial conditions (work-item seed), starting vitals, character core profile fields, backstory.
  - Editable: process/goals/parameters/channels/teams/model/sprite fields.
  - Editable changes during a live run append `coach_edit` timeline rows with `effective_turn = world.turn + 1`.
- User-facing copy uses **Make a copy**; `/scenarios/{slug}/fork` remains a compatibility alias that redirects to `/copy`.

## Build CSS

```bash
./scripts/build_css.sh          # one-shot
./scripts/build_css.sh --watch  # dev
```

If `harness/web/static/css/app.css` is missing, `agile-harness serve` still starts; layout falls back until you run the build (tests inject a tiny placeholder `app.css`).

## See also

[`architecture.md`](architecture.md) — FastAPI + HTMX + Alpine + Tailwind.  
[`ui-design.md`](ui-design.md) — mission control layout and JRPG/Teams aesthetic.
