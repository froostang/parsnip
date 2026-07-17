# Parsnip v0.1 dogfood

Use this sheet for synthetic dogfood and formative user testing. Passing technical
checks is necessary but does not establish that the pacing is useful to people.

## Acceptance checks

A session passes when:

- useful task content appears in the first response;
- skipping calibration begins at Level 1;
- **next** advances without changing density;
- **more** and **less** move exactly one level and affect the current content;
- **map** preserves orientation without changing density;
- natural-language equivalents work;
- **full answer** exits progressive disclosure for one response;
- after one continuation, the usage guard defaults the next generated content to
  **finish compactly** unless the user explicitly chooses **keep pacing**;
- local answer capsules activate only by explicit request, preserve authored text
  and attached warnings, expire locally, and become stale when premises change;
- ordinary chat controls are not counted as zero-model navigation merely because
  the local buffer is installed;
- critical context appears with every risky action;
- no automatic change is based on timing alone; and
- automatic changes are disclosed, reversible, and separated by a cooldown;
- no background or speculative model calls occur; and
- usage is measured against an equivalent baseline, higher usage is disclosed,
  and no token- or cost-saving claim is made without evidence;
- drift compatibility learns only from spontaneous user prose, requires repeated
  evidence across messages, and ignores pasted or quoted styles;
- the drift profile densely captures relevant preferences in language, abstraction,
  reasoning, structure, orientation, interaction, affect, and typography without
  trying to populate every dimension;
- inferred preferences carry confidence and counterevidence, while explicit
  corrections apply immediately;
- concept maps promote only after two evidence kinds across messages or explicit
  confirmation, and retain context, confidence, counterevidence, and recency;
- learned relationships improve later explanations without decorative repetition
  or being forced onto unrelated topics;
- distinctive punctuation and formatting stay off unless the user demonstrates
  them;
- compatible responses feel native without copying errors, mimicry, or implying
  access to the user's internal state; and
- **neutral drift** and **neutral voice** immediately reset compatibility without
  changing density.

## Five test tasks

1. **Debugging:** diagnose a failing test and propose a safe change.
2. **Planning:** reduce a large project idea to the next finishable action.
3. **Learning:** explain an unfamiliar technical concept from first principles.
4. **Document review:** extract decisions and risks from a long document.
5. **Decision:** compare options with meaningful tradeoffs and choose a next step.

Include at least one calibration, one interrupted calibration sample, one natural
language control, one map request, and one full-answer request across the five
sessions.

## Usage harness

`run_usage_eval.py` can run nine matched conditions and sums their
`turn.completed.usage` records:

1. concise one-shot;
2. transparent viewport over the exact concise one-shot response;
3. adaptive viewport over a retained baseline, with model re-entry only for
   semantic requests;
4. an ordinary follow-up fork over the same retained baseline, visible slice,
   and raw semantic request, without the adaptive delta contract or schema;
5. ordinary progressive chat with two scripted continuations;
6. Parsnip progressive chat with the same continuations;
7. one rich Parsnip capsule-authoring turn followed by direct local navigation;
8. one lean capsule-authoring turn, with no skill/reference reads or duplicate
   synthesis, followed by the same local navigation; and
9. one no-reasoning capture-and-carve app-server turn followed by exact-span
   local navigation.

Both buffered arms extract the capsule session id from the completed MCP tool call,
replay the case controls through `mcp/launch.sh cli`, and locally request `full`
when needed to produce the same completed outcome. These local processes never run
`codex exec`; their call counts and single authoring turns are reported separately.
A Codex turn may still contain multiple model/tool-planning cycles, all of which
remain included in its usage record. The five synthetic cases and their
predeclared rubrics live in `usage_cases.json`.

The capture arm reads the app-server `thread/tokenUsage/updated` event, requires a
complete per-turn usage breakdown, records one Codex turn, and verifies the SHA-256
hash of the locally returned canonical **full** response. It also requires the
compiled marker protocol and carries a separately computed raw-response hash
across capture and local storage. It fails closed when usage accounting, the
session id, either integrity hash, or the marker protocol is missing.

The viewport arm starts no model turn of its own. It ingests the baseline's exact
final response, attributes the same thread id and usage record, and verifies
`viewport-v1`, byte-exact **full**, and direct local navigation. Treat its `1.000×`
ratio as valid only when `shared_baseline_turn_verified` is true.

Viewport controls are now sent to the local intent router as their raw natural
utterances. The harness records `model_escalation_requests` and
`all_intents_satisfied_locally` separately from token equality. A new baseline
thread is retained for possible semantic re-entry; a replayed historical baseline
is marked non-resumable because its original ephemeral status cannot be proven.

