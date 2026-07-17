# Local answer capsules

Use capsule mode only after the user explicitly requests local buffering or when
the host declares that navigation controls bypass model turns. Normal composer
messages do not bypass the model merely because the MCP server is installed.

## Capture-and-carve contract

Prefer capture-and-carve when a host can own the app-server turn boundary. Start
one ephemeral, read-only turn with `parsnip-buffer` disabled, ask for a complete
Markdown answer, and store the authoritative `final_answer` text from
`item/completed` or the completed turn. Do not ask the model to construct or call
a capsule schema.

### Transparent viewport

Use the viewport only when the host reuses an ordinary completed one-shot response
without adding model instructions or starting another turn. Index natural Markdown
blocks locally and combine introducing prose or a heading with the structured
list, code fence, or table that follows it. Keep every resulting unit mandatory.
**next** advances one unit; **more** returns the current and following units
together and consumes the following unit, so it cannot later be skipped. Keep
fenced code intact and preserve the response byte-for-byte for **full**. Use this
mode only where these syntactic boundaries are safe; return one indivisible block
when natural structure is insufficient or progressive separation could hide a
governing warning.

When the host supports intent-aware routing, pass the raw natural utterance to the
router instead of first normalizing it to **next** or **more**. High-confidence
continuations, topic retrieval, orientation, and consolidation can resolve to
exact local spans. Requests for explanation, deeper reasoning, revision, or
execution return `model_required` with the current section pointer and a retained
thread id when one is available. These are invisible implementation choices: do
not teach the person routing keywords or ask them which path to use.

The unified client command is:

```text
mcp/launch.sh capture reenter SESSION_ID --prompt-file REQUEST.md --allow-model-call
```

`--allow-model-call` is a host safety boundary, not user-facing vocabulary. The
same command returns a local result without using that permission when exact
routing succeeds. When new inference is necessary, it forks the retained Codex
context onto a new thread branch. It compiles the raw request, exact visible
slice, and a semantic-delta contract into the turn input, constrains the response
field with a turn-level schema, and stores only that field as a new viewport
linked to its parent thread and local session.

The direct fixture command is:

```text
mcp/launch.sh capture viewport-file RESPONSE.md
```

Zero overhead means zero incremental model usage relative to that exact one-shot
turn. It does not make ordinary composer controls free.

### Compiled capture

When the host declares compiled capture, preserve the user's original request
verbatim and attach delivery instructions separately. Begin every release unit
with an exact marker on its own line:

```html
<!--p:s SHORT TITLE-->
```

Put an independently useful brief after it. If optional elaboration follows,
separate it with this exact marker on its own line:

```html
<!--p:d-->
```

Include every warning, prerequisite, irreversible consequence, and verification
step governing an action in its brief. Do not repeat the brief in the detail or
place marker-like text outside the protocol. The local parser serves the exact
brief for **less** or **next**, the exact complete unit for **more**, marker titles
for **map**, and the canonical visible response for **full**. Canonicalization
removes recognized marker lines only; the store hashes both the raw response and
canonical marker-free response. Malformed markers, empty briefs, and excessive
sections keep the entire answer indivisible instead of guessing boundaries.

For legacy uncompiled captures, an optional `#` title and explicit `##` reveal
sections remain a compatibility fallback; do not treat other heading levels as
reveal boundaries.

The plugin's direct client is exposed as:

```text
mcp/launch.sh capture capture-file RESPONSE.md
mcp/launch.sh capture navigate SESSION_ID ACTION
mcp/launch.sh capture run --allow-model-call --prompt-file REQUEST.md
```

`run` also accepts `--target-output-tokens N` (128–4096, default 450) and an
optional `--steering-file` containing style-only drift compatibility hints. It
defaults to the app-server's `none` per-turn reasoning effort when supported and accepts an
explicit `--effort`. The sidecar must never change the request's meaning.

The explicit `--allow-model-call` gate prevents a local test from accidentally
starting a billable turn. Captured answers use private temporary files, exact
canonical spans, a six-hour sliding expiry, and no local summarization or semantic
rewrite.

## Authoring contract

Prefer `create_lean_answer_capsule` when the complete answer can be composed from
ordered sections. Keep it under twenty-four nodes and include only stable material
likely to be useful. Every lean node must contain:

- a stable lowercase `id`, short `title`, and semantic `kind`;
- a self-sufficient `brief` authored at the current density;
- an optional `extension` that continues the brief without restating it;
- critical `warnings` that must appear whenever that node is revealed; and
- `parent_id` and `depends_on` links that point only to earlier nodes.

Put every node id exactly once in `sequence` and list factual changes or user
inputs that require a new model turn in `requery_triggers`. The buffer constructs
**full** by concatenating each title, brief, and extension in sequence. It does not
summarize or rewrite them, so author sections to read coherently in that order.

Use `create_answer_capsule` version 1 only when the answer needs a separately
authored polished `final_synthesis`. Its nodes contain:

- a stable lowercase `id`, short `title`, and semantic `kind`;
- a self-sufficient `brief` authored at the current density;
- an optional `detail` authored by the same model, never locally rewritten;
- critical `warnings` that must appear whenever that node is revealed;
- `parent_id` and `depends_on` links that point only to earlier nodes.

Put every node id exactly once in `sequence`. Store a concise complete
`final_synthesis` and list factual changes or user inputs that require a new model
turn in `requery_triggers`. In either schema, do not store hidden reasoning,
chain-of-thought, quoted private deliberation, tool logs, or unrelated source
material.

## Navigation contract

Use `navigate_answer_capsule` only for deterministic operations over already
authored content:

- `next`: reveal the next brief node;
- `more`: reveal the current node's authored detail, or its brief plus extension
  in a lean capsule;
- `less`: return to its authored brief;
- `map`: show node titles and progress;
- `full`: reveal the authored final synthesis, or deterministically concatenate
  lean sections, plus accumulated warnings;
- `status` or `reset`: inspect or restart local progress; and
- `close`: delete the capsule immediately.

Capsules expire after six hours by default and are stored in a private temporary
directory with restrictive permissions. A direct client or future scheduler can
invoke the same navigation operation locally. Do not implement timed delivery in
the skill or infer an interval from response timing.

If the user supplies new facts, changes a constraint, disputes a premise, asks a
question outside the capsule, or matches a `requery_trigger`, stop local navigation
and return to the primary model with only the relevant nodes and new information.
