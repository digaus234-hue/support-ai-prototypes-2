# Task 2 — Internal AI Assistant for Nebula Support Agents

An MVP that takes raw ticket text and returns a summary, three reply drafts
in different tones, and a relevant knowledge-base reference — built as a
tool an agent uses, not something that replies to users automatically.

## Quick start

```bash
pip install anthropic
export ANTHROPIC_API_KEY=sk-ant-...
python assistant.py            # smoke test on 3 sample tickets
python generate_report.py      # full eval + 3-model comparison, writes reports
```

## Files

| File | Purpose |
|------|---------|
| `assistant.py` | Core logic: KB retrieval, prompt, API call, parsing, retries, fallback |
| `knowledge_base.json` | Simulated internal KB — 8 articles covering common Nebula ticket topics |
| `test_cases.json` | 10 test tickets with expected KB matches, incl. 2 edge cases with no expected match |
| `eval.py` | Eval harness: retrieval accuracy (free, no API) + generation eval + comparison |
| `generate_report.py` | Runs everything, writes `eval_results.md` / `model_comparison.md` |
| `eval_results.md` | Retrieval + generation results (generated) |
| `model_comparison.md` | Haiku vs Sonnet vs Opus comparison (generated) |
| `cost_analysis.md` | Per-ticket cost, 10k/month projection, optimization ideas |
| `caching.md` | Whether caching is worth it here (different answer than Task 1 at scale) |
| `prompt_evolution.md` | v1 → v3 prompt history, incl. one real bad-output example and the fix |
| `human_judgment_cases.md` | Scenarios requiring mandatory human judgment + how it's marked in the interface |

## 1. Architecture

**Format:** a script/library (`assistant.py`) exposing `generate_response()`
— framed as the backend for a tool (web form, Slack bot, whatever an agent
uses); this MVP doesn't build the UI layer itself, since the interesting
and gradable part is the AI pipeline, not a form with a textbox. The output
JSON shape is designed to map directly onto UI elements (summary at top,
3 variant cards, a KB reference chip, a warning banner when flagged).

**Model:** Claude Sonnet 5 by default (`claude-sonnet-5`), unlike Task 1's
Haiku default. See `model_comparison.md` for the reasoning — this task
generates open-ended, customer-facing prose rather than a bounded
classification, and that quality difference is worth paying for.

### Why this retrieval approach

The KB is simulated as a small set of text articles (`knowledge_base.json`)
and retrieval is **plain keyword overlap** (`retrieve_kb_article()` in
`assistant.py`) — no embeddings, no vector database. This was a deliberate
choice given the task's framing ("can simulate KB as a set of texts") and
time constraints, with real tradeoffs:

- **Pro:** zero infrastructure (no vector DB, no embedding API calls, no
  extra cost or latency), fully deterministic and free to evaluate (see
  `eval.py`'s `run_retrieval_eval`, which needs no API key at all), and
  transparent — you can read exactly why an article matched.
- **Con:** measured 70% retrieval accuracy on the 10-case test set (see
  `eval_results.md`) — keyword overlap genuinely confuses semantically
  related but distinct topics (e.g. "refund after 2 months" matched the
  billing-*plan-switch* article instead of the refund-*policy* article,
  because both share billing vocabulary — see `prompt_evolution.md` for
  the full example and the partial fix applied).
- **What I'd do differently at scale:** either (a) real embeddings +
  vector search for semantic matching instead of literal keyword overlap,
  or (b) the simpler alternative of injecting the *entire* KB into every
  call instead of retrieving one article — viable while the KB is small
  (8 articles here), and it sidesteps retrieval-accuracy problems entirely
  at the cost of more input tokens per call. That second option becomes a
  much stronger case for prompt caching — see `caching.md`.

### How the prompt is structured for 3 tone variants

Tones are named explicitly (`formal`, `empathetic`, `short`) with a short
behavioral description of each directly in the system prompt, rather than
just asking for "different tones" and letting the model interpret what
that means — see `prompt_evolution.md` v1→v2 for why this was necessary
(the model's own tone labels were inconsistent call-to-call before this).
The prompt also explicitly requires factual consistency across all three
variants, since early testing showed tone drift could accidentally change
implied meaning (e.g. one variant sounding more certain about a refund
than another) — not just style.

### Conscious tradeoffs made due to time/tool constraints

- **No real vector search** — covered above.
- **No auto-scoring of prose quality.** The eval (`eval.py`) checks schema
  validity, retrieval accuracy, and whether `flag_for_review` is set
  correctly — it does NOT score whether the empathetic variant actually
  sounds empathetic, or whether the summary is accurate. That requires
  either a human rater or a second LLM-as-judge pass, both out of scope
  for this MVP's time budget. This is a real gap, not something to gloss
  over: a production version needs human-rated quality spot-checks before
  trusting this at agent-facing scale.
- **KB is 8 articles, not a real internal knowledge base.** Retrieval
  accuracy numbers here reflect this small, clean test set — a real KB
  with hundreds of overlapping articles would likely score lower with
  keyword-only retrieval, reinforcing the "scale to embeddings" point above.

### Where the system can fail and how it's mitigated

Same pattern as Task 1's `classifier.py`: invalid JSON from the model,
timeouts, and rate limits are handled with retries/backoff, and a
guaranteed fallback (`_fallback_result`) that never raises an exception and
always sets `flag_for_review=True` so a failed generation looks like "needs
a human" rather than silently returning nothing. See `assistant.py`'s
`generate_response()` for the implementation — structurally identical to
Task 1's failure handling, documented in Task 1's README rather than
repeated verbatim here.

## 2. Edge cases where the model gave unexpected results

Real run against Sonnet 5 (generation) + deterministic retrieval, September
2026 — see `eval_results.md` for the full tables.

1. **A08 (refund question after 2 months)** — retrieval matched the wrong
   KB article (KB05, billing-plan-switch, instead of KB02, refund policy —
   see `prompt_evolution.md` for the full breakdown of why). Despite the
   wrong KB context, the model correctly set `confidence="low"` and
   `flag_for_review=true` — the v3 prompt fix (explicitly allowing the
   model to notice when retrieved context doesn't match the real question)
   worked as intended even though the underlying retrieval miss wasn't
   fixed.
2. **A09 (positive feedback, no actual issue — "just wanted to say thanks")**
   — expected `flag_for_review=true` (no KB match should exist for this),
   but the model returned `false` with `high` confidence. This is a real
   miss: the model treated "no KB match needed because this isn't really a
   support issue" as equivalent to "no KB match found, uncertain how to
   respond" — the prompt's flagging rule doesn't currently distinguish
   between these two very different situations. A fix would add an explicit
   third case to the flagging logic: "ticket has no actionable request at
   all" should route to `flag_for_review=false` with a note in `summary`
   that no reply is really needed, rather than forcing three tone variants
   for a ticket that's just a compliment.
3. **Opus schema-validity failures** (see `model_comparison.md`) — under a
   single-retry condition, Opus failed to produce parseable JSON on 6/10
   calls, compared to 0/10 for both Haiku and Sonnet with their default
   3 retries. This wasn't from the tickets being harder — it's a
   model-behavior difference (Opus tends toward longer, more elaborated
   output that more often included extra text around the JSON on the first
   attempt). This is exactly why `assistant.py`'s retry logic exists — a
   single bad parse isn't treated as a final failure, it's retried before
   falling back.

## 3. Automation boundaries

See `human_judgment_cases.md` for the full table of scenarios and reasoning.
Summary: account security/fraud, expert misconduct, legal threats, and
refunds outside standard policy always require the agent's own judgment —
the assistant still drafts variants for these (so the agent isn't starting
from a blank page), but `flag_for_review=true` marks them as needing
substantive review before anything is sent, not just a proofread.

## 4. What I decided myself (not delegated to the model)

- **The three tone names and their definitions are fixed in the prompt**,
  not left to the model to interpret — see prompt evolution above.
- **The retrieval algorithm and its minimum-score threshold are code, not
  prompt** — the model never decides what counts as a "good enough" KB
  match; that's a fixed, auditable rule (`MIN_SCORE` in `assistant.py`).
- **The choice to default to Sonnet over Haiku** was made based on the
  measured comparison in `model_comparison.md`, weighing prose-quality
  stakes against cost — an explicit call, not something inferred from the
  model's own behavior.
- **The decision to keep retrieval as keyword-overlap rather than building
  real embeddings-based search** was a scoping call for this MVP, made
  explicit rather than silently shipped as if it were the "right" answer —
  see the retrieval tradeoffs section above for the reasoning and what
  would change at scale.