The Parsnip condition attaches the canonical `SKILL.md` locator from the current
checkout. This prevents a raw non-interactive prompt from silently falling back to
ordinary output when a marketplace-installed skill is absent from that session's
model-visible skill list.

The scripted cases use one continuation followed by a second content control. The
second control exercises the default consolidation guard; broader control behavior
remains covered by the functional dogfood checklist rather than adding avoidable
calls to every usage pair.

List or inspect cases without making model calls:

```sh
python3 evals/run_usage_eval.py --list
python3 evals/run_usage_eval.py \
  --case learning-bloom-filter \
  --dry-run \
  --output-dir /tmp/parsnip-evals
```

Prepare the minimal two-turn capture smoke without running it:

```sh
python3 evals/run_usage_eval.py \
  --case learning-bloom-filter \
  --condition baseline \
  --condition capture \
  --dry-run \
  --output-dir /tmp/parsnip-evals
```

Run one measured comparison with the same explicit model in every model-backed
condition:

```sh
python3 evals/run_usage_eval.py \
  --case learning-bloom-filter \
  --model MODEL_ID \
  --output-dir ~/.parsnip-private-evals
```

Without `--condition`, `--all` runs all nine conditions across all five cases and
can make many model calls. Use it deliberately; prefer the paired baseline/capture
smoke first.
The harness rejects output paths inside this repository. It writes raw JSONL,
stderr logs, cumulative outputs for rubric review, per-case summaries, and a cohort
summary only to the external output directory.

Exact token components are available whenever Codex emits usage metadata. Dollar
cost remains unverified unless `--rates` points to a JSON object containing current
`input_per_million`, `cached_input_per_million`, and `output_per_million` rates for
the selected model. Rates are supplied at run time because pricing can change.
Reasoning output remains visible as a diagnostic component but is excluded from
the cost formula to avoid double-counting; confirm the selected model's billing
semantics before treating the estimate as invoice-equivalent.

## Session note

Copy this block once per session:

```text
Task:
Calibration: skipped / completed / interrupted
Starting level:
Controls used:
Did the first response provide value? yes / no
Did critical context stay with its action? yes / no / not applicable
Overall density: too little / right / too much
Where did I lose orientation, if anywhere?
Did I complete or decide the next move?
One change for Parsnip:
Model calls:
Billable tokens, if available:
Comparable one-shot baseline, if available:
Usage result: neutral / lower / higher / unverified
Drift fit: translating / compatible / mimicry
Automatic drift adaptation observed by dimension:
Explicit reasoning or structure preference and response:
Explicit punctuation preference and response:
Conflicting evidence handled:
Pasted-text style ignored: yes / no / not tested
One-off metaphor ignored: yes / no / not tested
Concept map promoted from reuse / extension / transfer / prediction / confirmation:
Learned relationship reused without parroting: yes / no / not tested
Concept-map counterevidence handled:
Did neutral drift reset correctly? yes / no / not tested
```

## Decision after formative sessions

Review patterns rather than isolated events. Continue product development only if
people report meaningful completion or orientation benefits beyond simply asking
the AI to be concise, and some judge those benefits worth the disclosed usage
tradeoff.

The first measured five-case synthetic cohort on 2026-07-15 established
answer-quality non-inferiority: Parsnip passed every rubric item, while one baseline
decision-comparison item was partial. It failed the usage target: Parsnip consumed
19.25× the aggregate reported tokens, with a 22.34× median case ratio. Treat the
alpha as usage-blocked pending a passing rerun; the new continuation guard is a
mitigation to test, not evidence of neutrality.

The guarded rerun reduced Parsnip's reported total by 45.7% and retained
non-inferiority, with Parsnip passing every rubric item, but still measured 10.49×
the one-shot aggregate and 10.51× at the median case. Keep the usage blocker open.

The four-condition rerun retained rubric quality: ordinary progressive, Parsnip
progressive, and buffered outputs each passed all 30 items; the concise one-shot
arm had 29 passes and one partial due to a weekly-hours inconsistency in its
planning answer. Reported totals were 66,974 one-shot, 418,565 ordinary,
704,225 Parsnip, and 458,492 buffered. The buffer verified fourteen direct local
navigation calls with no added Codex turns, but still measured 6.85× the one-shot
token total and 5.24× the current rate-card proxy. Keep the usage blocker open and
target capsule-authoring overhead rather than the now-local navigation path.

