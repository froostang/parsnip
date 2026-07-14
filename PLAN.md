# Parsnip product plan

## 1. The problem

AI can produce information much faster than a person can absorb, judge, and act
on it. A helpful answer can still fail when it arrives as a wall of text, exposes
too many branches, or encourages speed before understanding.

For people with attention or working-memory constraints, this creates a familiar
loop:

1. Start with an exciting, expansive idea.
2. Receive an equally expansive response.
3. Scan, lose the thread, or jump ahead.
4. Leave without completing the next concrete action.

Most interfaces optimize the model's output. Parsnip optimizes the handoff to the
human.

## 2. Product promise

Parsnip turns a large thought into a sequence of **parseable snips**: small units
that can be understood, decided on, or completed before the next unit appears.

It should make the user feel:

- oriented, not flooded;
- in control, not slowed down arbitrarily;
- able to act, not merely well-informed;
- confident that hidden context has not been lost.

## 3. Core interaction

Each Parsnip response delivers **one snip**: the smallest independently useful and
safe unit for the current task. A prose snip defaults to one sentence, but a snip
may instead be one question, one command with its warning, or a small code block
with the context required to use it safely.

The snip serves one focus and, when useful, makes the next move clear. These are
properties of the snip, not three mandatory blocks that add visual overhead.

The system keeps the larger map in the background and reveals it progressively.
The user can always ask to zoom out, speed up, slow down, or see the backlog.

One sentence is the starting dose, not a permanent ceiling. Parsnip can titrate the
size upward as the interaction demonstrates that the user is comfortable, then
back downward when needed.

The first prototype uses four observable density levels: one useful unit; two or
three sentences or a short list; one compact paragraph or a few related bullets;
and a concise structured answer. Density is clamped at Levels 1 and 4.

### Adaptive titration

Pacing is a feedback loop:

1. Start with one useful sentence.
2. Observe interaction signals after the snip.
3. Increase size gradually when repeated evidence supports it.
4. Decrease size gradually when repeated evidence supports it.
5. Preserve the user's explicit ability to request more or less at any time.

Signals available in any conversation include explicit feedback, requests for more
or less detail, repeated **next** actions, clarification requests, and completion
of the current action. Rereading, gaze, and abandonment are not observable in a
prompt or skill and must not be inferred. A future interface may measure additional
signals only with informed consent.

Timing is an inference signal, not a measurement of cognitive processing. A long
pause may mean reflection, interruption, sleep, or getting a glass of water. Rapid
input may suggest that the user wants greater density, but it could also mean
skimming or urgency. A timing event may justify a small calibration prompt; by
itself, it should not change the pace.

Adaptation should use sampled patterns across multiple interactions rather than
reacting to individual events. Both upward and downward changes should normally be
gradual. Explicit feedback such as “smaller,” “more detail,” or “this is too much”
can override that smoothing immediately.

The system should adapt conservatively. It must not treat fast clicking, silence,
or continued conversation as proof of comprehension. It should explain meaningful
pacing changes and allow adaptation to be reset or disabled. It should not require
physical, biometric, or invasive attention tracking.

After any automatic density change, Parsnip waits at least three content snips
before making another automatic change. This cooldown prevents oscillation.

### Confidence rules for pacing

- **Direct instruction:** change immediately.
- **Repeated behavioral pattern:** make one small change, then observe again.
- **Single ambiguous event:** keep the current size; optionally ask a calibration
  question at a natural boundary.
- **Conflicting evidence:** preserve the current size and prefer user control.

This smoothing prevents pacing from oscillating after every interaction while
still allowing Parsnip to learn a person's working rhythm over time.

### Opt-in initial calibration

At onset, Parsnip offers a short calibration after introducing its pacing
controls. Calibration is optional. It presents one to three samples
of increasing relational complexity, one at a time, and asks the user to respond
only after the meaning feels clear. After each sample, the user marks it **easy**,
**comfortable**, or **dense**.

Self-reported comfort seeds the initial pace. Timing remains optional and is used
only by an interface that can measure it reliably; a prompt or skill cannot use
message timing as reading time. The calibration provides an **interrupted**
response that discards a contaminated sample. The result selects a starting
density rather than producing a reading score or permanent profile. See
[CALIBRATION.md](CALIBRATION.md) for the proposed exchange.

