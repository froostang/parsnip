# Alpha evaluation

## Acceptance checks

- First response provides task value before control education.
- Skipped calibration starts at level 1.
- **next** advances without changing density.
- **more** and **less** change exactly one level and affect current content.
- **map** restores orientation without changing density.
- Natural-language controls behave like their explicit equivalents.
- **full answer** applies once and restores the prior density.
- Risky actions keep warnings, prerequisites, consequences, and verification
  together.
- Automatic changes require three aligned signals, disclose the change, and honor
  the cooldown.
- Timing alone never changes density.
- Voice matching feels natural rather than mimicked; **neutral voice** resets it
  without changing density.
- Token usage is lower, neutral, higher, or explicitly unverified against an
  equivalent concise one-shot baseline.

## Task coverage

Run at least one realistic task in each category:

1. debugging;
2. project planning;
3. learning;
4. document review; and
5. decision-making.

Include an interrupted calibration, a natural-language control, a full-answer
request, a safety override, an automatic adjustment, a reminder, and a context
resume across the set.

## Trigger checks

The alpha must activate for explicit `$parsnip` requests. Because implicit
invocation is disabled, it must not pace ordinary requests, infer activation from
mentions of attention or accessibility needs, or override a request for a normal
complete answer.

Record evaluation transcripts outside this skill directory to avoid leaking prior
results into ordinary use.
