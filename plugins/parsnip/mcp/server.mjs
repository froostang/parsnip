import readline from "node:readline";
import { readFile } from "node:fs/promises";
import { CapsuleStore } from "./capsule-store.mjs";

const SERVER_NAME = "Parsnip Local Buffer";
const SERVER_VERSION = JSON.parse(
  await readFile(new URL("../.codex-plugin/plugin.json", import.meta.url), "utf8"),
).version;
const CREATE_TOOL = "create_answer_capsule";
const CREATE_LEAN_TOOL = "create_lean_answer_capsule";
const NAVIGATE_TOOL = "navigate_answer_capsule";
const store = new CapsuleStore();

function send(message) {
  process.stdout.write(`${JSON.stringify(message)}\n`);
}

function sendResult(id, result) {
  send({ jsonrpc: "2.0", id, result });
}

function sendError(id, code, message) {
  send({ jsonrpc: "2.0", id, error: { code, message } });
}

function textFor(result) {
  if (result.status === "node") {
    const warnings = result.warnings.length
      ? `\n\nWarnings:\n${result.warnings.map((item) => `- ${item}`).join("\n")}`
      : "";
    return `${result.node.title}\n\n${result.node.content}${warnings}\n\nBuffered ${result.progress.index}/${result.progress.total}`;
  }
  if (result.status === "map") {
    return result.nodes
      .map((node) => `${node.status === "current" ? "→" : "-"} ${node.title} [${node.status}]`)
      .join("\n");
  }
  if (result.status === "consolidated") {
    const warnings = result.warnings.length
      ? `\n\nWarnings:\n${result.warnings.map((item) => `- ${item}`).join("\n")}`
      : "";
    return `${result.content}${warnings}`;
  }
  if (result.status === "closed") {
    return "The local answer capsule was deleted.";
  }
  return JSON.stringify(result);
}

function toolResult(result) {
  return {
    content: [{ type: "text", text: textFor(result) }],
    structuredContent: result,
  };
}

const nodeSchema = {
  type: "object",
  properties: {
    id: { type: "string", pattern: "^[a-z0-9][a-z0-9_-]*$", maxLength: 64 },
    title: { type: "string", minLength: 1, maxLength: 120 },
    kind: {
      type: "string",
      enum: ["orientation", "mechanism", "example", "action", "warning", "checkpoint"],
    },
    parent_id: { type: ["string", "null"], maxLength: 64 },
    brief: { type: "string", minLength: 1, maxLength: 1600 },
    detail: { type: "string", maxLength: 6000 },
    warnings: {
      type: "array",
      maxItems: 8,
      items: { type: "string", minLength: 1, maxLength: 1000 },
    },
    depends_on: {
      type: "array",
      maxItems: 8,
      items: { type: "string", minLength: 1, maxLength: 64 },
    },
  },
  required: ["id", "title", "kind", "parent_id", "brief", "detail", "warnings", "depends_on"],
  additionalProperties: false,
};

const capsuleSchema = {
  type: "object",
  properties: {
    version: { type: "integer", const: 1 },
    focus: { type: "string", minLength: 1, maxLength: 500 },
    thesis: { type: "string", minLength: 1, maxLength: 4000 },
    nodes: { type: "array", minItems: 1, maxItems: 24, items: nodeSchema },
    sequence: {
      type: "array",
      minItems: 1,
      maxItems: 24,
      items: { type: "string", minLength: 1, maxLength: 64 },
    },
    final_synthesis: { type: "string", minLength: 1, maxLength: 16000 },
    requery_triggers: {
      type: "array",
      maxItems: 12,
      items: { type: "string", minLength: 1, maxLength: 500 },
    },
  },
  required: [
    "version",
    "focus",
    "thesis",
    "nodes",
    "sequence",
    "final_synthesis",
    "requery_triggers",
  ],
  additionalProperties: false,
};

const leanNodeSchema = {
  type: "object",
  properties: {
    id: { type: "string", pattern: "^[a-z0-9][a-z0-9_-]*$", maxLength: 64 },
    title: { type: "string", minLength: 1, maxLength: 120 },
    kind: {
      type: "string",
      enum: ["orientation", "mechanism", "example", "action", "warning", "checkpoint"],
    },
    parent_id: { type: ["string", "null"], maxLength: 64 },
    brief: { type: "string", minLength: 1, maxLength: 1200 },
    extension: { type: "string", maxLength: 6000 },
    warnings: {
      type: "array",
      maxItems: 8,
      items: { type: "string", minLength: 1, maxLength: 1000 },
    },
    depends_on: {
      type: "array",
      maxItems: 8,
      items: { type: "string", minLength: 1, maxLength: 64 },
    },
  },
  required: [
    "id",
    "title",
    "kind",
    "parent_id",
    "brief",
    "extension",
    "warnings",
    "depends_on",
  ],
  additionalProperties: false,
};

