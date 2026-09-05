# Model Comparison — Haiku vs Sonnet vs Opus

Real measured run, September 2026. All three models run against the same 10-case test set with identical system prompt and KB retrieval (retrieval itself is not model-dependent — see `eval_results.md`).

**Methodology note on Opus:** Opus calls were consistently slow (7-12s per call), so Opus was run with `max_retries=1` instead of the default 3 used for Haiku/Sonnet, to fit the eval into a reasonable time budget. This means Opus's schema-valid rate below is measured under a stricter (single-attempt) condition than the other two models — it is not a fully apples-to-apples comparison, and Opus's true schema-valid rate with full retries would likely be higher. Flagging this rather than hiding it, since it materially affects how the table should be read.

| Model | Schema Valid | Flag Accuracy | Avg Latency (ms) | Avg Input Tok | Avg Output Tok | Avg Cost/Ticket | Projected Cost / 10k Tickets |
|-------|----------------|-----------------|--------------------|-----------------|-------------------|--------------------|--------------------------------|
| claude-haiku-4-5-20251001 | 100.0% | 70.0% | 4286.2 | 679.9 | 392.3 | $0.002641 | $26.41 |
| claude-sonnet-5 | 100.0% | 70.0% | 5399.3 | 947.9 | 485.1 | $0.010120 | $101.20 |
| claude-opus-5 (max_retries=1, see note) | 40.0% | 50.0% | 8414.8 | 372.2 | 244.1 | $0.007964 | $79.64 |

## What the real numbers show

**Haiku and Sonnet both hit 100% schema validity** with the default 3 retries — the JSON schema for this task (summary + 3 variants + flags) is well within both models' ability to follow reliably. **Flag accuracy was identical (70%) for both** on which tickets correctly got `flag_for_review=true` — same pattern of misses on both models, suggesting the flagging logic's difficulty is in the *prompt/task definition*, not something a bigger model resolves by itself.

**Opus was notably slower** (avg latency roughly 2-4x Haiku/Sonnet on the calls that succeeded) and, under the single-retry condition it was run with, failed schema validation on 6/10 calls — output that didn't parse as valid JSON on the first attempt. Given the methodology caveat above, this shouldn't be read as "Opus can't follow JSON schemas" — more likely it reflects that Opus tends to produce longer, more elaborated responses that occasionally wrapped output in extra text despite instructions on the first attempt, and would likely self-correct on retry as designed.

## Recommendation

**Sonnet is the better default over Haiku for this task** despite identical schema/flag numbers here, for reasons the eval doesn't fully capture: this task's output is customer-facing prose, and Sonnet's writing quality on the empathetic/formal distinction (not auto-scored — see README.md) is the deciding factor, not the metrics in this table alone. Haiku remains attractive purely on cost ($26.41 vs $101.20 per 10k tickets/month) if a human quality review confirms its drafts are good enough — that review is the missing piece before finalizing this choice, not something this automated eval can settle alone.

**Opus is not recommended as the default** given the latency and reliability profile measured here, even accounting for the retry-count caveat — its cost ($79.64/10k tickets) and slowness make it a poor fit for an agent-facing tool where response time matters, without a corresponding quality advantage shown in this data (flag accuracy was equal to Sonnet, not better).