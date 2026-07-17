#!/bin/sh
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)

ENTRYPOINT=server.mjs
if [ "${1:-}" = "cli" ]; then
  ENTRYPOINT=cli.mjs
  shift
elif [ "${1:-}" = "capture" ]; then
  ENTRYPOINT=capture-client.mjs
  shift
fi

if [ -n "${PARSNIP_NODE:-}" ] && [ -x "$PARSNIP_NODE" ]; then
  exec "$PARSNIP_NODE" "$SCRIPT_DIR/$ENTRYPOINT" "$@"
fi

if command -v node >/dev/null 2>&1; then
  exec "$(command -v node)" "$SCRIPT_DIR/$ENTRYPOINT" "$@"
fi

CODEX_BUNDLED_NODE="${HOME}/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node"
if [ -x "$CODEX_BUNDLED_NODE" ]; then
  exec "$CODEX_BUNDLED_NODE" "$SCRIPT_DIR/$ENTRYPOINT" "$@"
fi

printf '%s\n' \
  'Parsnip buffer could not locate Node.js. Set PARSNIP_NODE to a Node.js 18+ executable.' \
  >&2
exit 127
