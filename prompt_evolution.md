# Prompt Evolution

## v1 — naive first pass

```
Here's a support ticket: {ticket_text}
Write a summary and a few reply drafts in different tones.
```

**Problems:**
- No fixed output schema → got a mix of prose, bullet lists, and occasional
  JSON depending on the ticket, impossible to parse reliably into a UI.
- "A few reply drafts in different tones" with no tone names specified →
  the model picked its own tone labels inconsistently ("casual", "brief",
  "professional", "warm" — different words each call for what was
  conceptually the same three tones).
- No knowledge-base grounding at all — the model would sometimes state
  specific policy details (like refund timeframes) that it invented rather
  than pulled from anywhere, which is dangerous for a tool whose output an
  agent might paste straight into a reply.

## v2 — fixed schema + named tones + KB context injected

Added:
- Strict JSON schema with `summary`, `variants` (array of `{tone, text}`),
  explicit tone names: `formal`, `empathetic`, `short`.
- The retrieved KB article (if any) is now injected into the user message
  before the ticket, with an instruction to stay factually consistent with
  it and not invent policy specifics beyond it.
- Instruction that variants must be "factually consistent with each other"
  — this was added after noticing the formal and empathetic variants would
  sometimes imply different things (e.g. one implying a refund is
  guaranteed, the other more hedged) purely from writing-style drift.

**Problems that showed up in testing:**
- Still no signal for when the agent should NOT trust the drafts at all —
  the model would produce three polished-sounding variants even for tickets
  involving account security or expert misconduct, with nothing flagging
  that these need a human decision before anything gets sent (see
  `human_judgment_cases.md` for why this matters).
- Retrieval failures (no good KB match) were invisible to the model — it
  would just write from general knowledge without any indication to the
  agent that no KB grounding was used, which matters for trust calibration.

## v3 (final) — flag_for_review + kb_used visibility

Added:
- `flag_for_review` boolean + `flag_reason` string, with explicit trigger
  conditions in the system prompt: account security/fraud, expert
  misconduct/legal/safety, no relevant KB match found, or a language the
  model isn't confident drafting in.
- `kb_used` boolean in the output so the agent-facing UI can visibly show
  "grounded in KB article X" vs. "no KB match — verify before sending",
  rather than presenting all drafts with equal implied confidence.
- Instruction to still draft the variants even when flagging for review —
  the agent gets a starting point either way, just with a visible warning
  attached, rather than an empty response that's less useful.

This is the version implemented in `assistant.py`.

## One concrete example of bad AI-output and how it was fixed

**Ticket (test case A08):** *"I want a refund but it's been 2 months since
I subscribed — is that even possible?"*

**What went wrong:** the keyword-overlap retrieval (see `README.md` for why
this approach was chosen) matched this to **KB05** (switching between
monthly/annual billing) instead of **KB02** (refund policy) — both articles
share billing-related vocabulary, and KB05 happens to score slightly higher
on raw keyword overlap even though it's the wrong article. In v2 of the
prompt, this produced a reply that vaguely discussed the wrong topic while
sounding confident, because the model trusted the retrieved KB context at
face value.

**Fix:** two changes, one in retrieval and one in the prompt:
1. Retrieval keeps a minimum score threshold (`MIN_SCORE` in
   `assistant.py`) so a weak/ambiguous match is less likely to be presented
   as ground truth — though this specific case (A08) still passes that
   threshold with the wrong article, since the overlap score is genuinely
   not low, just misdirected. This is flagged as a known retrieval
   limitation, not fully solved by the threshold alone (see
   `model_comparison.md`'s eval data for the measured 70% retrieval
   accuracy and this exact miss).
2. The prompt now explicitly allows the model to notice when the KB excerpt
   doesn't actually match the ticket's real question, rather than assuming
   whatever was retrieved is correct — "if the KB excerpt doesn't clearly
   address what the user is asking, say so in the summary rather than
   forcing the reply to use it." This doesn't fix the retrieval miss, but
   stops it from silently producing a confidently-wrong reply.

The deeper fix — better retrieval — is out of scope for this MVP's
keyword-overlap approach; see `README.md`'s retrieval section for the
tradeoff and what a production version would do differently.

## What I'd still iterate on with more time

- The retrieval failures cluster around ambiguous topic overlap
  (refund vs. billing-plan-change) — a real fix needs either embeddings
  (semantic similarity instead of keyword overlap) or a larger KB where
  articles are more clearly disambiguated by topic.
- I'd want a human agent to actually rate variant quality (not just schema
  validity) on a larger sample before trusting this in production — this
  eval intentionally does not auto-score prose quality, see README.md.