const leanCapsuleSchema = {
  type: "object",
  properties: {
    version: { type: "integer", const: 2 },
    focus: { type: "string", minLength: 1, maxLength: 500 },
    thesis: { type: "string", minLength: 1, maxLength: 4000 },
    nodes: { type: "array", minItems: 1, maxItems: 24, items: leanNodeSchema },
    sequence: {
      type: "array",
      minItems: 1,
      maxItems: 24,
      items: { type: "string", minLength: 1, maxLength: 64 },
    },
    requery_triggers: {
      type: "array",
      maxItems: 12,
      items: { type: "string", minLength: 1, maxLength: 500 },
    },
  },
  required: ["version", "focus", "thesis", "nodes", "sequence", "requery_triggers"],
  additionalProperties: false,
};

function tools() {
  return [
    {
      name: CREATE_TOOL,
      title: "Create a Local Parsnip Answer Capsule",
      description:
        "Store one model-authored, user-visible answer graph locally and return its first brief node. Use only when the user explicitly asks for local buffering or the host supports direct local navigation. Never store private chain-of-thought.",
      inputSchema: {
        type: "object",
        properties: { capsule: capsuleSchema },
        required: ["capsule"],
        additionalProperties: false,
      },
      annotations: {
        readOnlyHint: false,
        destructiveHint: false,
        idempotentHint: false,
        openWorldHint: false,
      },
    },
    {
      name: CREATE_LEAN_TOOL,
      title: "Create a Lean Local Parsnip Answer Capsule",
      description:
        "Store one compact model-authored answer as ordered sections and return its first brief. Author each section once: brief is the initial reveal and extension adds detail. Full output is deterministic concatenation, so do not duplicate a final synthesis. Use only for explicit local buffering or a direct host navigation path. Never store private reasoning.",
      inputSchema: {
        type: "object",
        properties: { capsule: leanCapsuleSchema },
        required: ["capsule"],
        additionalProperties: false,
      },
      annotations: {
        readOnlyHint: false,
        destructiveHint: false,
        idempotentHint: false,
        openWorldHint: false,
      },
    },
    {
      name: NAVIGATE_TOOL,
      title: "Navigate a Local Parsnip Answer Capsule",
      description:
        "Reveal or inspect already-authored capsule content without rewriting it. A direct client can call this tool without another model generation; invoking it through a normal chat message still starts a model turn.",
      inputSchema: {
        type: "object",
        properties: {
          session_id: { type: "string", minLength: 36, maxLength: 36 },
          action: {
            type: "string",
            enum: ["next", "more", "less", "map", "full", "status", "reset", "close"],
          },
        },
        required: ["session_id", "action"],
        additionalProperties: false,
      },
      annotations: {
        readOnlyHint: false,
        destructiveHint: false,
        idempotentHint: false,
        openWorldHint: false,
      },
    },
  ];
}

async function handleToolCall(id, params) {
  try {
    if (params?.name === CREATE_TOOL) {
      sendResult(id, toolResult(await store.create(params.arguments?.capsule)));
      return;
    }
    if (params?.name === CREATE_LEAN_TOOL) {
      sendResult(id, toolResult(await store.create(params.arguments?.capsule)));
      return;
    }
    if (params?.name === NAVIGATE_TOOL) {
      sendResult(
        id,
        toolResult(
          await store.navigate(params.arguments?.session_id, params.arguments?.action),
        ),
      );
      return;
    }
    sendError(id, -32602, `Unknown tool: ${params?.name ?? ""}`);
  } catch (error) {
    sendError(id, -32602, error instanceof Error ? error.message : String(error));
  }
}

async function handleRequest(message) {
  const { id, method, params } = message;
  if (method === "initialize") {
    sendResult(id, {
      protocolVersion: params?.protocolVersion ?? "2025-11-25",
      capabilities: { tools: {} },
      serverInfo: { name: SERVER_NAME, version: SERVER_VERSION },
      instructions:
        "Use this server only when the user explicitly requests local answer buffering or a direct host navigation path is active. Store only model-visible answer content, never private reasoning. Keep warnings attached to their nodes. Normal chat messages still cause model turns; do not claim zero-call navigation unless the client invokes navigate_answer_capsule directly.",
    });
    return;
  }
  if (method === "ping") {
    sendResult(id, {});
    return;
  }
  if (method === "tools/list") {
    sendResult(id, { tools: tools() });
    return;
  }
  if (method === "tools/call") {
    await handleToolCall(id, params);
    return;
  }
  if (id !== undefined) {
    sendError(id, -32601, `Method not found: ${method}`);
  }
}

await store.initialize();
const lines = readline.createInterface({ input: process.stdin, crlfDelay: Infinity });
let requestQueue = Promise.resolve();
lines.on("line", (line) => {
  if (line.trim().length === 0) return;
  try {
    const message = JSON.parse(line);
    requestQueue = requestQueue
      .then(() => handleRequest(message))
      .catch((error) => {
        process.stderr.write(
          `Parsnip buffer request failed: ${error instanceof Error ? error.message : String(error)}\n`,
        );
      });
  } catch {
    // Ignore malformed transport lines; never write diagnostics to stdout.
  }
});
