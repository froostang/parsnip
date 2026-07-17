# Local answer buffer

## Goal

Let the primary model author a compact answer graph once, then reveal stable layers
without repeatedly sending the expanding conversation back to the model. The
buffer preserves model quality by selecting existing text rather than summarizing
or rewriting it.

The preferred path is now **capture-and-carve**: request an ordinary complete
answer once, capture its authoritative final text outside the model, then reveal
exact spans locally. This factors the pacing state out of the model conversation
without trying to relocate provider-side prompt caching.

The zero-incremental-model-usage variant is a **transparent viewport**. It sends the ordinary
one-shot prompt unchanged, reuses that exact response as the baseline and Parsnip
artifact, and groups natural Markdown blocks locally. This makes incremental
model usage exactly zero by construction. It is intentionally limited to
low-risk exposition because natural paragraph boundaries do not guarantee that a
warning remains attached to its action.

## Prototype boundary

The plugin now includes a dependency-free local stdio MCP server with three tools:

- `create_answer_capsule` validates and stores one rich model-authored graph;
- `create_lean_answer_capsule` stores ordered briefs and non-repeating extensions
  without a duplicate synthesis; and
- `navigate_answer_capsule` deterministically reveals `next`, `more`, `less`,
  `map`, or `full` content.

The same store has a direct CLI at `plugins/parsnip/mcp/cli.mjs`, exposed portably
as `mcp/launch.sh cli navigate SESSION_ID ACTION`. A client that calls the CLI or
MCP navigation endpoint directly performs no model generation. Typing a control
into the ordinary chat composer still creates a model turn, so the skill must not
claim otherwise.

The plugin also includes `mcp/launch.sh capture`, a local Codex app-server client.
Its `run` command starts one ephemeral read-only turn, disables the
`parsnip-buffer` MCP server for that turn, captures the completed final agent
message, and terminates the app-server process. It requires
`--allow-model-call`, making the usage-bearing boundary explicit. `capture-file`
ingests an existing fixture without a model call, and `navigate` serves stored
content locally. `viewport-file` indexes an unchanged one-shot response without a
sidecar or marker tokens. Its block parser keeps fenced code intact and binds
prose or a heading to the structured list, code fence, or table it introduces.
Every resulting unit is mandatory: `next` advances by one unit, while `more`
returns the current and following unit together and consumes that following unit.
No natural unit is hidden as skippable detail.

This mandatory-unit behavior makes **more** mean adjacent authored content, not
guaranteed semantic deepening. A heading boundary can make that distinction
visible: expanding non-goals into owners is coherent continuation but not a
deeper explanation of non-goals. The zero-model path must be evaluated on that
control-semantic tradeoff separately from exact reconstruction. A likely hybrid
is to keep **next**, **map**, and **full** local while routing true **go deeper**
requests to model-backed enrichment only on demand.

The first intent-aware router now implements that boundary without requiring the
person to name it. The capture client accepts `route SESSION_ID NATURAL_REQUEST`
and preserves the raw utterance. High-confidence acknowledgements and continuation
phrases advance locally; requests naming an existing section jump to its exact
span; overview and complete-answer requests remain local. Explanation, deeper
reasoning, revision, and execution requests return `model_required` rather than
silently degrading into adjacent content. Low-confidence requests also fail open
to the primary model. The classifier only routes and never authors or paraphrases
answer content.

New viewport evaluations retain the baseline thread and persist its id with the
local capture. An escalation result includes that dormant thread id plus the
current section title, index, and exact span. This is enough for a host to resume
the original authoring context with a compact hidden viewport pointer; older
ephemeral fixtures correctly report `resumable: false`.

The unified `reenter` command now executes this policy. It always routes the raw
request locally first. A locally satisfiable request returns immediately without
consulting Codex, even when the host has pre-authorized model calls. For
`model_required`, the client calls app-server `thread/fork`, then `turn/start`
on the new branch. The turn input is a locally compiled envelope containing the
raw request, the exact current slice as untrusted JSON, and the semantic-delta
contract. A turn-level `outputSchema` caps the Markdown response field at 2,400
characters. Re-entry inherits the parent thread's model and reasoning
configuration by default and indexes only that field as a new transparent
viewport linked to the previous local session and parent thread. The source
thread and old viewport remain immutable and available until normal expiry.

