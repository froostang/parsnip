# Parsnip formative user testing

The next product question is whether Parsnip improves orientation and task
completion enough to justify its added interaction and potential AI usage. This is
a formative protocol, not a clinical study or accessibility certification.

## Participant disclosure

Before the task, tell the participant:

> Parsnip reveals AI responses in smaller pieces and may use more AI tokens or
> cost more than a single complete response. Some navigation can reuse existing
> text locally, while requests for new reasoning require another model turn. We
> are testing whether the pacing is useful enough to justify that tradeoff.

Participation should be voluntary. A participant may stop, skip a question, or
switch to a normal complete answer at any time.

## Session shape

Use a 20–30 minute, low-risk task the participant genuinely wants to complete.
Avoid medical, legal, financial, employment, crisis, or other high-stakes tasks in
early testing. Do not ask for secrets, personal records, or proprietary material.

For comparisons, use both of these conditions and alternate which comes first
across participants:

1. Parsnip with its normal controls; and
2. ordinary Codex with a concise complete-answer request.

Keep the task outcome equivalent. Do not coach the participant to use Parsnip's
exact control vocabulary; natural requests are part of the test.

## Observe

Record compact observations rather than a transcript:

- Did the first response provide immediate task value?
- Could the participant say what the current focus and next move were?
- Did **next**, requests for depth, simplification, and map-like orientation match
  their natural intent?
- Did they reach a decision, artifact, or completed next action?
- Where did they lose orientation or feel slowed down?
- Did critical context remain attached to risky actions?
- Would they choose Parsnip again for a similar task?
- After seeing the usage disclosure, was the experience worth the tradeoff to
  them?

When the participant knowingly agrees, record model calls and the usage metadata
available from the product. Do not infer reading time, attention, abandonment, or
emotion from response timing.

## End-of-session questions

Ask in plain language:

1. What, if anything, felt easier with Parsnip?
2. What felt slower, repetitive, or harder?
3. Did you ever want the whole answer sooner?
4. Did the controls behave the way you expected?
5. Knowing it may increase AI usage, when would you still choose it?
6. What would make you avoid it?

## Minimal session record

Store only what is needed:

```text
Participant code:
Task category:
Comparison order:
Outcome completed: yes / partial / no
First response useful: yes / partial / no
Orientation: 1–5
Control fit: 1–5
Would use again: yes / maybe / no
Usage tradeoff acceptable: yes / depends / no
Model calls and reported usage, if consented:
One observed benefit:
One observed failure:
One product change:
```

Keep the participant-code key, consent record, raw notes, and usage export outside
the public repository. Commit only aggregated, de-identified findings with small
cells suppressed when they could identify someone.

## Decision rule

Do not optimize token mechanics indefinitely without user evidence. After a small
formative round, continue only if participants can identify a meaningful
orientation or completion benefit and some say that benefit is worth the disclosed
usage tradeoff. Treat confusion, unwanted friction, or unwillingness to bear the
tradeoff as product evidence—not participant failure.
