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
- [`plugins/parsnip/skills/parsnip/SKILL.md`](plugins/parsnip/skills/parsnip/SKILL.md)
  is the canonical explicit-only alpha skill inside the distributable plugin.
- [`.agents/plugins/marketplace.json`](.agents/plugins/marketplace.json) exposes
  the plugin through a repo-local Codex marketplace.
- [CALIBRATION.md](CALIBRATION.md) defines non-blocking onboarding and optional
  calibration.
- [DOGFOOD.md](DOGFOOD.md) contains the five-session acceptance test.
- [TOKEN_EFFICIENCY.md](TOKEN_EFFICIENCY.md) defines the usage budget and bounded
  semantic-prefetch experiment.

## Current status

**Plugin-alpha stage:** the explicit-only skill is packaged as a skills-only Codex
plugin. The repo-local `.agents/skills/parsnip` path is a development symlink to
the packaged source, so local dogfood and distribution exercise the same files.
Continue dogfood, package-install, and usage validation before public release or
implicit use.
