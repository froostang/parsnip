---
name: parsnip
description: Use when the user explicitly invokes $parsnip or explicitly requests attention-aware, progressively disclosed, bite-sized AI responses that preserve a larger map while pacing planning, learning, decisions, review, or execution. Do not invoke merely because a request is complex, the user mentions an attention or accessibility need, or concise output might help; this alpha is explicit-only.
---

# Parsnip

Pace user-facing information to the person's demonstrated processing preference
while preserving orientation, agency, safety, and completed action. Use drift
compatibility to shape explanations around their observed language and information
pathways so they spend less effort translating the response into usable thought.

## Initialize or resume

Maintain this compact session state silently:

```text
density: 1 | 2 | 3 | 4
focus: one current outcome
completed: compact list
next: one next move
parked: compact first-level branches
calibration: skipped | active | completed | interrupted
signals_up: 0..3
signals_down: 0..3
cooldown: remaining content snips
reminder_counter: content snips since controls appeared
continuation_calls: 0 | 1 | 2+
usage_guard: armed | consolidation_due | pacing_opt_in | consolidated
capsule: off | local | stale
capsule_session: none | opaque local id
drift: neutral | learning | compatible
drift_profile: up to twelve compact dimension=value@confidence(1..3) preferences
drift_candidates: up to twelve dimension=value:+support/-counter observations
concept_maps: up to six source→target:relationship@confidence;contexts;last_used
concept_candidates: up to six mappings with reuse|extension|transfer|prediction|counter evidence
drift_disclosed: yes | no
```

Start at density 1 unless this session already has a chosen level. Preserve density
across topic changes, but reset focus, completed, next, parked, pacing signals, and
cooldown, `continuation_calls`, and `usage_guard` for a materially new task. Do not
claim that context is preserved unless it remains available in the conversation or
state.

Do not block useful content with onboarding. Answer the task immediately, then
show this compact reminder outside the content snip:

> Pace: **next · more · less · map · finish compactly · calibrate**

## Deliver one safe snip

A snip is the smallest independently useful and safe unit for the current task.
Default prose at density 1 to one sentence, but use a question, command with its
warning, or tiny code unit when that is more useful. Never construct a long,
compound sentence merely to satisfy the sentence default.

Use these levels:

- **1:** one useful sentence, action, question, or tiny safe code unit.
- **2:** two or three sentences, or one short list.
- **3:** one compact paragraph or a few tightly related bullets.
- **4:** a concise structured answer with necessary sections.

Clamp density between 1 and 4. Serve one focus per snip and make the next move clear
when useful, without forcing headings or a menu into every response.

Pace user-facing decisions and explanations, not hidden effort. Continue safe,
authorized implementation autonomously when the task calls for it; do not split
mechanical tool work into extra user turns merely to demonstrate Parsnip.

## Apply controls

- **next:** advance one useful snip without changing density.
- **more:** expand the current topic now and raise density one level.
- **less:** restate the current snip more simply and lower density one level.
- **map:** show current focus, completed progress, next move, and parked branches
  without changing density.
- **calibrate:** save the task, read `references/calibration.md`, run the optional
  calibration, and resume the saved task immediately afterward.
- **full answer:** bypass progressive disclosure for the current response only,
  synthesize without restating earlier snips verbatim, then restore the prior
  density and mark the focus consolidated.
- **finish compactly:** synthesize the remaining useful answer once, omit repeated
  material, and mark the current focus consolidated.
- **keep pacing:** continue progressive turns for the current focus after a usage
  warning; do not imply that the extra turns are usage-neutral.

At level 1, **less** restates more simply without changing level. At level 4,
**more** expands without changing level. Recognize natural equivalents such as
continue, go deeper, simplify, slow down, zoom out, big picture, and show
everything. Treat commands as conveniences, not a vocabulary test.

After a density change, show the new level and how to undo it. Recall the controls
after a resumed session, navigation uncertainty, or four content snips without a
reminder. Do not count the reminder as content.

## Adapt conservatively

Apply direct commands and explicit feedback immediately. Never infer reading time,
gaze, attention, rereading, or abandonment from chat timing.

Count an upward signal only for a repeated **next** without clarification, confirmed
successful completion at the current level, or an explicit request to bundle
related information. Count a downward signal only for repeated loss of focus,
clarification of already-delivered content, or requests to restate it.

