import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { mkdtemp, readdir, rm, stat } from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import test from "node:test";
import {
  CaptureStore,
  carveMarkdown,
  compileCapturedResponse,
  compileViewportResponse,
} from "./capture-store.mjs";

const response = `# Release path

One-line orientation before the reveal sections.

## Prepare

Run validation before publishing; do not continue if it fails.

This longer explanation remains available through **more**.

\`\`\`sh
# This is code, not a section heading.
npm test
\`\`\`

## Ship

Publish only after validation passes, then verify the released artifact immediately.

Monitor the first defined success signal.
`;

async function withStore(fn, options = {}) {
  const directory = await mkdtemp(path.join(os.tmpdir(), "parsnip-capture-test-"));
  try {
    await fn(new CaptureStore({ directory, ...options }), directory);
  } finally {
    await rm(directory, { recursive: true, force: true });
  }
}

test("carves Markdown sections without rewriting exact response spans", () => {
  const sections = carveMarkdown(response);
  assert.equal(sections.length, 2);
  assert.deepEqual(sections.map(({ title }) => title), ["Prepare", "Ship"]);
  assert.equal(response.slice(sections[0].start, sections[0].end).includes("not a section heading"), true);
  assert.equal(response.slice(sections[0].start, sections[0].brief_end).includes("do not continue"), true);
  assert.equal(response.slice(sections[0].brief_end, sections[0].end).includes("longer explanation"), true);
  assert.equal(response.slice(sections[1].start, sections[1].brief_end).includes("verify the released"), true);
});

test("compiles marker releases into canonical visible text", () => {
  const raw = `# Primer

<!--p:s Core-->
## Core

A bloom filter can reject definite misses without storing every item.

<!--p:d-->
False positives are possible; false negatives are not when updates are correct.

<!--p:s Check-->
## Check

Verify membership elsewhere after a possible match.
`;
  const compiled = compileCapturedResponse(raw);
  assert.equal(compiled.protocol, "marker-v1");
  assert.equal(compiled.sections.length, 2);
  assert.deepEqual(compiled.sections.map(({ title }) => title), ["Core", "Check"]);
  assert.doesNotMatch(compiled.response, /<!--p:/);
  assert.match(
    compiled.response.slice(compiled.sections[0].start, compiled.sections[0].brief_end),
    /reject definite misses/,
  );
  assert.doesNotMatch(
    compiled.response.slice(compiled.sections[0].start, compiled.sections[0].brief_end),
    /False positives/,
  );
  assert.match(
    compiled.response.slice(compiled.sections[0].brief_end, compiled.sections[0].end),
    /False positives/,
  );
  assert.notEqual(compiled.raw_response_sha256, compiled.response_sha256);
});

test("ignores marker examples inside code fences", () => {
  const raw = `Keep this example literal:

\`\`\`markdown
<!--p:s Example-->
\`\`\`
`;
  const compiled = compileCapturedResponse(raw);
  assert.equal(compiled.protocol, "indivisible");
  assert.equal(compiled.response, raw);
});

test("fails safe when marker syntax is malformed or a brief is empty", () => {
  for (const raw of [
    "<!--p:section Wrong name-->\nContent.\n",
    "<!--p:s Empty-->\n<!--p:d-->\nOnly detail.\n",
  ]) {
    const compiled = compileCapturedResponse(raw);
    assert.equal(compiled.protocol, "indivisible");
    assert.equal(compiled.response, raw);
    assert.equal(compiled.sections.length, 1);
  }
});

