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

On a chat surface where every reveal requires another model call, use one
continuation as a conservative budget proxy. After that continuation, default the
next content request to a compact synthesis unless the user explicitly chooses to
keep pacing. Describe this as a usage guard, not as proof of neutrality.

When a host supports capture-and-carve, compare its one complete authoring turn
against the same concise one-shot baseline. Count that authoring turn in full, but
count direct exact-span navigation as local only when the client actually bypasses
the composer and starts no Codex turn. Do not infer savings from fixture tests.

## Bounded prefetch experiment

Test a two-snip prefetch window only after measuring the lazy baseline. Prefetch
only when repeated **next** behavior predicts reuse, the batch replaces later calls,
unused output stays within the baseline budget, feedback is unlikely to invalidate
the content, and cached snips need not be resent each turn.

Never precompute multiple density or voice variants. If progressive turns are
likely to cross the comparable one-shot budget, disclose that before crossing it
and offer the user a consolidated response.
