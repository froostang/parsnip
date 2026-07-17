# Token-efficiency design

The canonical alpha constraints are
[`plugins/parsnip/skills/parsnip/references/token-efficiency.md`](../../plugins/parsnip/skills/parsnip/references/token-efficiency.md).
This document retains the broader product and measurement design.

## Requirement

Parsnip must make AI-usage tradeoffs visible and avoid unnecessary model turns.
Exact local navigation over already-authored content should add no model usage;
new reasoning may require another turn and may cost more than a concise one-shot
answer. Shorter visible responses are not evidence of savings: input, output,
repeated context, calibration, hidden generations, and unused prefetches all
count.

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

The executable measurement path is
[`evals/run_usage_eval.py`](../../evals/run_usage_eval.py). It uses isolated
one-shot and Parsnip Codex sessions, captures JSONL usage per turn, aggregates
progressive turns, and keeps raw evaluation artifacts outside the public
repository. Synthetic prompts, controls, and predeclared rubrics live in
[`evals/usage_cases.json`](../../evals/usage_cases.json). Cost estimates require
run-time rates rather than a committed price table.

## Budget behavior

- No background or speculative model calls by default.
- No claim of savings without usage evidence.
- After one continuation call, warn that another generated snip may exceed a
  comparable one-shot answer. Default the next content request to one compact
  synthesis unless the user explicitly chooses to keep pacing.
- Optimize dollar cost as well as token count when provider caching or pricing
  changes the relationship between them.

The continuation guard is a conservative proxy. It reduces avoidable turns but
does not prove token or dollar neutrality.

## First measured cohort

The 2026-07-15 synthetic five-case run achieved answer-quality non-inferiority:
Parsnip passed every rubric item, while one baseline decision-comparison item was
partial. The skill-only progressive path used 1,290,020 reported tokens against
67,018 for concise one-shot baselines: a 19.25× aggregate ratio and 22.34× median
case ratio. Cached input dominated Parsnip usage (1,069,312 tokens), showing that
short visible snips did not avoid repeated-context cost. Dollar cost remains
unverified because no model-specific rate card was supplied.

This fails the original token-neutrality target. Public token- or cost-saving
claims remain blocked. Product testing may continue only with that tradeoff
disclosed and measured alongside user benefit.

The [`local answer buffer`](local-buffer.md) is the first implementation of that
runtime boundary. It stores one model-authored capsule and supports direct local
navigation, but it remains opt-in until a client-facing control path and paired
usage evaluation demonstrate that navigation actually bypasses model turns in the
target surface.

The guarded rerun held every Parsnip path to three assistant turns and retained
answer-quality non-inferiority, with Parsnip again passing every rubric item.
Reported Parsnip usage fell to 700,313 tokens, a 45.7% reduction, while the
aggregate ratio fell to 10.49× and the median case ratio to 10.51×.
Using the configured GPT-5.6 Sol model's 2026-07-15 API rates as a comparison proxy
($5/M uncached input, $0.50/M cached input, and $30/M output), the estimated cohort
ratio improved from 9.95× to 6.21×. This is not invoice-equivalent: the traces do
not identify cache writes, service-plan billing, or other fees.

The guard is therefore worth retaining as a loss-control mechanism, but it does
not clear the release blocker. Because the guarded scripts intentionally removed
late turns, that rerun demonstrates the earlier-consolidation workflow rather than
isolating the cost of the guard text itself; the already three-turn decision case
became slightly more expensive under normal sampling variance.

## Buffered four-arm cohort

The 2026-07-15 four-arm rerun compared concise one-shot, ordinary matched
multi-turn, Parsnip progressive, and one GPT-5.6 Sol-authored capsule followed by
direct local navigation. The synthetic rubric review found all 30 items present in
ordinary progressive, Parsnip progressive, and buffered outputs. The one-shot arm
had 29 passes and one partial because its planning answer allocated 16 hours in
Week 6 despite the 12-hour weekly cap.