### Controls

- **Next** — advance to the next snip without changing density.
- **More** — expand the current topic and raise density by one level.
- **Less** — restate the current snip more simply and lower density by one level.
- **Map** — briefly show the larger structure without changing normal density.

The plain-language request **full answer** bypasses progressive disclosure for the
current response. Ordinary requests such as “help me do this” or “save that branch”
remain part of natural conversation rather than becoming pacing controls.

Control awareness is required even though calibration is optional. At the start
of a session, Parsnip answers immediately at Level 1 and displays **next**,
**more**, **less**, **map**, and **calibrate** without requiring acknowledgment. If
the user skips calibration, output remains at the default until explicit commands
or repeated interaction patterns change it.

Controls should remain visible as lightweight interface elements when possible.
In plain chat, Parsnip gives compact reminders at natural boundaries—such as a
resumed session or evidence of pacing mismatch—rather than adding them to every
response. Natural-language equivalents must work so the commands are aids, not a
vocabulary test.

## 4. Design principles

### Comprehension sets the pace

Output length is based on what the user can process, not what the model can
generate.

### Progressive disclosure

Details appear when they become relevant or when the user asks for them.

### Preserve, then narrow

The system records the breadth of an idea before selecting one thread, so focus
does not feel like loss.

### Completion over momentum theater

A finished small action is more valuable than a beautiful, exhaustive plan that
is never used.

### Agency over paternalism

Parsnip offers pacing and gates; it does not trap the user in them. The user can
request the full answer or change the pace.

### Safety and completeness override pacing

A snip must include warnings, prerequisites, consequences, and verification needed
to make its action independently safe. Parsnip may exceed the current density when
splitting the information would make it misleading or dangerous. It explains the
exception briefly and never postpones a critical warning until after the risky
action.

### Token neutrality

Progressive disclosure must not quietly multiply the user's billable AI usage.
Parsnip counts repeated input, generated output, calibration, hidden generations,
and unused prefetches—not only visible words. By default it generates the current
snip plus a compact semantic map and performs no speculative model calls.

Bounded semantic prefetching may later batch likely next snips into an already
needed call, but only when measured savings from reduced context repetition exceed
wasted output. See [TOKEN_EFFICIENCY.md](TOKEN_EFFICIENCY.md).

### Calm language

The interface should avoid urgency, excessive headings, long menus, and repeated
encouragement.

### Familiar voice without impersonation

Parsnip gradually accommodates the user's observable language—such as vocabulary,
formality, rhythm, directness, metaphor, and preferred structure—so the response
requires less stylistic decoding. Voice adaptation is independent from density and
must never be described as access to the user's internal monologue.

Adapt only after repeated examples, keep the profile compact and session-local by
default, and honor requests such as “neutral voice,” “more formal,” or “don't match
my style” immediately. Preserve clarity, accuracy, and safety instead of copying
typos, fragmentation, hostility, self-criticism, or momentary distress.

## 5. What Parsnip is not

- Merely a summarizer: it manages sequence and action, not only word count.
- A rigid character limit: complexity and cognitive load matter more than length.
- A generic task manager: its special concern is the AI-to-human bandwidth gap.
- A system that hides information permanently: the larger map remains available.
- A medical intervention or substitute for accessibility research.

## 6. Smallest viable experiment

Before building software, test a written **Parsnip protocol** in real AI
conversations.

### Prototype behavior

Given a large or ambiguous request, the prototype:

1. Selects one immediate focus and records other branches in a compact map.
2. Returns the first useful and safe snip immediately at Level 1.
3. Shows the controls without requiring acknowledgment or calibration.
4. Advances at the current density with **next**.
5. Changes density explicitly with **more** or **less**, or conservatively after a
   repeated pattern and a cooldown.
6. Reveals the preserved structure with **map** and allows **full answer** as an
   escape hatch.
7. Periodically restates progress so the user does not need to hold the map.

### First test scenario

Use Parsnip to design Parsnip. Continue this project conversation in short snips
and note moments when the response is:

- too long;
- too small to be useful;
- missing necessary context;
- making too many decisions at once;
- successfully producing a completed action.

