# Run analysis: `run_20260501T145051Z_2298ecc1`

Run folders scanned: **1** with `summary.json`.

## Meta

```yaml
run_id: run_20260501T145051Z_2298ecc1
harness_version: 0.0.1
git_sha: unknown
scenario_id: two-devs-and-a-pm
scenario_path: /Users/foz/src/agile-sim/scenarios/two-devs-and-a-pm
models:
  agent: google/gemini-3-flash-preview
  coach: google/gemini-3-flash-preview
seed: null
```

## Variant: `default`

- Runs: 1
- Goal rate: 100.0% (1/1)
- Work items done (mean ± stdev): 4.00 ± 0.00
- Cost USD (mean ± stdev): 0.0264 ± 0.0000
- Tokens in (mean): 26411
- Tokens out (mean): 4413

| run | goal | work_done | cost | agent_model |
|-----|------|------------|------|-------------|
| `run_20260501T145051Z_2298ecc1` | True | 4 | 0.0264 | google/gemini-3-flash-preview |

## Vitals and work (end of each simulation turn)

| Turn | lin E/M/S | marcus E/M/S | priya E/M/S | done | delivery % | msgs |
|---|---|---|---|---|---|---|
| 1 | 73/78/62 | 63/73/54 | 65/78/60 | 0 | 0 | 5 |
| 2 | 70/83/58 | 59/78/48 | 60/80/63 | 1 | 20 | 11 |
| 3 | 67/88/54 | 55/80/53 | 56/82/65 | 2 | 40 | 14 |
| 4 | 63/93/51 | 50/82/55 | 52/84/70 | 3 | 60 | 18 |
| 5 | 58/98/59 | 45/85/59 | 47/88/73 | 4 | 80 | 23 |

## LLM calls

- Total API calls: **20**
- **agent**: 15 calls, latency mean **3013** ms, tokens in/out **18513** / **3515**, subtotal cost **0.0198** USD
- **coach**: 5 calls, latency mean **9425** ms, tokens in/out **7898** / **898**, subtotal cost **0.0066** USD

Slowest calls:

- turn **3** coach @ google/gemini-3-flash-preview: **16288** ms
- turn **5** coach @ google/gemini-3-flash-preview: **13865** ms
- turn **1** lin @ google/gemini-3-flash-preview: **13222** ms
- turn **1** coach @ google/gemini-3-flash-preview: **12715** ms
- turn **3** marcus @ google/gemini-3-flash-preview: **2727** ms

## Outcome (from summary.json)

- **Goal met:** True
- **Final turn:** 5
- **Work items done:** 4
- **Aborted (stress):** False
- **Final vitals:**
  - `lin`: {'energy': 58, 'motivation': 98, 'stress': 59}
  - `marcus`: {'energy': 45, 'motivation': 85, 'stress': 59}
  - `priya`: {'energy': 47, 'motivation': 88, 'stress': 73}
- **Org:** {'delivery_progress': 80, 'happiness': 90}
