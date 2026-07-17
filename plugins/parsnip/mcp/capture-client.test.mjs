import assert from "node:assert/strict";
import { execFile } from "node:child_process";
import { chmod, mkdtemp, rm, writeFile } from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import test from "node:test";
import { promisify } from "node:util";
import {
  compileCaptureInstructions,
  compileOrdinaryFollowupPrompt,
  compileReentryPrompt,
  extractStructuredReentryText,
  extractFinalAgentText,
  REENTRY_OUTPUT_SCHEMA,
} from "./capture-client.mjs";

const execFileAsync = promisify(execFile);

test("prefers the authoritative final agent message", () => {
  assert.equal(
    extractFinalAgentText([
      { type: "agentMessage", phase: "commentary", text: "Working." },
      { type: "agentMessage", phase: null, text: "Legacy intermediate." },
      { type: "agentMessage", phase: "final_answer", text: "Exact final." },
    ]),
    "Exact final.",
  );
});

test("compiles a compact delivery sidecar without rewriting the user request", () => {
  const instructions = compileCaptureInstructions({
    steering: "Prefer mechanism-first explanations.",
    targetOutputTokens: 320,
  });
  assert.match(instructions, /PARSNIP_CAPTURE_V1/);
  assert.match(instructions, /<!--p:s SHORT TITLE-->/);
  assert.match(instructions, /at most 320 visible output tokens/);
  assert.match(instructions, /mechanism-first/);
  assert.throws(
    () => compileCaptureInstructions({ targetOutputTokens: 64 }),
    /between 128 and 4096/,
  );
});

test("compiles the raw follow-up and current slice into a bounded turn envelope", () => {
  const prompt = compileReentryPrompt("Why exclude microwaves?", {
    title: "Non-goals",
    index: 1,
    total: 5,
    content: "Microwaves and high-voltage equipment are out of scope.",
    exact_span: { start: 120, end: 220 },
  });
  assert.match(prompt, /untrusted reference data/);
  assert.match(prompt, /"title":"Non-goals"/);
  assert.match(prompt, /Microwaves and high-voltage/);
  assert.match(prompt, /only the semantic delta/);
  assert.match(prompt, /RAW_USER_MESSAGE:\nWhy exclude microwaves/);
  assert.equal(REENTRY_OUTPUT_SCHEMA.properties.response.maxLength, 2400);
  assert.equal(
    extractStructuredReentryText('{"response":"A concise delta."}'),
    "A concise delta.",
  );
  assert.throws(() => extractStructuredReentryText("plain Markdown"), /schema-constrained JSON/);
});

test("compiles an ordinary follow-up with the same raw request and visible slice", () => {
  const prompt = compileOrdinaryFollowupPrompt("Go deeper", {
    title: "Scope and non-goals",
    index: 1,
    total: 8,
    content: "Accept small, portable household items.",
    exact_span: { start: 120, end: 180 },
  });
  assert.match(prompt, /previously completed answer/);
  assert.match(prompt, /Accept small, portable household items/);
  assert.match(prompt, /RAW_USER_MESSAGE:\nGo deeper/);
  assert.doesNotMatch(prompt, /only the semantic delta/);
});