## 7. Key product questions

Early experiments should answer:

1. What makes a snip feel complete rather than artificially truncated?
2. How does the system detect overload without pretending to read the user's mind?
3. What information must remain visible for trust and orientation?
4. When should the system ask a question versus choose a safe default?
5. Does the user prefer explicit controls, natural conversation, or both?
6. Is Parsnip most valuable while planning, learning, deciding, or executing?

## 8. Measures of success

For an early prototype, prefer observable behavior over broad engagement metrics.

- The user can state the current focus without rereading the conversation.
- The first response contains useful task content rather than blocking onboarding.
- The user completes or decides the next move.
- The user rarely abandons a response midway through.
- The user can use **next**, **more**, **less**, and **map** without instruction
  beyond the compact reminder.
- Snip size grows only after positive signals and contracts after overload signals.
- Every command, irreversible choice, or risky action includes its critical context
  in the same snip.
- Important branches are preserved without dominating the current view.
- The number of open decisions decreases over a session.
- For the same completed outcome, median billable usage across dogfood scenarios
  does not exceed a concise one-shot baseline.
- Users rate the accommodated voice as familiar and easier to process without
  perceiving it as mimicry or impersonation.

A simple post-snip check can collect three signals: **too much**, **about right**,
or **too little**.

## 9. Risks

- **Over-gating:** the interaction becomes tedious or patronizing.
- **Fragmentation:** small pieces obscure relationships and cause context loss.
- **False personalization:** the system guesses cognitive capacity incorrectly.
- **Oscillation:** noisy signals repeatedly push the snip size up and down.
- **Surveillance creep:** better adaptation is used to justify invasive tracking.
- **Token amplification:** extra turns, repeated context, calibration, or unused
  prefetches cost more than the answer Parsnip replaces.
- **Uncanny mirroring:** style adaptation feels invasive, caricatured, or falsely
  claims insight into the user's inner state.
- **Planning forever:** decomposition replaces real action.
- **Novelty without differentiation:** ordinary concise prompting may solve most of
  the problem.
- **Accessibility mismatch:** different users need different kinds of pacing.

Each risk should become a test, not just a warning.

## 10. Staged roadmap

### Stage 1 — Conversation protocol

Write a compact set of behavioral instructions. Test it manually in several real
tasks and record pacing feedback.

**Exit condition:** the interaction repeatedly helps produce a concrete next action
without the user needing to restate the pacing preference.

### Stage 2 — Codex skill prototype

Package the proven protocol as a local skill with clear triggers, controls, and a
small state format.

**Exit condition:** the skill behaves consistently across planning, learning, and
execution conversations.

### Stage 3 — Standalone interaction prototype

Only if the skill reveals a need for stronger UI, prototype a focused interface
with progressive reveal, a persistent map, parked branches, and pace controls.

**Exit condition:** the interface adds measurable value beyond the conversational
skill.

### Stage 4 — Personalization and evaluation

Explore user-selected reading pace, adaptive snip sizing, accessibility settings,
and privacy-respecting local history.

## 11. Near-term backlog

Keep this ordered. Work on only the first uncompleted item.

- [x] Choose the default prose snip: one complete, useful sentence within an
  independently safe unit.
- [x] Define initial signal rules: direct instructions, sampled patterns, and
  timing-triggered calibration prompts.
- [x] Choose the smallest useful controls: **next**, **more**, **less**, and **map**.
- [x] Draft an opt-in onset calibration for initial pacing.
- [x] Make control awareness non-blocking, keep calibration optional, and define
  reminder behavior.
- [x] Draft Parsnip conversation protocol v0.1.
- [x] Dogfood protocol v0.1 in this project conversation.
- [x] Define a tiny session note for “too much / right / too little.”
- [x] Decide that evidence supports an explicit-only repo-local alpha, but not
  implicit activation or distribution.
- [x] Scaffold and structurally validate an explicit-only repo-local alpha skill.
- [x] Forward-test first responses for debugging, learning, and technical decisions.
- [ ] Measure each dogfood session against a concise one-shot token baseline.
- [ ] Run five varied evaluation conversations.
- [ ] Review the transcripts for overload and completion patterns.
