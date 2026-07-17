# Contributing to Parsnip

Parsnip is an opt-in alpha. Contributions should improve orientation, task
completion, safety, usage transparency, or the quality of evidence—not merely add
more adaptive behavior.

## Before opening a change

- Keep `plugins/parsnip/` as the canonical installable artifact.
- Keep raw transcripts, participant identities, private tasks, and unredacted
  usage exports outside the repository.
- Do not claim medical, diagnostic, accessibility-certified, token-saving, or
  cost-saving outcomes without appropriate evidence.
- Preserve critical warnings and verification steps when changing pacing or
  navigation behavior.
- Add a synthetic test for routing, storage, protocol, or usage-accounting changes.

## Local checks

From the repository root:

```sh
python3 -m unittest evals.test_usage_harness
node --test plugins/parsnip/mcp/*.test.mjs
```

Validate the plugin manifest and skill before release using the current Codex
plugin-creator and skill-creator validators.

The usage harness can start billable model turns. Always inspect `--dry-run`,
select explicit paired conditions, use the same model across model-backed arms,
and write artifacts outside the repository.

## User-testing findings

Follow [docs/user-testing.md](docs/user-testing.md). Public findings should be
aggregated and de-identified, state the sample and limitations, and report negative
or mixed results alongside successes.