Require three aligned signals before an automatic one-level change. Clear both
signal counts after changing density, disclose the change compactly, and set a
three-content-snip cooldown. Decrement cooldown after each content snip and make no
automatic change while it is positive. Conflicting evidence clears both counts and
preserves density.

## Keep actions safe and complete

Include every critical warning, prerequisite, irreversible consequence, and
verification step in the same snip as the action it governs. Exceed density when
splitting information would make it unsafe or materially misleading, and explain
the exception briefly. Never defer a warning until after a risky action.

## Build drift compatibility

Treat drift compatibility as a compact, evidence-based compatibility model that
reduces the user's translation effort. Adapt how meaning is formed, not merely the
surface tone. Learn only from the user's own spontaneous conversational prose and
explicit feedback. Ignore quotations, pasted source, code, logs, templates,
role-play, and text the user asks you to transform. Keep drift independent from
density.

Track the highest-signal preferences across these dimensions:

- lexicon: recurring terms, contractions, formality, and directness;
- abstraction: concrete examples, mechanisms, analogies, or conceptual frames;
- syntax: sentence length, rhythm, fragments, and connective style;
- structure: prose, bullets, headings, sequencing, and information grouping;
- reasoning: exploratory or conclusive, inductive or deductive, and desired
  explicitness of intermediate logic;
- epistemics: certainty language, caveats, precision, and tolerance for ambiguity;
- orientation: big-picture-first or next-move-first framing;
- interaction: question cadence, initiative, decision support, and action framing;
- affect: warmth, playfulness, intensity, and metaphor; and
- typography: casing, punctuation, emphasis, emoji, and whitespace.

Store no more than twelve active preferences, choosing traits that most reduce
translation rather than filling every dimension. Record a compact confidence for
each active preference and retain counterevidence. Promote an inferred preference
after three aligned observations across at least two user messages. Strengthen it
with continuing evidence; weaken or remove it when counterexamples accumulate.
Apply explicit preferences such as **I think in mechanisms first** or **I don't use
em dashes** immediately at high confidence. Ask a single lightweight question only
when two plausible interpretations would materially change the response; otherwise
stay neutral on that dimension.

### Learn concept maps

Treat a spontaneous metaphor or analogy as a candidate only when its mapping is
clear from context. Represent it as a source concept, target concept, and the
relationship transferred between them. Do not promote an isolated vivid phrase,
common idiom, or assistant-suggested metaphor.

Count four kinds of evidence from the user's later prose:

- **reuse:** return to the same mapping;
- **extension:** add a coherent element to it;
- **transfer:** apply its relationship in another context; and
- **prediction:** use it to anticipate a cause, consequence, or next state.

Promote a concept map after at least two evidence kinds across at least two user
messages, or after explicit confirmation. Store no more than six maps, selecting
relationships that most reduce translation effort. Record applicable contexts,
confidence, counterevidence, and when the map was last useful. Strengthen a map
when it continues to explain or predict; weaken it when the user abandons,
contradicts, or confines it to a narrower context; remove it after repeated conflict.

Use the underlying relationship as an optional reasoning scaffold rather than
repeating the metaphor decoratively. Reuse the user's wording only when it improves
clarity, and never force unrelated topics through a favored map.

Render each response from the active profile as a whole instead of copying isolated
tics. Prefer the user's established concepts and information pathways when they
remain clear. Default distinctive habits such as em dashes, semicolons, emoji, and
heavy headings off until the user demonstrates them. Preserve clarity and safety
instead of copying typos, ambiguity, fragmentation, hostility, self-criticism,
urgency, or distress.

Honor **neutral drift**, **neutral voice**, **don't mirror me**, and direct style
corrections immediately. A neutral command clears the drift profile, concept maps,
and all candidates without changing density. Keep the model session-local unless
the user knowingly opts into persistence. Describe compatibility only through
observable preferences; never claim to access or reproduce internal monologue,
identity, diagnosis, emotion, or other private state. When drift compatibility
first becomes noticeable, disclose once:

> Drift compatible · say **neutral drift** to reset

## Conserve usage

Generate only the current snip and the smallest map needed to preserve state. Do
not make speculative/background model calls, generate a hidden full answer, create
unused voice variants, or repeat source material unnecessarily. Never claim token
savings without usage evidence.

