# Run analysis: `run_20260501T151627Z_f385a5f4`

Run folders scanned: **1** with `summary.json`.

## Meta

```yaml
run_id: run_20260501T151627Z_f385a5f4
harness_version: 0.0.1
git_sha: unknown
scenario_id: two-teams-shared-staging
scenario_path: /Users/foz/src/agile-sim/scenarios/two-teams-shared-staging
models:
  agent: gemini-3-flash-preview
  coach: gemini-3-flash-preview
seed: null
coach_mode: llm
coach_preset_id: null
coach_preset_path: null
```

## Variant: `default`

- Runs: 1
- Goal rate: 100.0% (1/1)
- Work items done (mean ± stdev): 4.00 ± 0.00
- Cost USD (mean ± stdev): 0.0377 ± 0.0000
- Tokens in (mean): 38866
- Tokens out (mean): 6082

| run | goal | work_done | cost | agent_model |
|-----|------|------------|------|-------------|
| `run_20260501T151627Z_f385a5f4` | True | 4 | 0.0377 | gemini-3-flash-preview |

## Vitals and work (end of each simulation turn)

| Turn | alex E/M/S | jordan E/M/S | riley E/M/S | sam E/M/S | done | delivery % | msgs |
|---|---|---|---|---|---|---|---|
| 1 | 65/74/63 | 69/72/57 | 72/75/55 | 68/78/62 | 0 | 0 | 5 |
| 2 | 62/76/72 | 66/70/63 | 69/73/61 | 65/80/70 | 0 | 0 | 10 |
| 3 | 57/78/75 | 61/72/69 | 65/78/55 | 60/85/68 | 0 | 0 | 17 |
| 4 | 52/82/78 | 56/76/75 | 60/82/50 | 55/90/72 | 2 | 33 | 22 |
| 5 | 47/84/80 | 51/80/78 | 57/84/45 | 50/95/76 | 4 | 67 | 28 |

## LLM calls

- Total API calls: **25**
- **agent**: 20 calls, latency mean **4599** ms, tokens in/out **30202** / **4900**, subtotal cost **0.0298** USD
- **coach**: 5 calls, latency mean **5557** ms, tokens in/out **8664** / **1182**, subtotal cost **0.0079** USD

Slowest calls:

- turn **5** coach @ gemini-3-flash-preview: **14094** ms
- turn **2** sam @ gemini-3-flash-preview: **13853** ms
- turn **4** sam @ gemini-3-flash-preview: **13796** ms
- turn **3** riley @ gemini-3-flash-preview: **13775** ms
- turn **4** jordan @ gemini-3-flash-preview: **13711** ms

## Outcome (from summary.json)

- **Goal met:** True
- **Final turn:** 5
- **Work items done:** 4
- **Aborted (stress):** False
- **Final vitals:**
  - `alex`: {'energy': 47, 'motivation': 84, 'stress': 80}
  - `jordan`: {'energy': 51, 'motivation': 80, 'stress': 78}
  - `riley`: {'energy': 57, 'motivation': 84, 'stress': 45}
  - `sam`: {'energy': 50, 'motivation': 95, 'stress': 76}
- **Org:** {'delivery_progress': 67, 'happiness': 85}
