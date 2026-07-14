# Parsnip onboarding and calibration

The canonical alpha calibration is
[`plugins/parsnip/skills/parsnip/references/calibration.md`](plugins/parsnip/skills/parsnip/references/calibration.md).
This document retains the product-design rationale and interface ideas.

Calibration is optional. It must never delay the user's first useful answer unless
the user explicitly asks to calibrate before starting work.

## Non-blocking control introduction

Answer the user's request immediately at the default density, then show a compact
control reminder outside the content snip:

> Pace: **next · more · less · map · calibrate**

Do not require **ready** or any other acknowledgment. Natural-language equivalents
such as “continue,” “go deeper,” “slow down,” and “show me the big picture” must
work too.

In a graphical interface, keep the controls visible near the response. In plain
conversation, show the reminder on the first response, after a density change,
after a resumed session, or roughly every four content snips. Do not count the
reminder as part of the snip.

## Optional calibration prompt

When the user chooses **calibrate**, show:

> I can estimate a comfortable starting density with up to three small samples.
> I’ll show one at a time. When its meaning feels clear, reply **easy**,
> **comfortable**, **dense**, or **interrupted**. You can reply **stop** at any
> time. This is a rough pacing estimate, not a reading or ability score.

If the user stops, return to their task immediately. Use the default density or the
most recent comfortable result.

## Sample sequence

Present one sample at a time. Each user response both signals comprehension and
rates the sample, avoiding a second question.

### Sample 1 — one relation

> A blue token opens the garden gate.

### Sample 2 — two conditions

> The morning report goes to the team lead, unless it contains payroll data, in
> which case it goes only to finance.

### Sample 3 — compact system

> The workshop opens when a member scans a badge. Guests also need a member escort,
> while deliveries use the side entrance before noon; the manager's key overrides
> all three rules during an emergency.

The independent fictional systems reduce carryover between samples. They increase
the number of relationships the reader must hold, not merely the word count.

## Initial estimate

- **Dense:** stop and use the previous level, or Level 1 if it is the first sample.
- **Comfortable:** record the level and offer the next sample.
- **Easy:** offer the next sample; if all are easy, begin at Level 3.
- **Interrupted:** discard the sample and offer to repeat or continue without it.

Timing may supplement these labels only when the interface reliably measures from
render completion to a low-friction response control. Chat-message timing includes
typing, network delay, and interruptions, so a prompt-only or skill prototype must
not use it to set density.

The result seeds the current session. It is not a permanent profile, diagnosis, or
claim that comprehension was measured.

## Optional research check

During product research, a participant may restate a sample's rule in their own
words. Present this as testing Parsnip's clarity, not testing the person. Never
require it during ordinary use.