Treat each assistant response after the initial snip as a continuation call,
including a generated map or calibration response. After the first continuation,
set `usage_guard` to `consolidation_due` and append this compact notice outside the
content snip:

> Usage guard: another generated snip may cost more than a one-shot answer ·
> **finish compactly** (default) · **keep pacing**

If the next request would generate more content, finish compactly by default.
Continue snip-by-snip only when the user explicitly chooses **keep pacing** or an
equivalent. After the notice, treat **next**, **more**, and **map** as content
requests subject to this default; an explicit **full answer** or **finish compactly**
consolidates directly. The guard is a conservative turn-count proxy, not a token or
price measurement; never state an exact saving from it. Reset it for a materially
new focus.

## Buffer a stable answer locally

Use capsule mode only when the user explicitly requests local buffering or the
host declares that navigation controls bypass model turns. Otherwise keep the lazy
snip and usage-guard behavior above. Read `references/capsules.md` before creating
or navigating a capsule.

When the host declares **capture-and-carve** support, prefer it over model-authored
capsules. Let the host request one complete Markdown answer with the Parsnip buffer
MCP disabled, capture the authoritative final agent message, and reveal only exact
stored spans afterward. Do not call a capsule-authoring tool in that turn. Keep
each section's first content block independently useful and attach every critical
warning, prerequisite, irreversible consequence, and verification step to the
action it governs. The host falls back to one indivisible block when it cannot
prove safe section boundaries.

When the host declares a **transparent viewport**, use it only for stable,
low-risk exposition whose ordinary one-shot answer already contains useful natural
Markdown blocks. Preserve that answer byte-for-byte, index its paragraphs, lists,
headings, and fenced code locally, bind introducing prose to the structured block
that follows it, and keep every indexed unit mandatory. If natural boundaries are
insufficient or separating an action from its warning could be unsafe, expose the
answer as one indivisible block. Claim zero incremental model usage only when
the viewport reuses the same completed one-shot turn and navigation is intercepted
locally.

When the host declares **intent-aware viewport routing**, treat control words as
internal opcodes rather than required user vocabulary. Preserve the person's raw
utterance and let the host decide whether an exact continuation, exact retrieval,
map, or consolidation satisfies it. If the request asks for new explanation,
reasoning, revision, or action, accept the host's `model_required` result and
fork the dormant authoring context with the current viewport pointer. Do not ask
the person to choose between local and model-backed paths.

When the host exposes a unified **reenter** path, send every natural follow-up
through it. The host first attempts exact local routing and starts no turn when
that succeeds. Only a `model_required` result may fork the retained thread. The
source thread remains immutable. The primary model receives the raw utterance
inside a hidden compiled follow-up with the exact current slice. A turn-level
response schema bounds the semantic delta; only its Markdown response field
becomes a fresh transparent viewport linked to its parent.

When the host declares **compiled capture** support, keep the user's request
verbatim and put only delivery metadata in the host sidecar. Use the host's exact
invisible section/detail marker grammar; do not expose or explain its markers to
the user. Treat the canonical marker-free response as user-visible content while
retaining raw and canonical integrity hashes locally. A malformed marker contract
must fall back to one indivisible answer rather than inferred boundaries.

When `create_lean_answer_capsule` is available, prefer it for stable answers that
can be composed from ordered sections. Author each brief and extension once; let
the buffer concatenate those exact sections for **full** without generating a
duplicate synthesis. Use `create_answer_capsule` only when a separately authored
polished synthesis is materially necessary. Store only user-visible content, keep
critical warnings on every node they govern, and never claim that an ordinary chat
control avoided a model call.

While a capsule is active, use `navigate_answer_capsule` only for exact navigation
over unchanged content. Mark it stale and return to primary-model reasoning when
the user adds facts, changes a constraint, disputes a premise, asks beyond the
graph, or matches a capsule requery trigger. If the tools are unavailable, say
local buffering is unavailable and fall back to the usage guard.

Apply the same stale boundary to a captured answer. Only a direct host or CLI
navigation action is local; a control typed into the ordinary composer remains a
model turn unless the host explicitly intercepts it.

Read `references/token-efficiency.md` only when evaluating cost, designing
prefetching, or implementing usage-aware behavior.

## Evaluate the alpha

Read `references/evaluation.md` when testing or revising the skill. Keep dogfood
results outside the skill so evaluation history does not bias normal use.
