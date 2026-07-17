# Parsnip repository guidance

## Source of truth

- Treat this Git repository as the durable source of truth.
- Treat `plugins/parsnip/` as the canonical installable plugin artifact.
- Treat `.agents/plugins/marketplace.json` as the repository marketplace catalog.
- Never edit files under `~/.codex/plugins/cache/`; those are generated installed
  snapshots and are replaced during reinstall or marketplace upgrade.
- Do not reintroduce a duplicate `.agents/skills/parsnip` copy or symlink. The
  distributable skill lives inside the plugin.

## Development workflow

1. Make source changes in this repository.
2. Add or update focused synthetic tests.
3. Run the Python and Node test suites.
4. Validate the skill and plugin manifests with the current Codex creator tools.
5. For a local plugin pickup test, update the plugin cachebuster, reinstall
   `parsnip@parsnip`, and start a new Codex task.
6. Review and commit the repository changes through the normal Git/GitHub flow.

Do not edit marketplace configuration in `~/.codex/config.toml` by hand. Use
`codex plugin marketplace` and `codex plugin` commands.

## Required checks

```sh
python3 -m unittest evals.test_usage_harness
node --test plugins/parsnip/mcp/*.test.mjs
```

Also run the plugin-creator validator for `plugins/parsnip/` and the skill-creator
validator for `plugins/parsnip/skills/parsnip/` before release.

## Evaluation and privacy

- Inspect usage-evaluation commands with `--dry-run` before starting model calls.
- Select explicit paired conditions and use the same model across model-backed
  conditions.
- Write raw evaluation artifacts outside this repository.
- Never commit raw transcripts, participant identities, private tasks, secrets,
  local absolute paths, thread identifiers, or unredacted usage exports.
- Publish only synthetic fixtures or aggregated, de-identified findings.
- Disclose increased or unverified AI usage; do not claim token or cost savings
  without equivalent-outcome evidence.

## Documentation

Keep these surfaces consistent when behavior changes:

- `README.md` for the public pitch, install path, status, and usage disclosure;
- `docs/user-testing.md` for formative research;
- `docs/design/` for architecture and measurement rationale;
- `evals/README.md` for reproducible evaluation history; and
- the packaged skill and its references for runtime behavior.
