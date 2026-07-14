# Parsnip

**Parseable snips for human-paced AI.**

Parsnip is an attention-aware pacing layer for AI output. It helps a person turn a
large, unrefined idea into small, finishable steps without flooding them with the
entire solution at once.

The core rule is simple:

> Give me the smallest useful piece now. Keep the larger picture safe. Let me
> choose when to reveal more.

Parsnip is designed for different reading speeds, attention constraints, working
memory limits, and the very human temptation to move faster than understanding.
The current alpha is distributed as an explicit-only Codex skill inside a
skills-only plugin.

## Start here

- [`plugins/parsnip/skills/parsnip/SKILL.md`](plugins/parsnip/skills/parsnip/SKILL.md)
  is the canonical explicit-only alpha skill inside the distributable plugin.
- [`.agents/plugins/marketplace.json`](.agents/plugins/marketplace.json) exposes
  the plugin through a repo-local Codex marketplace.
- [`docs/design/calibration.md`](docs/design/calibration.md) explains non-blocking
  onboarding and optional calibration.
- [`docs/design/token-efficiency.md`](docs/design/token-efficiency.md) defines the
  usage budget and bounded semantic-prefetch experiment.
- [`evals/README.md`](evals/README.md) contains the sanitized acceptance criteria
  and evaluation template.

## Repository boundary

- `plugins/parsnip/` is the installable artifact and canonical runtime source.
- `docs/` contains stable public rationale that helps contributors understand the
  behavior without being loaded during ordinary skill use.
- `evals/` contains reproducible synthetic criteria and templates, never raw human
  sessions.
- Operational planning, prompt history, private ideas, transcripts, and raw usage
  measurements live outside this public repository.

## Current status

**Plugin-alpha stage:** the explicit-only skill is packaged as a skills-only Codex
plugin. The repo-local `.agents/skills/parsnip` path is a development symlink to
the packaged source, so local dogfood and distribution exercise the same files.
Continue fresh-task dogfood and usage validation before public release or implicit
use.