| Condition | Reported tokens | Ratio to one-shot | Rate proxy | Ratio to one-shot |
|---|---:|---:|---:|---:|
| Concise one-shot | 66,974 | 1.00× | $0.1940 | 1.00× |
| Ordinary progressive | 418,565 | 6.25× | $0.7174 | 3.70× |
| Parsnip progressive | 704,225 | 10.51× | $1.2095 | 6.23× |
| Parsnip buffered | 458,492 | 6.85× | $1.0168 | 5.24× |

All fourteen post-capsule controls ran through the direct local launcher and added
no Codex turns. Buffering reduced reported tokens by 34.9% and the rate proxy by
15.9% relative to Parsnip progressive, but remained more expensive than ordinary
progressive chat and far above one-shot. The capsule's single Codex turn still
contains model/tool-planning cycles; authoring and validating a rich graph, rather
than local navigation, is now the main optimization target. The rate proxy uses
the 2026-07-15 API rates and is not invoice-equivalent.

The next experiment adds a lean capsule schema. It removes the separately authored
final synthesis, stores each section as a brief plus a non-repeating extension, and
constructs **full** through deterministic concatenation. Its evaluation prompt
calls the schema-bearing MCP tool directly without rereading Parsnip or its capsule
reference, isolating answer-authoring cost from skill-loading overhead.

The first same-build learning-case smoke retained all six rubric requirements. It
used 44,335 reported tokens and a $0.1235 rate proxy: 3.34× and 3.20× the one-shot
condition. Rich buffering used 101,785 tokens and $0.1953, so the lean path reduced
authoring tokens by 56.4% and the proxy by 36.8%. It also beat ordinary progressive
chat on reported tokens (44,335 versus 82,828), but not on the rate proxy ($0.1235
versus $0.0873) because the lean answer emitted more uncached/output work. Treat
this as a promising single-case result, not a cohort pass.

## Capture-and-carve experiment

The next implementation removes capsule authoring entirely. A small app-server
client starts one ephemeral read-only turn with the Parsnip buffer MCP disabled,
captures the authoritative final Markdown response, and stores exact section
spans locally. Navigation is deterministic and `full` restores canonical visible
text without concatenation or semantic rewriting. An explicit command-line
confirmation guards the only model-bearing operation.

Local fixture tests verify the protocol boundary, safe fallback, file permissions,
expiry, section navigation, and character-for-character full response. No live
model call was made for this implementation because the current objective is to
conserve the user's remaining weekly usage. The acceptance target remains open
until a future paired cohort compares this path with concise one-shot and ordinary
progressive baselines.

The usage harness can now isolate `baseline` and `capture` with repeated
`--condition` flags. The capture arm requires app-server token accounting and
verifies the exact-response hash after local consolidation, so the next validation
step needs only two model turns for one case rather than rerunning every historical
condition.

The 2026-07-16 learning-case smoke used those two model turns. Both outputs passed
all six predeclared content requirements. The concise baseline reported 12,775
input tokens, 8,960 cached input tokens, and 404 output tokens; capture reported
12,865 input, 8,960 cached input, and 573 output. Reported totals were 13,179 and
13,438 respectively, making capture 1.020× baseline. Exact full-response hashing
passed and subsequent navigation remained local.

Using the project's earlier $5/M uncached-input, $0.50/M cached-input, and $30/M
output comparison proxy—not an invoice or current-price claim—the conditions were
$0.0357 and $0.0412, a 1.155× capture ratio. That misses the provisional 1.10× cost
gate because capture emitted 169 more output tokens.

The smoke also exposed a format-contract failure: the response used `###` headings
instead of requested `##` reveal boundaries, and the permissive parser carved an
awkward setup fragment. The parser now treats only explicit `##` headings as safe
boundaries and otherwise returns one indivisible answer. The prompt also forbids
incomplete first-block setup. Treat this smoke as a functional and content pass but
an efficiency/format iteration, not a release pass.

The follow-up **compiled capture** implementation makes that contract mechanical.
It preserves the baseline request verbatim as user input and adds a deterministic
developer-instruction sidecar with a 450-visible-token target, optional drift
compatibility hints, and exact invisible section/detail markers. The store removes
only recognized marker lines, hashes both raw and canonical responses, and rejects
malformed release structures to one indivisible block. The paired harness now
requires marker-protocol compliance in addition to canonical full-response
integrity. Nineteen runtime fixtures and sixteen harness tests pass; no new live
model call was used while implementing it.