A same-build learning-case smoke of the experimental lean arm passed all six
rubric items and reduced rich-buffer usage from 101,785 to 44,335 reported tokens.
Its 3.20× one-shot rate proxy still exceeded ordinary progressive chat's 2.26×.
Run the remaining synthetic categories before treating the lean schema as a
general improvement.

Capture-and-carve is implemented after this smoke as a sixth experimental path,
and received one paired learning-case smoke on 2026-07-16. Baseline and capture
both passed all six content requirements; capture used 13,438 reported tokens
against 13,179 for baseline (1.020×), reconstructed the exact full response, and
kept navigation local. Under the project's previous rate-card proxy it measured
1.155× baseline because of additional output, so it missed the provisional 1.10×
cost gate. It also used non-contract heading levels; the parser now fails safe to
one indivisible answer unless explicit `##` boundaries exist. Rerun this single
pair after that format/conciseness change before starting a five-case cohort.

That format iteration is now implemented as **compiled capture**. The baseline
prompt is preserved verbatim, while a deterministic sidecar asks for at most 450
visible output tokens and exact invisible release markers. Local fixtures verify
marker removal, brief/detail navigation, raw and canonical hashes, fenced-code
isolation, and fail-safe fallback. Its paired rerun passed all six requirements on
manual review and used 13,463 reported tokens against 13,233 for baseline, a
1.017× ratio. `exact_full_verified`, `marker_protocol_verified`, and zero-model
local navigation all passed. The historical rate proxy was $0.03982 versus
$0.03730, a 1.068× ratio that clears the provisional 1.10× cost gate. This is one
category with manual rather than blinded review; run the remaining four categories
before treating compiled capture as release-validated.

The next paired arm reuses baseline as a transparent viewport and sets compiled
capture to `none` reasoning effort. This comparison still requires only two
model calls; viewport adds local indexing and navigation only.

The learning-case run validated viewport at exactly 1.000× baseline usage: both
shared 12,775 input, 8,960 cached input, and 491 output tokens. Exact full content,
`viewport-v1`, shared-turn accounting, and three local actions passed. A local-only
replay then fixed an orphaned code-block boundary by binding colon-ended
introductions to their following structured blocks. Manual full-answer review
passed all six rubric requirements.

Compiled capture with `none` reasoning used 12,950 input and 345 output tokens,
with zero reasoning output, for a 1.002× reported-token ratio. Content, marker,
hash, and navigation checks passed, but cached input unexpectedly fell from 8,960
to zero. The historical rate proxy therefore measured $0.07510 capture versus
$0.03829 baseline, a 1.962× ratio. Do not generalize compiled capture's cost until
cache behavior is repeated and understood; viewport's cost equality is structural
because it reuses the baseline turn itself.

The next one-call viewport check used `debugging-future-timestamp`. Baseline and
viewport shared 12,805 input, 8,960 cached input, and 287 output tokens, totaling
13,092 each for a 1.000× ratio. A first local replay revealed that the previous
brief/detail pairing could let `next` skip the required Go patch. The parser now
binds introducing prose to its following structured block, keeps every natural
unit mandatory, and makes `more` consume the following unit instead of hiding it
as optional detail. Replaying the same response locally then revealed diagnosis
plus patch, boundary tests, and the full test command in order. Exact full content,
shared-turn accounting, `viewport-v1`, and three zero-model local actions passed.
This is two manually reviewed categories, not yet a release-quality cohort.

The planning case was the third one-call viewport check. Baseline and viewport
each reported 12,825 input, 8,960 cached input, 1,082 output, and 114 reasoning
tokens, totaling 13,907 for a 1.000× ratio. The complete answer passed all seven
manual content requirements, exact full reconstruction, shared-turn accounting,
and local-action checks. Its progressive trajectory was only a partial experience
pass: scope and non-goals appeared in order, but normalized `go deeper` added the
adjacent Owners section rather than deepening non-goals, and the immediate action
remained buried until **full**. Review artifacts now label initial, `next`,
`more`, and `full` responses separately. Treat full-answer completeness and
control-semantic quality as independent gates; do not call the viewport
experience validated merely because its token ratio is 1.000×.

Replaying that same planning response through the intent-aware router required no
new model call. `next` advanced to non-goals, while `go deeper` returned a
high-confidence `model_required` decision anchored to the current Non-goals span
instead of incorrectly revealing Owners. **full** remained exact and local. The
run therefore stayed at 1.000× while correctly recording one semantic escalation
request and `all_intents_satisfied_locally: false`. Because the paid baseline was
an older ephemeral fixture, it correctly reported `resumable: false`; new runs
retain the dormant baseline thread for that handoff.