test("stores both raw and canonical hashes for marker captures", async () => {
  const raw = "<!--p:s First-->\nA safe brief.\n<!--p:d-->\nExtra context.\n";
  await withStore(async (store) => {
    const created = await store.create(raw, { origin: "fixture" });
    assert.equal(created.protocol, "marker-v1");
    assert.notEqual(created.raw_response_sha256, created.response_sha256);
    assert.doesNotMatch(created.section.content, /Extra context/);

    const more = await store.navigate(created.session_id, "more");
    assert.match(more.section.content, /Extra context/);
    const full = await store.navigate(created.session_id, "full");
    assert.equal(full.content, "A safe brief.\nExtra context.\n");
    assert.equal(
      createHash("sha256").update(full.content, "utf8").digest("hex"),
      full.response_sha256,
    );
    assert.equal(
      createHash("sha256").update(raw, "utf8").digest("hex"),
      full.raw_response_sha256,
    );
  });
});

test("indexes an unchanged one-shot answer as a transparent viewport", async () => {
  const raw = `A Bloom filter answers definitely absent or possibly present.

- It stores a bit array.
- It uses several hashes.

Insert by setting every hashed position.

\`\`\`text
00000000

01000100
\`\`\`

Never clear shared bits in an ordinary Bloom filter.
`;
  const compiled = compileViewportResponse(raw);
  assert.equal(compiled.protocol, "viewport-v1");
  assert.equal(compiled.response, raw);
  assert.equal(compiled.raw_response_sha256, compiled.response_sha256);
  assert.equal(compiled.sections.length, 3);
  assert.match(raw.slice(0, compiled.sections[0].brief_end), /definitely absent/);
  assert.match(raw.slice(0, compiled.sections[0].brief_end), /bit array/);
  assert.doesNotMatch(raw.slice(0, compiled.sections[0].end), /Insert by setting/);
  assert.match(
    raw.slice(compiled.sections[1].start, compiled.sections[1].end),
    /00000000[\s\S]*01000100/,
  );

  await withStore(async (store) => {
    const created = await store.create(raw, { origin: "fixture" }, { mode: "viewport" });
    assert.equal(created.protocol, "viewport-v1");
    assert.match(created.section.content, /definitely absent/);
    assert.match(created.section.content, /bit array/);
    const more = await store.navigate(created.session_id, "more");
    assert.match(more.section.content, /Insert by setting/);
    assert.match(more.section.content, /00000000/);
    const next = await store.navigate(created.session_id, "next");
    assert.match(next.section.content, /Never clear shared bits/);
    const full = await store.navigate(created.session_id, "full");
    assert.equal(full.content, raw);
    assert.equal(full.response_sha256, compiled.response_sha256);
  });
});

test("keeps a colon-ended introduction with its structured block", () => {
  const raw = `Suppose the array starts empty:

\`\`\`text
00000000
\`\`\`

The tradeoffs are:

- More bits use more memory.
- More items increase collisions.
`;
  const compiled = compileViewportResponse(raw);
  assert.equal(compiled.protocol, "viewport-v1");
  assert.equal(compiled.sections.length, 2);
  assert.match(raw.slice(0, compiled.sections[0].brief_end), /00000000/);
  assert.match(
    raw.slice(compiled.sections[1].start, compiled.sections[1].brief_end),
    /More bits/,
  );
});

test("routes natural viewport requests without collapsing semantic intent", async () => {
  const raw = `## Repair plan

**Scope:** One bounded pilot.

### Non-goals

No microwaves or hazardous materials.

### Budget

Spend no more than $600.

### Immediate action

Volunteer A confirms the venue in writing.
`;
  await withStore(async (store) => {
    const created = await store.create(
      raw,
      { origin: "fixture", thread_id: "thread-planning-1", resumable: "true" },
      { mode: "viewport" },
    );

    const continued = await store.route(created.session_id, "hmm ok");
    assert.equal(continued.status, "section");
    assert.equal(continued.routing.intent, "continue");
    assert.equal(continued.routing.operation, "next");
    assert.match(continued.section.content, /Non-goals/);

    const retrieved = await store.route(created.session_id, "show me the budget");
    assert.equal(retrieved.status, "section");
    assert.equal(retrieved.routing.intent, "retrieve");
    assert.equal(retrieved.routing.operation, "jump");
    assert.match(retrieved.section.content, /\$600/);

    const action = await store.route(created.session_id, "what's the immediate action?");
    assert.equal(action.routing.intent, "retrieve");
    assert.match(action.section.content, /confirms the venue/);

    const deeper = await store.route(created.session_id, "Why exclude microwaves?");
    assert.equal(deeper.status, "model_required");
    assert.equal(deeper.routing.intent, "semantic_expansion");
    assert.equal(deeper.routing.local, false);
    assert.equal(deeper.escalation.resumable, true);
    assert.equal(deeper.escalation.thread_id, "thread-planning-1");
    assert.match(deeper.escalation.current.title, /Immediate action/);
    assert.match(deeper.escalation.current.content, /confirms the venue/);

    const full = await store.route(created.session_id, "show me everything");
    assert.equal(full.status, "consolidated");
    assert.equal(full.routing.intent, "consolidate");
    assert.equal(full.content, raw);
  });
});

