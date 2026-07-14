# Parsnip

**Parseable snips for human-paced AI.**

Parsnip is an attention-aware pacing layer for AI output. It helps a person turn a
large, unrefined idea into small, finishable steps without flooding them with the
entire solution at once.

The core rule is simple:

> Give me the smallest useful piece now. Keep the larger picture safe. Let me
> choose when to reveal more.

Parsnip is designed for different reading speeds, attention constraints, working
memory limits, and the very human temptation to move faster than understanding. It
may begin as a Codex skill, a prompt protocol, or a small standalone tool. The
first goal is to validate the interaction before choosing the container.

## Start here

- [PLAN.md](PLAN.md) explains the product idea and staged roadmap.
- [NOW.md](NOW.md) contains only the current decision and next action.
- [PROTOCOL.md](PROTOCOL.md) contains the copy-paste v0.1 prompt.
- [`.agents/skills/parsnip/SKILL.md`](.agents/skills/parsnip/SKILL.md) is the
  canonical explicit-only alpha skill.
- [CALIBRATION.md](CALIBRATION.md) defines non-blocking onboarding and optional
  calibration.
- [DOGFOOD.md](DOGFOOD.md) contains the five-session acceptance test.
- [TOKEN_EFFICIENCY.md](TOKEN_EFFICIENCY.md) defines the usage budget and bounded
  semantic-prefetch experiment.

## Current status

**Alpha-skill stage:** the explicit-only repo-local skill is structurally valid;
continue dogfood and usage validation before personal installation or implicit use.