test("launcher captures one fake app-server turn and navigates it locally", async () => {
  const directory = await mkdtemp(path.join(os.tmpdir(), "parsnip-capture-client-test-"));
  const captureDirectory = path.join(directory, "captures");
  const promptFile = path.join(directory, "request.md");
  const fakeServer = path.join(directory, "fake-app-server.mjs");
  const finalText = "# Cache\n\n<!--p:s Core-->\n## Core\n\nReuse a valid result; invalidate it when its assumptions change.\n\n<!--p:d-->\nThis avoids repeating work.\n\n<!--p:s Check-->\n## Check\n\nVerify freshness before relying on the cached value.\n";
  const visibleText = "# Cache\n\n## Core\n\nReuse a valid result; invalidate it when its assumptions change.\n\nThis avoids repeating work.\n\n## Check\n\nVerify freshness before relying on the cached value.\n";
  const fakeSource = `#!${process.execPath}
import readline from "node:readline";
const lines = readline.createInterface({ input: process.stdin, crlfDelay: Infinity });
const send = (message) => process.stdout.write(JSON.stringify(message) + "\\n");
if (!process.argv.includes('plugins."parsnip@personal".mcp_servers.parsnip-buffer.enabled=false')) process.exit(8);
lines.on("line", (line) => {
  const message = JSON.parse(line);
  if (message.method === "initialize") {
    send({ id: message.id, result: { userAgent: "fake", platformFamily: "unix", platformOs: "test" } });
  } else if (message.method === "thread/start") {
    if (message.params.approvalPolicy !== "never" || message.params.sandbox !== "read-only") process.exit(9);
    if (!message.params.developerInstructions.includes("one response")) process.exit(10);
    if (!message.params.developerInstructions.includes("PARSNIP_CAPTURE_V1")) process.exit(11);
    if (!message.params.developerInstructions.includes("at most 320 visible output tokens")) process.exit(12);
    send({ id: message.id, result: { thread: { id: "thread_test" }, model: "fake-model" } });
  } else if (message.method === "turn/start") {
    if (message.params.input?.[0]?.text !== "Explain cache invalidation.") process.exit(13);
    if (message.params.effort !== "none") process.exit(14);
    send({ id: message.id, result: { turn: { id: "turn_test", items: [], status: "inProgress" } } });
    const item = { id: "message_test", type: "agentMessage", phase: "final_answer", text: ${JSON.stringify(finalText)} };
    send({ method: "item/completed", params: { threadId: "thread_test", turnId: "turn_test", completedAtMs: 1, item } });
    send({ method: "turn/completed", params: { threadId: "thread_test", turn: { id: "turn_test", items: [item], status: "completed" } } });
    setTimeout(() => send({ method: "thread/tokenUsage/updated", params: { threadId: "thread_test", turnId: "turn_test", tokenUsage: { last: { inputTokens: 100, cachedInputTokens: 40, outputTokens: 20, reasoningOutputTokens: 5, totalTokens: 125 }, total: { inputTokens: 100, cachedInputTokens: 40, outputTokens: 20, reasoningOutputTokens: 5, totalTokens: 125 } } } }), 10);
  }
});
`;

  try {
    await writeFile(promptFile, "Explain cache invalidation.", "utf8");
    await writeFile(fakeServer, fakeSource, { encoding: "utf8", mode: 0o700 });
    await chmod(fakeServer, 0o700);
    const launcher = new URL("./launch.sh", import.meta.url).pathname;
    const env = {
      ...process.env,
      PARSNIP_NODE: process.execPath,
      PARSNIP_CAPTURE_DIR: captureDirectory,
      PARSNIP_CODEX_EXECUTABLE: fakeServer,
    };
    const { stdout } = await execFileAsync(
      "/bin/sh",
      [launcher, "capture", "run", "--allow-model-call", "--prompt-file", promptFile, "--target-output-tokens", "320"],
      { env },
    );
    const captured = JSON.parse(stdout);
    assert.equal(captured.source.origin, "codex_app_server");
    assert.equal(captured.source.model, "fake-model");
    assert.deepEqual(captured.capture_usage, {
      input_tokens: 100,
      cached_input_tokens: 40,
      output_tokens: 20,
      reasoning_output_tokens: 5,
    });
    assert.equal(captured.codex_turns, 1);
    assert.equal(captured.protocol, "marker-v1");
    assert.equal(captured.capture_raw_sha256, captured.raw_response_sha256);
    assert.notEqual(captured.raw_response_sha256, captured.response_sha256);
    assert.equal(captured.section.title, "Core");
    assert.match(captured.section.content, /invalidate it/);
    assert.doesNotMatch(captured.section.content, /avoids repeating work/);

    const fullResult = await execFileAsync(
      "/bin/sh",
      [launcher, "capture", "navigate", captured.session_id, "full"],
      { env },
    );
    assert.equal(JSON.parse(fullResult.stdout).content, visibleText);
  } finally {
    await rm(directory, { recursive: true, force: true });
  }
});

