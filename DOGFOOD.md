# Parsnip v0.1 dogfood

Use this sheet for five evaluation conversations before deciding whether to package
a skill.

## Acceptance checks

A session passes when:

- useful task content appears in the first response;
- skipping calibration begins at Level 1;
- **next** advances without changing density;
- **more** and **less** move exactly one level and affect the current content;
- **map** preserves orientation without changing density;
- natural-language equivalents work;
- **full answer** exits progressive disclosure for one response;
- critical context appears with every risky action;
- no automatic change is based on timing alone; and
- automatic changes are disclosed, reversible, and separated by a cooldown;
- no background or speculative model calls occur; and
- total billable usage does not exceed the concise one-shot baseline for the same
  completed outcome, or the result is explicitly marked unverified;
- accommodated language feels familiar without copying errors or implying access
  to the user's internal state; and
- **neutral voice** immediately resets stylistic accommodation without changing
  density.

## Five test tasks

1. **Debugging:** diagnose a failing test and propose a safe change.
2. **Planning:** reduce a large project idea to the next finishable action.
3. **Learning:** explain an unfamiliar technical concept from first principles.
4. **Document review:** extract decisions and risks from a long document.
5. **Decision:** compare options with meaningful tradeoffs and choose a next step.

Include at least one calibration, one interrupted calibration sample, one natural
language control, one map request, and one full-answer request across the five
sessions.

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
Voice fit: unfamiliar / natural / mimicry
Did neutral voice reset correctly? yes / no / not tested
```

## Decision after five sessions

Review patterns rather than isolated events. Package a Codex skill only if the
protocol consistently improves completion or orientation beyond simply asking the
AI to be concise.

## Evaluation privacy

Keep raw transcripts, participant details, private project ideas, local paths,
timestamps, provider identifiers, and unredacted usage exports out of the public
repository. Store private notes under `.dogfood-private/` or in `*.local.md` files,
which Git ignores.

Commit only synthetic fixtures or aggregated findings that cannot be traced to an
individual or confidential project. Review staged changes and commit metadata for
names, email addresses, locations, and secrets before every public push.