The subsequent same-case paired rerun passed all six requirements on manual
review. Baseline reported 12,775 input tokens, 8,960 cached input tokens, and 458
output tokens; compiled capture reported 12,950 input, 8,960 cached input, and 513
output. Totals were 13,233 and 13,463, a 1.017× capture ratio. The exact canonical
hash, compact marker protocol, and three zero-model local actions all verified.
Under the same historical rate proxy, baseline was $0.03730 and capture $0.03982,
a 1.068× ratio that clears the provisional 1.10× cost gate. This is still one
learning case with manual rather than blinded quality review; expand to the other
four categories before making a release claim.

The next experiment adds two branches without adding a third model call. A
transparent viewport reuses the exact baseline answer and indexes its natural
Markdown blocks locally, making its incremental usage exactly zero. Compiled
capture now requests `none` per-turn reasoning effort because the preceding
capture reported 101 reasoning-output tokens while baseline reported zero. The
paired harness runs baseline/viewport/capture as two model turns: viewport shares
baseline's thread id and usage record, while both local paths must verify exact
full content and their expected protocols.

The learning-case comparison confirmed the architectural split. Baseline and
viewport shared 12,775 input tokens, 8,960 cached input tokens, and 491 output
tokens: viewport was exactly 1.000×, with byte-exact full response, `viewport-v1`,
and three local actions verified. Manual review found all six requirements in the
full answer; a first replay exposed an orphaned code block, and the deterministic
parser was tightened to bind colon-ended introductions to their structured blocks.

No-reasoning compiled capture reported 12,950 input tokens, 345 output tokens,
zero reasoning tokens, and a 1.002× reported-token ratio. It also passed all six
requirements, exact canonical hashing, marker compliance, and local navigation.
However, its input event reported zero cached tokens. Under the historical rate
proxy this makes capture $0.07510 versus baseline/viewport $0.03829, or 1.962×.
With the baseline's cache amount it would have been $0.03478, but that is a
counterfactual rather than a result. Treat transparent viewport as the proven
zero-incremental-usage path for eligible low-risk answers; keep compiled capture
experimental until repeated runs explain or control cache behavior.

A second one-call viewport check used the adversarial
`debugging-future-timestamp` case. Baseline and viewport again shared exactly
12,805 input tokens, 8,960 cached input tokens, and 287 output tokens, for 13,092
reported tokens and a 1.000× ratio. The first local replay exposed a more serious
navigation flaw: treating the Go patch as optional detail allowed `next` to skip
it. The viewport now makes every natural unit mandatory and binds introducing
prose to its following structured block. Replaying the same paid response locally
then produced diagnosis plus usable patch initially, boundary tests on the first
`next`, and the full test command on the second. Exact full content, shared-turn
accounting, `viewport-v1`, and all three local actions remained verified. This
extends the evidence to two categories, but quality assessment is still manual
and the remaining categories are untested.

The third one-call check used `planning-repair-cafe`. Baseline and viewport shared
12,825 input tokens, 8,960 cached input tokens, 1,082 output tokens, and 114
reasoning-output tokens: 13,907 reported tokens each, again 1.000×. The complete
answer contained all seven rubric requirements and exact reconstruction passed.
The action-level review exposed a distinct experience issue, however. The initial
viewport showed scope, `next` showed non-goals, and normalized `go deeper` returned
the non-goals plus the adjacent Owners section. That is coherent additional
content, but it is not genuinely deeper treatment of non-goals; the immediate
action also remained at the end until **full**. Token neutrality therefore passes
for a third category while progressive-trajectory quality remains provisional.
Evaluation now scores full-answer quality and action semantics independently. The
next design question is whether semantic deepening should trigger an on-demand
model call while sequential `next`, `map`, and `full` remain local and free.

The first intent-aware replay answers the routing half of that question without a
new paid turn. The harness now preserves the raw `go deeper` utterance instead of
normalizing it to **more**. On the same planning response, **next** resolved to an
exact local continuation, while `go deeper` produced `model_required` against the
current Non-goals span. **full** remained byte-exact and local, so measured usage
stayed 13,907 versus 13,907. This is a better trajectory result than returning
Owners as false depth, but not yet an end-to-end experience pass: the prototype
prepares a dormant-thread handoff and does not invoke it. New runs retain the
baseline thread; the historical replay correctly marks its old ephemeral thread
non-resumable.

