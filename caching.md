# Caching — do we need it here?

## Short answer: more relevant here than in Task 1, because the KB is
## reused across every single call.

## What's different from Task 1

In Task 1, there was nothing to cache on the input side beyond the system
prompt (~450 tokens) — every ticket was unique text with no shared context.

In Task 2, **every single call includes the same knowledge base content in
principle** — right now the code only injects the *one retrieved article*
into the prompt (not the whole KB), so the cacheable surface per-call is
smaller than it could be. But the **system prompt itself** (tone
definitions, JSON schema, flagging rules — roughly 400-500 tokens) is
identical on every call, exactly like Task 1.

## Should we cache the system prompt?

Same conclusion as Task 1: at ~450-500 tokens and moderate ticket volume,
the absolute savings are small in dollar terms (a few dollars per 10k
tickets/month) — see the calculation logic in Task 1's `caching.md`, which
applies identically here. Not worth the added complexity yet.

## Where caching WOULD matter more here than in Task 1

If a future version injects the **entire knowledge base** into every call
instead of doing keyword-based single-article retrieval (i.e. "give the
model everything and let it find the right part" — a legitimate simpler
alternative to retrieval, see README.md's retrieval tradeoffs section),
caching becomes much more valuable: the KB content would then be large,
static, and repeated on every call, which is exactly the profile Anthropic's
prompt caching is built for (up to ~90% off the cached portion). This is
flagged as a concrete reason to revisit caching if the retrieval approach
changes — see README.md's "what I'd do differently at scale" section.

## When to invalidate

Same principle as Task 1: cache invalidates automatically when the cached
content changes. If the KB is edited (an article's text is updated), any
cached version of that content should naturally fall out of the cache on
the next call with the new text — no manual invalidation needed as long as
the KB content itself is what's being cached (not a stale snapshot held
elsewhere in the code).

## Conclusion

Not implementing caching in this prototype, same reasoning as Task 1 at
current volume. The one thing worth flagging: **if the retrieval approach
changes to "inject the whole KB" (see README.md), caching stops being
optional and becomes a real cost lever** — worth revisiting together with
that architectural decision rather than as a separate afterthought.
