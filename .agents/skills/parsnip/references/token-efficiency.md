# Token-efficiency constraints

## Baseline

Compare total billable usage for the same completed outcome, including model calls,
uncached and cached input, visible output, reminders, calibration, hidden output,
and unused prefetches. Mark neutrality **unverified** when provider usage metadata
is unavailable.

## Default

Use lazy generation with a zero-snip prefetch window. Generate the current snip and
a compact semantic map only. Reuse stable context or provider caching when
available, and prefer local deterministic navigation of already-generated content.

## Bounded prefetch experiment

Test a two-snip prefetch window only after measuring the lazy baseline. Prefetch
only when repeated **next** behavior predicts reuse, the batch replaces later calls,
unused output stays within the baseline budget, feedback is unlikely to invalidate
the content, and cached snips need not be resent each turn.

Never precompute multiple density or voice variants. If progressive turns are
likely to cross the comparable one-shot budget, disclose that before crossing it
and offer the user a consolidated response.