test("captures, navigates, restores the exact full answer, and closes", async () => {
  await withStore(async (store, directory) => {
    const created = await store.create(response, { origin: "fixture" });
    const expectedHash = createHash("sha256").update(response, "utf8").digest("hex");
    assert.equal(created.response_sha256, expectedHash);
    assert.equal(created.raw_response_sha256, expectedHash);
    assert.equal(created.protocol, "markdown-v1");
    assert.equal(created.section.title, "Prepare");
    assert.match(created.section.content, /do not continue if it fails/);
    assert.doesNotMatch(created.section.content, /longer explanation/);

    const filename = path.join(directory, `${created.session_id}.json`);
    assert.equal((await stat(directory)).mode & 0o777, 0o700);
    assert.equal((await stat(filename)).mode & 0o777, 0o600);

    const more = await store.navigate(created.session_id, "more");
    assert.match(more.section.content, /longer explanation/);
    assert.match(more.section.content, /npm test/);

    const next = await store.navigate(created.session_id, "next");
    assert.equal(next.section.title, "Ship");
    assert.match(next.section.content, /validation passes/);

    const map = await store.navigate(created.session_id, "map");
    assert.deepEqual(map.sections.map(({ status }) => status), ["seen", "current"]);

    const full = await store.navigate(created.session_id, "full");
    assert.equal(full.content, response);
    assert.equal(full.response_sha256, expectedHash);
    assert.deepEqual(full.exact_span, { start: 0, end: response.length });

    const closed = await store.navigate(created.session_id, "close");
    assert.equal(closed.status, "closed");
    await assert.rejects(store.navigate(created.session_id, "status"), /not found|expired/);
  });
});

test("falls back to one indivisible block when headings are absent", async () => {
  const plain = "One complete paragraph.\n\nA second paragraph with a warning.";
  const sections = carveMarkdown(plain);
  assert.equal(sections.length, 1);
  assert.equal(sections[0].brief_end, plain.length);

  await withStore(async (store) => {
    const created = await store.create(plain);
    assert.equal(created.section.content, plain);
    const more = await store.navigate(created.session_id, "more");
    assert.equal(more.section.content, plain);
  });
});

test("falls back to one indivisible block when only non-contract headings exist", () => {
  const nonContract = "### Setup\n\nSuppose there is a risky operation.\n\n### Action\n\nDo it.";
  const sections = carveMarkdown(nonContract);
  assert.equal(sections.length, 1);
  assert.equal(sections[0].start, 0);
  assert.equal(sections[0].brief_end, nonContract.length);
  assert.equal(sections[0].end, nonContract.length);
});

test("expires captured answers", async () => {
  let now = 100;
  await withStore(
    async (store, directory) => {
      const created = await store.create(response);
      now = 111;
      await assert.rejects(store.navigate(created.session_id, "status"), /expired|not found/);
      assert.deepEqual(await readdir(directory), []);
    },
    { ttlMs: 10, clock: () => now },
  );
});
