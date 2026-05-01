# Generated assets

Images listed in [`manifest.yaml`](manifest.yaml) are produced with OpenRouter and the model configured there (default `google/gemini-3.1-flash-image-preview`).

```bash
agile-harness assets list
agile-harness assets generate --dry-run
agile-harness assets generate
agile-harness assets generate --item default/happy --force   # tweak one prompt, regen
```

Outputs go under `harness/web/static/sprites/` and `harness/web/static/covers/` (gitignored). The manifest is the source of truth for prompts. Call logs: `assets/.log/asset_calls.jsonl`.

Generated files use a real extension from the response (`.png`, `.jpg`, or `.webp`); the UI resolves `/static/sprites/<set>/<id>.(png|jpg|…)`.

If avatars look like grey noise in the browser, older builds may have saved JPEG bytes with a `.png` name. Run `agile-harness assets generate --force --secrets …` to rewrite them, or delete `harness/web/static/sprites/` and regenerate.

Runner styling requires a Tailwind build after changing `components.css` / tokens: `./scripts/build_css.sh`, then hard-refresh the page.