The dormant-thread handoff is now executable rather than descriptive. The unified
re-entry client routes first and invokes the model only for `model_required`; it
uses app-server `thread/fork`, compiles the raw follow-up and exact current slice
into the new turn, inherits reasoning effort from the parent, and constrains the
Markdown response field with `outputSchema`. Only that field becomes the new
viewport. Fake-server coverage verifies both the zero-call local branch and the
one-turn fork branch.

The first live adaptive planning run then retained one baseline thread, resolved
`next` locally, and resumed exactly once for `go deeper`. Baseline usage was
13,391 input and 1,008 output tokens, totaling 14,399. The re-entry turn added
14,407 input and 2,928 output tokens, totaling 17,335; 13,056 of its input tokens
were cached. Combined usage was 31,734, or 2.204× baseline. Original and enriched
full hashes, thread continuity, `viewport-v1`, and local cleanup all verified.

The experience did not pass. Rather than deepen the visible Non-goals section,
the resumed model emitted a 2,928-token reconstruction of almost the entire plan.
The re-entry developer instruction had asked for a “complete” response, which
created the wrong optimization target. It now requests only the semantic delta,
forbids restating the prior answer or adjacent sections, and targets 150–350
visible output tokens unless correctness or safety requires more. This revision
still needs a paid rerun.

A prompt-only attempt to rerun that revision is excluded because it reconstructed
the older local viewport while reusing a remote thread already mutated by the
first semantic turn. Local state cannot rewind remote history. The implementation
now forks an immutable source thread, stores `parent_thread_id`, and makes the
evaluator verify every parent-to-child transition before accepting a result.

The first clean forked rerun verified those invariants but not the experience. A
14,493-token baseline plus an 18,021-token re-entry totaled 32,514 tokens, or
2.243×. Re-entry used 14,501 input tokens, 9,984 cached, and 3,520 output. The
stored child trace showed that fork-time `developerInstructions` had not entered
the model-visible history, so the intended delta bound was never applied. The
next revision moves the raw request, exact visible slice, and delivery contract
into the actual turn input and adds a 2,400-character response schema. It is
protocol-tested but not yet paid-validated.

The 2.204× total is not all pacing overhead: semantic deepening produces a richer
outcome than the one-shot baseline. Future acceptance must therefore preserve two
comparisons: exact local pacing versus one-shot, where the target remains 1.000×,
and incremental semantic re-entry versus an equivalent ordinary follow-up. The
first re-entry is overlong under either framing.

## Ordinary follow-up comparator

The planning comparator forks one newly retained baseline twice after the same
local `next`. Both branches receive the exact visible Scope/non-goals slice and raw
`go deeper` request. The adaptive branch adds the semantic-delta prompt and a
bounded response schema; the ordinary branch answers without those constraints.

Three fresh repetitions kept all six follow-up answers on the selected slice.
Adaptive output averaged 354 tokens and 199 visible words, compared with 736
tokens and 447 words for ordinary follow-up. Adaptive incremental reported usage
was lower in every pair by 199–386 tokens, averaging a 269-token or approximately
1.7% reduction.

The ordinary branch reported 9,984 cached input tokens in every repetition while
adaptive reported zero. That repeated asymmetry makes an invoice-cost advantage
unverified and may outweigh the modest reported-token reduction, depending on the
provider's billing semantics. Do not continue prompt micro-optimization without
user evidence that the tighter response materially improves the experience.

## Current acceptance target

For exact local navigation, incremental model usage must remain zero. For semantic
re-entry, compare the incremental turn with an equivalent ordinary follow-up and
report both cache behavior and output focus. Across product tests, do not treat a
usage increase as acceptable merely because the interaction is novel: users must
identify a meaningful orientation or completion benefit and knowingly judge it
worth the disclosed tradeoff. Parsnip must not claim token or cost neutrality
while the measurements remain higher or billing semantics are unverified.
