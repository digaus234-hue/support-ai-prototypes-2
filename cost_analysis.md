# Cost Analysis

## Why this is more expensive per-ticket than Task 1

Task 2 generates three full reply drafts plus a summary — much more output
than Task 1's small fixed JSON classification — so output tokens dominate
cost here, unlike Task 1 where input (the system prompt) was the bigger
share.

## Per-ticket cost (measured — see `model_comparison.md` for the real run)

Retrieval itself (`retrieve_kb_article`) costs nothing — it's local keyword
matching, no API call. Only the generation step (summary + 3 variants)
calls the model.

Real numbers are written into `model_comparison.md` by `generate_report.py`.
As a rough estimate before that run: with ~500 input tokens (system prompt +
ticket + KB excerpt) and ~400-600 output tokens (summary + 3 drafted
replies), expect roughly 3-5x the per-ticket cost of Task 1's classification
on the same model, simply from output length.

## Projected cost at 10,000 tickets/month

See `model_comparison.md` for the actual measured table. Given Task 2
defaults to Sonnet (not Haiku — see `model_comparison.md` for why), expect
this to land in the same rough range as Task 1's Sonnet numbers scaled up
by the larger output size, likely in the $80-150/month range at 10k
tickets/month. This is still a small line item compared to the agent time
saved if the drafts genuinely cut response-writing time.

## Ideas to reduce cost without losing quality

1. **Generate 2 variants instead of 3 for low-complexity tickets.** Simple,
   clearly-scoped tickets (e.g. "how do I switch billing plans") probably
   don't need a distinct "empathetic" variant — that tone matters most for
   tickets involving frustration or a problem, not neutral how-to questions.
   This could be a cheap pre-classification step (reusing Task 1's
   classifier!) rather than always generating all 3.
2. **Batch API for a nightly "pre-draft common tickets" job**, if the
   support team has a backlog of similar recurring tickets — not useful for
   real-time agent assistance, but could pre-generate drafts for a queue at
   50% off.
3. **Cap output length more aggressively for the "short" variant** — right
   now all three variants share one `max_tokens=800` budget; a tighter
   explicit word-count instruction for the short variant specifically would
   reduce output tokens without hurting the formal/empathetic variants.
4. **Route to Haiku for tickets that already have a very strong KB match**
   (high retrieval score) and reserve Sonnet for weak/no-match tickets where
   writing quality without KB grounding matters more. This is the mirror
   image of Task 1's confidence-based routing.