test("run requires explicit confirmation before starting a model turn", async () => {
  const directory = await mkdtemp(path.join(os.tmpdir(), "parsnip-capture-confirm-test-"));
  try {
    const promptFile = path.join(directory, "request.md");
    await writeFile(promptFile, "A request.", "utf8");
    const launcher = new URL("./launch.sh", import.meta.url).pathname;
    await assert.rejects(
      execFileAsync(
        "/bin/sh",
        [launcher, "capture", "run", "--prompt-file", promptFile],
        { env: { ...process.env, PARSNIP_NODE: process.execPath } },
      ),
      /allow-model-call/,
    );
  } finally {
    await rm(directory, { recursive: true, force: true });
  }
});

test("launcher ingests an ordinary response as a zero-model viewport", async () => {
  const directory = await mkdtemp(path.join(os.tmpdir(), "parsnip-viewport-client-test-"));
  try {
    const responseFile = path.join(directory, "response.md");
    const continueFile = path.join(directory, "continue.md");
    const response = "A useful orientation.\n\n- First fact.\n- Second fact.\n\nA later consequence.\n";
    await writeFile(responseFile, response, "utf8");
    await writeFile(continueFile, "okay", "utf8");
    const launcher = new URL("./launch.sh", import.meta.url).pathname;
    const env = {
      ...process.env,
      PARSNIP_NODE: process.execPath,
      PARSNIP_CAPTURE_DIR: path.join(directory, "captures"),
    };
    const { stdout } = await execFileAsync(
      "/bin/sh",
      [
        launcher,
        "capture",
        "viewport-file",
        responseFile,
        "--thread-id",
        "thread-viewport-1",
        "--resumable",
        "true",
      ],
      { env },
    );
    const created = JSON.parse(stdout);
    assert.equal(created.protocol, "viewport-v1");
    assert.equal(created.source.origin, "baseline_viewport");
    assert.equal(created.source.thread_id, "thread-viewport-1");
    assert.match(created.section.content, /useful orientation/);
    assert.match(created.section.content, /First fact/);
    assert.doesNotMatch(created.section.content, /later consequence/);

    const routed = await execFileAsync(
      "/bin/sh",
      [launcher, "capture", "reenter", created.session_id, "--prompt-file", continueFile],
      { env },
    );
    const routedResult = JSON.parse(routed.stdout);
    assert.equal(routedResult.routing.intent, "continue");
    assert.match(routedResult.section.content, /later consequence/);

    const deeper = await execFileAsync(
      "/bin/sh",
      [launcher, "capture", "route", created.session_id, "why does that matter?"],
      { env },
    );
    const deeperResult = JSON.parse(deeper.stdout);
    assert.equal(deeperResult.status, "model_required");
    assert.equal(deeperResult.escalation.resumable, true);

    const full = await execFileAsync(
      "/bin/sh",
      [launcher, "capture", "navigate", created.session_id, "full"],
      { env },
    );
    assert.equal(JSON.parse(full.stdout).content, response);
  } finally {
    await rm(directory, { recursive: true, force: true });
  }
});

