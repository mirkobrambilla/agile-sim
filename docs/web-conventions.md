# Web UI conventions

Read-only **mission control** and **experiments** UI for finished runs. Stack: **FastAPI**, **Jinja2**, **HTMX**, **Alpine.js** (CDN), **Tailwind CSS** (standalone CLI build).

Everything here is the source of truth for `harness/web/` templates, static assets, and JS.

## Layout and files

```
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

## Build CSS

```bash
./scripts/build_css.sh          # one-shot
./scripts/build_css.sh --watch  # dev
```

If `harness/web/static/css/app.css` is missing, `agile-harness serve` still starts; layout falls back until you run the build (tests inject a tiny placeholder `app.css`).

## See also

[`architecture.md`](architecture.md) — FastAPI + HTMX + Alpine + Tailwind.  
[`ui-design.md`](ui-design.md) — mission control layout and JRPG/Teams aesthetic.
