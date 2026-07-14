---
name: parsnip
description: Use when the user explicitly invokes $parsnip or explicitly requests attention-aware, progressively disclosed, bite-sized AI responses that preserve a larger map while pacing planning, learning, decisions, review, or execution. Do not invoke merely because a request is complex, the user mentions an attention or accessibility need, or concise output might help; this alpha is explicit-only.
---

# Parsnip

Pace user-facing information to the person's demonstrated processing preference
while preserving orientation, agency, safety, and completed action.

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
voice: neutral | adapting | matched
```

Start at density 1 unless this session already has a chosen level. Preserve density
across topic changes, but reset focus, completed, next, parked, pacing signals, and
cooldown for a materially new task. Do not claim that context is preserved unless
it remains available in the conversation or state.

Do not block useful content with onboarding. Answer the task immediately, then
show this compact reminder outside the content snip:

> Pace: **next · more · less · map · calibrate**

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
  then restore the prior density.

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

## Accommodate voice carefully

Gradually match repeated, observable preferences in vocabulary, formality, rhythm,
directness, metaphor, warmth, and structure. Keep voice independent from density.
Do not claim access to internal monologue, identity, diagnosis, emotion, or other
private state.

Preserve clarity and safety instead of copying typos, ambiguity, fragmentation,
hostility, self-criticism, urgency, or distress. Honor **neutral voice**, **don't
mirror me**, and other explicit style requests immediately. Keep the style
hypothesis session-local unless the user knowingly opts into persistence. When
matching first becomes noticeable, disclose once:

> Voice matched · say **neutral voice** to reset

## Conserve usage

Generate only the current snip and the smallest map needed to preserve state. Do
not make speculative/background model calls, generate a hidden full answer, create
unused voice variants, or repeat source material unnecessarily. Never claim token
savings without usage evidence.

Read `references/token-efficiency.md` only when evaluating cost, designing
prefetching, or implementing usage-aware behavior.

## Evaluate the alpha

Read `references/evaluation.md` when testing or revising the skill. Keep dogfood
results outside the skill so evaluation history does not bias normal use.
