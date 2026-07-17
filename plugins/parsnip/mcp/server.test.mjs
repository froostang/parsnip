import assert from "node:assert/strict";
import { spawn } from "node:child_process";
import { mkdtemp, rm } from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import readline from "node:readline";
import test from "node:test";

function sampleCapsule() {
  return {
    version: 1,
    focus: "Explain a cache",
    thesis: "A cache trades freshness and memory for faster reuse.",
    nodes: [
      {
        id: "core",
        title: "Core idea",
        kind: "orientation",
        parent_id: null,
        brief: "A cache keeps reusable results close.",
        detail: "It avoids repeating slower work when the saved result remains valid.",
        warnings: [],
        depends_on: [],
      },
      {
        id: "tradeoff",
        title: "Tradeoff",
        kind: "mechanism",
        parent_id: "core",
        brief: "Invalidation controls staleness.",
        detail: "Expiration and explicit invalidation bound how long stale values survive.",
        warnings: ["Do not treat cached authorization decisions as permanently valid."],
        depends_on: ["core"],
      },
    ],
    sequence: ["core", "tradeoff"],
    final_synthesis: "Cache reusable results, then invalidate them when their assumptions change.",
    requery_triggers: ["The consistency requirement changes."],
  };
}

function sampleLeanCapsule() {
  return {
    version: 2,
    focus: "Explain a cache",
    thesis: "A cache trades freshness and memory for faster reuse.",
    nodes: [
      {
        id: "core",
        title: "Core idea",
        kind: "orientation",
        parent_id: null,
        brief: "A cache keeps reusable results close.",
        extension: "It avoids repeating slower work while a result remains valid.",
        warnings: [],
        depends_on: [],
      },
      {
        id: "tradeoff",
        title: "Tradeoff",
        kind: "mechanism",
        parent_id: "core",
        brief: "Invalidation controls staleness.",
        extension: "Expiration bounds how long stale values survive.",
        warnings: ["Do not treat cached authorization as permanently valid."],
        depends_on: ["core"],
      },
    ],
    sequence: ["core", "tradeoff"],
    requery_triggers: ["The consistency requirement changes."],
  };
}

test("stdio MCP server advertises and executes capsule tools", async () => {
  const directory = await mkdtemp(path.join(os.tmpdir(), "parsnip-server-test-"));
  const child = spawn("/bin/sh", [new URL("./launch.sh", import.meta.url).pathname], {
    env: {
      ...process.env,
      PARSNIP_BUFFER_DIR: directory,
      PARSNIP_NODE: process.execPath,
    },
    stdio: ["pipe", "pipe", "pipe"],
  });
  const lines = readline.createInterface({ input: child.stdout, crlfDelay: Infinity });
  const pending = new Map();
  lines.on("line", (line) => {
    const message = JSON.parse(line);
    const waiter = pending.get(message.id);
    if (waiter) {
      pending.delete(message.id);
      waiter.resolve(message);
    }
  });

  function request(id, method, params = {}) {
    return new Promise((resolve, reject) => {
      const timer = setTimeout(() => {
        pending.delete(id);
        reject(new Error(`Timed out waiting for ${method}`));
      }, 5_000);
      pending.set(id, {
        resolve: (message) => {
          clearTimeout(timer);
          resolve(message);
        },
      });
      child.stdin.write(`${JSON.stringify({ jsonrpc: "2.0", id, method, params })}\n`);
    });
  }

  try {
    const initialized = await request(1, "initialize", { protocolVersion: "2025-11-25" });
    assert.equal(initialized.result.serverInfo.name, "Parsnip Local Buffer");

    const listed = await request(2, "tools/list");
    assert.deepEqual(
      listed.result.tools.map(({ name }) => name),
      [
        "create_answer_capsule",
        "create_lean_answer_capsule",
        "navigate_answer_capsule",
      ],
    );

    const created = await request(3, "tools/call", {
      name: "create_answer_capsule",
      arguments: { capsule: sampleCapsule() },
    });
    const sessionId = created.result.structuredContent.session_id;
    assert.equal(created.result.structuredContent.node.id, "core");

    const next = await request(4, "tools/call", {
      name: "navigate_answer_capsule",
      arguments: { session_id: sessionId, action: "next" },
    });
    assert.equal(next.result.structuredContent.node.id, "tradeoff");
    assert.match(next.result.content[0].text, /authorization decisions/);

    const lean = await request(5, "tools/call", {
      name: "create_lean_answer_capsule",
      arguments: { capsule: sampleLeanCapsule() },
    });
    const leanSessionId = lean.result.structuredContent.session_id;
    const leanFull = await request(6, "tools/call", {
      name: "navigate_answer_capsule",
      arguments: { session_id: leanSessionId, action: "full" },
    });
    assert.match(leanFull.result.structuredContent.content, /Core idea/);
    assert.match(leanFull.result.structuredContent.content, /Tradeoff/);
  } finally {
    child.kill("SIGTERM");
    lines.close();
    await rm(directory, { recursive: true, force: true });
  }
});
