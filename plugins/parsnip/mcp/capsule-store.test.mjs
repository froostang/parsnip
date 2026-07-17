import assert from "node:assert/strict";
import { execFile } from "node:child_process";
import { mkdtemp, readdir, rm, stat } from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import test from "node:test";
import { promisify } from "node:util";
import { CapsuleStore, validateCapsule } from "./capsule-store.mjs";

const execFileAsync = promisify(execFile);

function sampleCapsule() {
  return {
    version: 1,
    focus: "Understand a small release plan",
    thesis: "Ship the safe core before optional automation.",
    nodes: [
      {
        id: "orient",
        title: "The core",
        kind: "orientation",
        parent_id: null,
        brief: "Start with a manual release path.",
        detail: "A manual path establishes the contract before adding automation.",
        warnings: [],
        depends_on: [],
      },
      {
        id: "verify",
        title: "Verification",
        kind: "checkpoint",
        parent_id: "orient",
        brief: "Verify the artifact before release.",
        detail: "Run the complete validation suite and inspect the generated artifact.",
        warnings: ["Do not release an unverified artifact."],
        depends_on: ["orient"],
      },
      {
        id: "ship",
        title: "Ship",
        kind: "action",
        parent_id: "verify",
        brief: "Publish after verification passes.",
        detail: "Publish once, then monitor the defined success signal.",
        warnings: ["Do not release an unverified artifact."],
        depends_on: ["verify"],
      },
    ],
    sequence: ["orient", "verify", "ship"],
    final_synthesis: "Validate the artifact, publish it once, and monitor the result.",
    requery_triggers: ["The release target changes.", "Validation fails."],
  };
}

function sampleLeanCapsule() {
  return {
    version: 2,
    focus: "Understand a small release plan",
    thesis: "Ship the safe core before optional automation.",
    nodes: [
      {
        id: "orient",
        title: "The core",
        kind: "orientation",
        parent_id: null,
        brief: "Start with a manual release path.",
        extension: "This establishes the contract before adding automation.",
        warnings: [],
        depends_on: [],
      },
      {
        id: "ship",
        title: "Ship",
        kind: "action",
        parent_id: "orient",
        brief: "Publish only after verification passes.",
        extension: "Monitor the defined success signal after publishing.",
        warnings: ["Do not release an unverified artifact."],
        depends_on: ["orient"],
      },
    ],
    sequence: ["orient", "ship"],
    requery_triggers: ["The release target changes.", "Validation fails."],
  };
}

async function withStore(fn, options = {}) {
  const directory = await mkdtemp(path.join(os.tmpdir(), "parsnip-store-test-"));
  try {
    await fn(new CapsuleStore({ directory, ...options }), directory);
  } finally {
    await rm(directory, { recursive: true, force: true });
  }
}

test("creates, persists, navigates, consolidates, and closes a capsule", async () => {
  await withStore(async (store, directory) => {
    const created = await store.create(sampleCapsule());
    assert.equal(created.node.id, "orient");
    assert.equal(created.node.content, "Start with a manual release path.");
    assert.equal(created.progress.remaining, 2);

    const filename = path.join(directory, `${created.session_id}.json`);
    assert.equal((await stat(filename)).mode & 0o777, 0o600);

    const detailed = await store.navigate(created.session_id, "more");
    assert.equal(detailed.node.expanded, true);
    assert.match(detailed.node.content, /establishes the contract/);

    const next = await store.navigate(created.session_id, "next");
    assert.equal(next.node.id, "verify");
    assert.deepEqual(next.warnings, ["Do not release an unverified artifact."]);

    const map = await store.navigate(created.session_id, "map");
    assert.deepEqual(
      map.nodes.map(({ status }) => status),
      ["seen", "current", "parked"],
    );

    const full = await store.navigate(created.session_id, "full");
    assert.equal(full.status, "consolidated");
    assert.equal(full.warnings.length, 1);
    assert.equal(full.progress.remaining, 0);

    const reopened = new CapsuleStore({ directory });
    const status = await reopened.navigate(created.session_id, "status");
    assert.equal(status.node.id, "ship");
    assert.equal(status.progress.consolidated, true);

    const closed = await reopened.navigate(created.session_id, "close");
    assert.equal(closed.status, "closed");
    await assert.rejects(
      reopened.navigate(created.session_id, "status"),
      /not found|expired/,
    );
  });
});

test("rejects unknown, duplicate, and forward dependency nodes", () => {
  const unknown = sampleCapsule();
  unknown.extra = true;
  assert.throws(() => validateCapsule(unknown), /unsupported field/);

  const duplicate = sampleCapsule();
  duplicate.nodes[1].id = "orient";
  assert.throws(() => validateCapsule(duplicate), /unique ids/);

  const forward = sampleCapsule();
  forward.nodes[0].depends_on = ["ship"];
  assert.throws(() => validateCapsule(forward), /earlier node/);
});

test("lean capsules expand and consolidate without a duplicate synthesis", async () => {
  await withStore(async (store) => {
    const capsule = validateCapsule(sampleLeanCapsule());
    assert.equal(capsule.version, 2);
    assert.equal("final_synthesis" in capsule, false);

    const created = await store.create(capsule);
    assert.equal(created.node.content, "Start with a manual release path.");

    const expanded = await store.navigate(created.session_id, "more");
    assert.match(expanded.node.content, /manual release path[\s\S]*establishes/);

    const full = await store.navigate(created.session_id, "full");
    assert.match(full.content, /The core[\s\S]*Start with a manual release path/);
    assert.match(full.content, /Ship[\s\S]*Monitor the defined success signal/);
    assert.equal(full.warnings.length, 1);
  });
});

test("expires local capsules without exposing their contents", async () => {
  let now = 1_000;
  await withStore(
    async (store, directory) => {
      const created = await store.create(sampleCapsule());
      now = 1_011;
      await assert.rejects(store.navigate(created.session_id, "status"), /expired|not found/);
      assert.deepEqual(await readdir(directory), []);
    },
    { ttlMs: 10, clock: () => now },
  );
});

test("launcher exposes direct CLI navigation without starting the MCP server", async () => {
  await withStore(async (store, directory) => {
    const created = await store.create(sampleCapsule());
    const launcher = new URL("./launch.sh", import.meta.url).pathname;
    const { stdout } = await execFileAsync(
      "/bin/sh",
      [launcher, "cli", "navigate", created.session_id, "next"],
      {
        env: {
          ...process.env,
          PARSNIP_NODE: process.execPath,
          PARSNIP_BUFFER_DIR: directory,
        },
      },
    );

    const result = JSON.parse(stdout);
    assert.equal(result.status, "node");
    assert.equal(result.node.id, "verify");
  });
});
