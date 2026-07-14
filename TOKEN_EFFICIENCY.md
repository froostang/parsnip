# Token-efficiency design

The canonical alpha constraints are
[`plugins/parsnip/skills/parsnip/references/token-efficiency.md`](plugins/parsnip/skills/parsnip/references/token-efficiency.md).
This document retains the broader product and measurement design.

## Requirement

Parsnip must not make an equivalent completed task cost the user more billable AI
usage by default. Shorter visible responses are not sufficient evidence: input,
output, repeated context, calibration, hidden generations, and unused prefetches
all count.

When usage metadata is unavailable, Parsnip must describe token neutrality as
unverified rather than assumed.

## Default strategy: lazy semantic skeleton

Generate only:

1. the current useful and safe snip; and
2. a very compact map of preserved branches.

Do not generate a full hidden answer, alternate phrasings, or speculative future
snips. Reuse stable context and provider prompt caching when available. Prefer
local, deterministic operations for revealing, grouping, or navigating content
that has already been generated.

Voice accommodation occurs inside the current generation from a compact style
hypothesis. It must not trigger a separate rewrite call or generate multiple voice
variants.

## Bounded semantic prefetching

Prefetching is an experiment, not the default. A useful version may generate a
small batch of semantic snips in one call, reveal the first, and cache the rest for
later **next** actions. This can reduce repeated input tokens but can waste output
tokens when the user changes direction or stops.

Only prefetch when:

- repeated **next** behavior predicts that the cached snips are likely to be used;
- the batch replaces future calls rather than adding a background call;
- generated and unused cached tokens remain inside the session's baseline budget;
- the content is not likely to change after user feedback; and
- the cache can be stored without resending it as prompt context on every turn.

Start with a prefetch window of zero. Test a window of two only after the lazy
version has a measured baseline. Never precompute multiple density variants merely
to make adaptation appear instant.

## Budget ledger

For each test, record when available:

- number of model calls;
- uncached input tokens;
- cached input tokens and their billed rate;
- visible output tokens;
- hidden or prefetched output tokens;
- unused prefetched tokens; and
- tokens required to reach the same completed outcome without Parsnip.

Compare equivalent outcomes, not merely the first response. Calibration and
control overhead belong to Parsnip's total.

## Budget behavior

- No background or speculative model calls by default.
- No claim of savings without usage evidence.
- If continued progressive turns are likely to exceed the comparable one-shot
  budget, disclose that before crossing it and offer the user a choice between the
  current pacing and a single consolidated response.
- Optimize dollar cost as well as token count when provider caching or pricing
  changes the relationship between them.

## Initial acceptance target

Across the five dogfood scenarios, Parsnip's median billable usage for the same
completed outcome must be no greater than the concise one-shot baseline. Any
scenario with higher usage must explain why and become an optimization case before
the project claims token neutrality.