Re-entry requests only the semantic delta for the current slice. The hidden
instruction forbids reconstructing the prior answer or adjacent sections and
targets 150–350 visible output tokens unless correctness or safety requires more.
This bound was added after the first live planning re-entry rewrote almost the
entire plan instead of deepening Non-goals.

A clean forked rerun proved that fork-time `developerInstructions` were not
present in the stored child trace. The model therefore received only the inherited
complete-plan request and raw `go deeper`, producing another full rewrite. The
compiled turn envelope and response schema move the contract onto documented
turn-level controls instead of relying on that ineffective field.

The CLI still requires `--allow-model-call` before executing the paid branch.
That flag is an integration safety boundary rather than a conversational control;
a product host can grant it once while keeping local-versus-model selection
invisible to the person.

The capture client now acts as a deterministic semantic prompt compiler. It leaves
the original user request unchanged and attaches a compact developer-instruction
sidecar containing a visible-output budget, optional drift compatibility hints,
and a release protocol. The primary model remains the only answer author; no
intermediate model paraphrases or enriches the request.

Compiled capture requests `none` app-server reasoning effort by default for the
validated Sol model. This
is a per-turn override supported by the installed app-server schema, not a second
model or a change to the user's request.

Release units begin with a compact invisible marker such as `<!--p:s Core-->`. An
optional `<!--p:d-->` separates the independently useful brief from later
elaboration. `next` and `less` return the exact brief, `more` returns the exact
complete unit, `map` returns marker titles and progress, and `full` returns the
canonical visible answer with recognized control markers removed. The store keeps
and hashes both the raw model response and canonical visible response. Malformed,
empty, excessive, or ambiguous marker structures fail to one indivisible answer;
marker examples inside fenced code are ignored. Legacy `##` carving remains only
as a compatibility fallback for unmarked captures.

The plugin launcher prefers `PARSNIP_NODE`, then a host `node`, then Codex's
bundled local runtime. The current alpha launcher targets POSIX local Codex hosts;
cross-platform runtime discovery remains a packaging requirement before public
release.

Capsules use a six-hour sliding expiry, random session identifiers, a 128 KiB size
limit, at most twenty-four nodes, and private temporary files. They contain only
user-visible answer content. Critical warnings stay attached to the node they
govern, and dependencies must appear earlier in reveal order.

Version 1 keeps authored briefs, details, and a separate polished final synthesis.
Version 2 is the lean path: each section has one brief plus an optional extension,
and `full` concatenates those exact authored sections in order. The host performs
no summarization or semantic rewrite.

Captured answers use a separate private temporary store, the same six-hour sliding
expiry and restrictive permissions, a 512 KiB ceiling, and at most twenty-four
locally indexed sections. The authoritative final answer and its small control
markers are stored; streamed commentary, hidden reasoning, tool logs, and deltas
are excluded. Marker removal is deterministic rather than a semantic rewrite.

## Model re-entry

Local navigation stops when the user changes a fact or constraint, disputes a
premise, asks beyond the graph, or triggers another requery condition authored in
the capsule. The next model turn should receive the new input plus only the
relevant capsule nodes, not the entire hidden artifact.

For capture-and-carve, any semantic change also ends local navigation. Exact-span
selection cannot answer a new question or safely revise an assumption. When a
dormant authoring thread is available, the host should fork it with the raw
utterance and current viewport pointer; otherwise it must start a fresh thread.

A prompt-only rerun exposed why the fork matters: rebuilding an older local
viewport does not rewind a remote thread that has already received a semantic
follow-up. That contaminated rerun is excluded from quality and usage results.
Each valid re-entry now records `parent_thread_id` and advances onto a new branch,
so the harness can verify the complete parent-to-child lineage without mutating
the source context.

## Timed delivery

Timed delivery is deliberately outside this prototype. A later client may call the
same deterministic navigation endpoint on a user-chosen schedule, but Parsnip
should not infer dwell time, attention, or a release interval. Add scheduling only
after direct manual navigation proves useful and usage-neutral.