Automatic dormant-thread re-entry is now implemented in the capture client and
verified against a fake app-server. One natural-request entrypoint first attempts
local routing; only `model_required` invokes `thread/fork` followed by
`turn/start` on the new branch. The turn input compiles the raw request with the
exact visible slice and a semantic-delta contract; `outputSchema` bounds the
Markdown response field to 2,400 characters. No reasoning-effort override is
sent, and only that field is captured as a new `viewport-v1` session with its
`parent_thread_id`. Fake-server and harness coverage verify both branches and the
parent-to-child lineage.

The first live adaptive planning run retained the baseline and correctly routed
`next` locally before using one resumed turn for `go deeper`. Baseline usage was
13,391 input plus 1,008 output, or 14,399 reported tokens. Re-entry added 14,407
input and 2,928 output, or 17,335 tokens; 13,056 of its input tokens were cached.
The combined adaptive path was 31,734 tokens, 2.204× the one-shot baseline. Both
the original and enriched full hashes, the retained thread, `viewport-v1`, and
two-session cleanup verified. Experience review failed: the model reconstructed
almost the entire plan instead of deepening the visible Non-goals slice. The
re-entry instruction now asks only for the semantic delta, forbids reconstructing
the prior answer, and targets 150–350 visible output tokens. That prompt revision
has not yet received a paid rerun.

A subsequent prompt-only attempt reused the already-mutated remote thread after
reconstructing its older local viewport. It is excluded: local reconstruction
cannot rewind remote conversation history. Re-entry now uses immutable
`thread/fork` branches, and the evaluator rejects any branch whose recorded
`parent_thread_id` does not match the current lineage.

The first clean immutable-fork validation also failed the experience gate. It
retained a new baseline, resolved `next` locally, and verified the child lineage,
but `go deeper` added 14,501 input and 3,520 output tokens, or 18,021 reported
tokens. Baseline was 14,493 tokens; combined usage was 32,514, or 2.243×. The
stored child trace contained the inherited history and raw follow-up but not the
fork-time `developerInstructions`, explaining why the 150–350-token contract had
no effect. The next implementation compiles that contract and current slice into
the actual turn input and adds a response schema; it has unit and fake-server
coverage but no paid validation yet.

The first paired ordinary-follow-up comparator used one newly retained planning
baseline and forked it twice after the same local `next`: adaptive re-entry and an
ordinary follow-up both received the exact visible Scope and non-goals slice and
raw `go deeper` request. Adaptive re-entry stayed focused at 183 visible words and
used 15,369 incremental reported tokens; the ordinary follow-up stayed on-topic
but expanded to 533 words and used 15,695. Adaptive therefore reduced incremental
reported usage by 326 tokens (2.1%) and output by 439 tokens. The ordinary fork,
however, reported 9,984 cached input tokens while adaptive reported none, so
invoice cost cannot be ranked without supplying verified model rates. Both child
lineages, initial/final hashes, local `next`, and single-follow-up limits passed.

Three fresh repetitions reproduced the result. Adaptive incremental usage was
15,307, 15,978, and 15,133 reported tokens versus 15,506, 16,364, and 15,356 for
ordinary follow-up, saving 199–386 tokens in every pair (269 mean). Adaptive
output averaged 354 tokens and 199 visible words; ordinary output averaged 736
tokens and 447 visible words. All six responses stayed on the selected
Scope/non-goals slice. The cache split was also exact in every repetition:
adaptive follow-up reported zero cached input while ordinary reported 9,984.
This makes the asymmetry repeatable in the current setup but does not identify
whether the compiled prompt, response schema, or their interaction causes it;
isolate those factors before drawing a billing conclusion.

Do not interpret 2.204× as pure pacing overhead: `go deeper` requests a different,
richer outcome than the original one-shot. The relevant efficiency questions are
whether local requests remain free and whether the incremental semantic turn is
competitive with an ordinary follow-up. This first turn was clearly overlong even
under that fairer comparison.

## Evaluation privacy

Keep raw transcripts, participant details, private project ideas, local paths,
timestamps, provider identifiers, and unredacted usage exports out of the public
repository. Store them in a separate private research workspace, not merely in a
folder inside this public worktree.

Commit only synthetic fixtures or aggregated findings that cannot be traced to an
individual or confidential project. Review staged changes and commit metadata for
names, email addresses, locations, and secrets before every public push.