test("launcher forks a dormant thread only when natural routing requires it", async () => {
  const directory = await mkdtemp(path.join(os.tmpdir(), "parsnip-reentry-client-test-"));
  try {
    const responseFile = path.join(directory, "response.md");
    const requestFile = path.join(directory, "request.md");
    const fakeServer = path.join(directory, "fake-app-server.mjs");
    const original = "A short orientation.\n\n## Limits\n\nDo not clear shared bits.\n";
    const enriched = "A deeper explanation.\n\n## Mechanism\n\nClearing a shared bit can invalidate another item.\n\n## Check\n\nVerify every inserted item still resolves.\n";
    const fakeSource = `#!${process.execPath}
import readline from "node:readline";
const lines = readline.createInterface({ input: process.stdin, crlfDelay: Infinity });
const send = (message) => process.stdout.write(JSON.stringify(message) + "\\n");
if (!process.argv.includes('plugins."parsnip@personal".mcp_servers.parsnip-buffer.enabled=false')) process.exit(20);
lines.on("line", (line) => {
  const message = JSON.parse(line);
  if (message.method === "initialize") {
    send({ id: message.id, result: { userAgent: "fake", platformFamily: "unix", platformOs: "test" } });
  } else if (message.method === "thread/fork") {
    if (message.params.threadId !== "thread-retained-1") process.exit(21);
    if (message.params.ephemeral !== undefined) process.exit(22);
    if (message.params.approvalPolicy !== "never" || message.params.sandbox !== "read-only") process.exit(23);
    if (Object.hasOwn(message.params, "developerInstructions")) process.exit(24);
    send({ id: message.id, result: { thread: { id: "thread-branch-1" }, model: "fake-model" } });
  } else if (message.method === "turn/start") {
    if (message.params.threadId !== "thread-branch-1") process.exit(26);
    if (!message.params.input?.[0]?.text.includes("RAW_USER_MESSAGE:\\nWhy does that matter?")) process.exit(27);
    if (!message.params.input?.[0]?.text.includes("A short orientation.")) process.exit(29);
    if (message.params.outputSchema?.properties?.response?.maxLength !== 2400) process.exit(30);
    if (Object.hasOwn(message.params, "effort")) process.exit(28);
    send({ id: message.id, result: { turn: { id: "turn_reentry", items: [], status: "inProgress" } } });
    const item = { id: "message_reentry", type: "agentMessage", phase: "final_answer", text: ${JSON.stringify(JSON.stringify({ response: enriched }))} };
    send({ method: "item/completed", params: { threadId: "thread-branch-1", turnId: "turn_reentry", completedAtMs: 1, item } });
    send({ method: "turn/completed", params: { threadId: "thread-branch-1", turn: { id: "turn_reentry", items: [item], status: "completed" } } });
    setTimeout(() => send({ method: "thread/tokenUsage/updated", params: { threadId: "thread-branch-1", turnId: "turn_reentry", tokenUsage: { last: { inputTokens: 80, cachedInputTokens: 60, outputTokens: 30, reasoningOutputTokens: 4, totalTokens: 114 }, total: { inputTokens: 80, cachedInputTokens: 60, outputTokens: 30, reasoningOutputTokens: 4, totalTokens: 114 } } } }), 10);
  }
});
`;
    await writeFile(responseFile, original, "utf8");
    await writeFile(requestFile, "Why does that matter?", "utf8");
    await writeFile(fakeServer, fakeSource, { encoding: "utf8", mode: 0o700 });
    await chmod(fakeServer, 0o700);
    const launcher = new URL("./launch.sh", import.meta.url).pathname;
    const env = {
      ...process.env,
      PARSNIP_NODE: process.execPath,
      PARSNIP_CAPTURE_DIR: path.join(directory, "captures"),
      PARSNIP_CODEX_EXECUTABLE: fakeServer,
    };
    const ingested = await execFileAsync(
      "/bin/sh",
      [
        launcher,
        "capture",
        "viewport-file",
        responseFile,
        "--thread-id",
        "thread-retained-1",
        "--resumable",
        "true",
      ],
      { env },
    );
    const sessionId = JSON.parse(ingested.stdout).session_id;

    await assert.rejects(
      execFileAsync(
        "/bin/sh",
        [launcher, "capture", "reenter", sessionId, "--prompt-file", requestFile],
        { env },
      ),
      /allow-model-call/,
    );

    const resumed = await execFileAsync(
      "/bin/sh",
      [
        launcher,
        "capture",
        "reenter",
        sessionId,
        "--allow-model-call",
        "--prompt-file",
        requestFile,
      ],
      { env },
    );
    const result = JSON.parse(resumed.stdout);
    assert.equal(result.source.origin, "codex_app_server_reentry");
    assert.equal(result.source.thread_id, "thread-branch-1");
    assert.equal(result.source.parent_thread_id, "thread-retained-1");
    assert.equal(result.source.parent_session_id, sessionId);
    assert.equal(result.routing.intent, "semantic_expansion");
    assert.equal(result.codex_turns, 1);
    assert.deepEqual(result.reentry_usage, {
      input_tokens: 80,
      cached_input_tokens: 60,
      output_tokens: 30,
      reasoning_output_tokens: 4,
    });
    assert.equal(result.protocol, "viewport-v1");
    assert.match(result.section.content, /deeper explanation/);
  } finally {
    await rm(directory, { recursive: true, force: true });
  }
});
