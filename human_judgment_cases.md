# Scenarios where human judgment is mandatory

These are ticket types where the agent must make the call themselves,
never send an AI-drafted variant without substantive review — and ideally
should be discouraged from even leaning on the draft as a starting point
for the decision itself (only for wording).

| Scenario | Why human judgment is mandatory |
|----------|-----------------------------------|
| **Account security / fraud** (unrecognized sessions, changed payment method, bookings the user didn't make) | The right response depends on an actual security investigation (was the account compromised, how, what else was accessed) that no amount of good drafting substitutes for. A well-written reply to the wrong security conclusion is actively harmful — it could reassure a user whose account is still compromised. |
| **Expert misconduct complaints** | These need to be logged in the Expert Conduct tracker (see `knowledge_base.json` KB04) regardless of how the ticket is resolved conversationally, and may involve a policy decision (refund, expert warning, expert removal) that's a judgment call about severity and pattern-matching against other complaints the agent may not see reflected in a single ticket's context. |
| **Legal threats or regulatory mentions** | Any reply that could be read as an admission of fault or a specific promise needs review by someone empowered to make that commitment on the platform's behalf — an AI-drafted "we're sorry, we'll fix this" is not something the platform should be bound by without a human deciding to send it. |
| **Refund requests outside standard policy** (see KB02) | The KB explicitly says these are evaluated case-by-case. A drafted reply can suggest tone and structure, but the actual yes/no on the refund is a policy judgment the assistant should never imply an answer to before the agent has decided. |
| **No KB match found, or retrieval confidence is low** | If the assistant had nothing solid to ground the reply in, the agent needs to verify the substance (not just polish the wording) before sending — this is exactly what `flag_for_review` + `kb_used=false` signals in the tool's output. |
| **Any ticket in a language the model flags as uncertain** | A grammatically fluent but subtly wrong reply in a language neither the model nor (potentially) the agent fully verifies is worse than an agent writing a shorter, correct reply themselves. |

## How this is marked in the interface

The `flag_for_review` boolean (see `assistant.py`, `prompt_evolution.md`)
is the technical mechanism. In a real UI, this would render as:

- A visible warning banner above the drafted variants: **"⚠️ Needs your
  judgment before sending"** with `flag_reason` shown as the specific
  reason (e.g. "Ticket mentions unauthorized account access").
- The variants are still shown (so the agent isn't starting from a blank
  page for the *wording*), but the send button for that ticket would
  require an extra explicit confirmation step, or route to a senior agent
  queue depending on severity — this mirrors Task 1's `needs_human`
  mechanism but applied to reply drafting instead of classification.
- Separately, `kb_used=false` is shown even on non-flagged tickets as a
  lighter-weight signal ("no KB article was used to ground this reply —
  double check the specifics") so agents calibrate trust per-ticket instead
  of treating every AI draft as equally grounded.
