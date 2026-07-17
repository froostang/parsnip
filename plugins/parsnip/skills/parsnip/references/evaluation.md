# Alpha evaluation

## Acceptance checks

- First response provides task value before control education.
- Skipped calibration starts at level 1.
- **next** advances without changing density.
- **more** and **less** change exactly one level and affect current content.
- **map** restores orientation without changing density.
- Natural-language controls behave like their explicit equivalents.
- **full answer** applies once and restores the prior density.
- After one continuation, the usage guard offers compact consolidation; another
  content request consolidates by default unless the user explicitly keeps pacing.
- **finish compactly** avoids repeating earlier snips and resets on a new focus.
- Local capsule mode activates only after explicit buffering intent or a declared
  direct-navigation host path.
- Capsule briefs, details, maps, and synthesis are selected without local rewriting;
  warnings remain attached and changed premises make the capsule stale.
- Ordinary chat controls are never described as zero-call navigation, and timed
  delivery is not inferred from user timing.
- Risky actions keep warnings, prerequisites, consequences, and verification
  together.
- Automatic changes require three aligned signals, disclose the change, and honor
  the cooldown.
- Timing alone never changes density.
- The drift profile uses spontaneous user prose, not pasted or quoted material.
- Drift compatibility adapts meaning formation across multiple relevant dimensions,
  not just surface tone or punctuation.
- Inferred preferences require repeated evidence across messages, retain confidence
  and counterevidence, and explicit preference feedback applies immediately.
- A one-off metaphor does not become a concept map; promotion requires two evidence
  kinds across messages or explicit confirmation.
- Promoted concept maps preserve source, target, relationship, context, confidence,
  counterevidence, and recency.
- Responses reuse the learned relationship when helpful without parroting the
  metaphor or forcing it onto unrelated topics.
- Distinctive punctuation and formatting stay off without user evidence.
- Drift compatibility reduces translation effort without mimicry or claims about
  private thought; **neutral drift** and **neutral voice** reset it without changing
  density.
- Token usage is lower, neutral, higher, or explicitly unverified against an
  equivalent concise one-shot baseline.
- Score the complete answer and the progressive trajectory separately. The
  trajectory must keep the initial bite useful, make each control match its
  semantic intent, avoid skipped requirements, and surface an immediate action
  soon enough to be usable. Exact **full** reconstruction does not compensate for
  a confusing reveal sequence.
- For a transparent viewport, distinguish **more content** from semantic
  **go deeper**. Adjacent exact spans are not automatically a deeper treatment of
  the current topic; record that limitation instead of awarding a pacing pass.

## Task coverage

Run at least one realistic task in each category:

1. debugging;
2. project planning;
3. learning;
4. document review; and
5. decision-making.

Include an interrupted calibration, a natural-language control, a full-answer
request, a safety override, an automatic adjustment, a reminder, a context resume,
an automatic drift adaptation spanning more than one dimension, explicit reasoning
and punctuation preferences, a promoted concept map, an ignored one-off metaphor,
concept-map counterevidence, conflicting style evidence, a pasted-text confound,
and a neutral-drift reset across the set.

## Trigger checks

The alpha must activate for explicit `$parsnip` requests. Because implicit
invocation is disabled, it must not pace ordinary requests, infer activation from
mentions of attention or accessibility needs, or override a request for a normal
complete answer.

Record evaluation transcripts outside this skill directory to avoid leaking prior
results into ordinary use.
