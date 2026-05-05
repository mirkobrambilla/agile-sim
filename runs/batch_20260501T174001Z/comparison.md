# Experiment Comparison: `batch_20260501T174001Z`

## Executive Summary
*   **LLM Coaching is highly effective:** The `llm_coach` variant achieved a 100% goal completion rate, compared to only 60% for `no_coach`.
*   **Stress Resilience:** `llm_coach` eliminated stress-related aborts (0%), whereas 40% of `no_coach` runs failed due to stress.
*   **Throughput:** Coaching nearly doubled the mean work done (2.9 vs 1.6 items).
*   **Cost Trade-off:** Improved performance comes at a ~72% increase in mean cost ($0.048 vs $0.028).
*   **Efficiency:** Coached runs took slightly longer on average (6.4 turns vs 5.9), but this is skewed by the fact that failed `no_coach` runs aborted early (Turn 5).
*   **Reliability:** `llm_coach` showed much lower variance in work output (stdev 0.30 vs 1.36).

## Variant Ranking

| Variant | Goal Rate | Stress Abort Rate | Mean Work Done | Mean Cost (USD) |
| :--- | :--- | :--- | :--- | :--- |
| **llm_coach** | **100%** | **0%** | **2.9** | $0.0484 |
| **no_coach** | 60% | 40% | 1.6 | $0.0281 |

**Caveats:**
*   Sample size is small ($n=10$ per variant).
*   The `no_coach` mean cost is artificially low because 40% of the runs aborted early, consuming fewer tokens.

## Patterns & Observations

### 1. Stress Management
The primary differentiator is the **stress_abort_rate**. In the `no_coach` variant, every failure (4/10) was a direct result of a stress abort at exactly Turn 5. The `llm_coach` variant appears to successfully mitigate agent stress, allowing the simulation to proceed to completion.

### 2. Work Consistency
*   **llm_coach:** Highly stable. 90% of runs completed exactly 3 work items.
*   **no_coach:** Bimodal distribution. Successful runs completed 2–3 items, but failures completed 0 items. Coaching ensures a floor for productivity.

### 3. Cost/Token Profile
The coaching intervention increases token usage significantly (Mean In: 51k vs 29k). This suggests the coach agent is injecting substantial context or frequent interventions into the message history to maintain alignment and reduce stress.

## Next Experiments

1.  **Cost Optimization:** Test a "Periodic Coach" variant where the coach only intervenes every $N$ turns or only when stress metrics cross a specific threshold, rather than every turn.
2.  **Coach Model Ablation:** Swap `google/gemini-3-flash-preview` for a smaller/cheaper model (e.g., Gemini Flash 1.5 or Haiku) for the coach role specifically to see if coaching logic requires high reasoning capabilities.
3.  **Stress Ceiling Test:** Increase the scenario difficulty (e.g., more concurrent tasks or tighter deadlines) to find the "breaking point" of the `llm_coach` variant.
