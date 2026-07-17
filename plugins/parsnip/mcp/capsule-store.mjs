import { randomUUID } from "node:crypto";
import {
  chmod,
  mkdir,
  readFile,
  readdir,
  rename,
  unlink,
  writeFile,
} from "node:fs/promises";
import os from "node:os";
import path from "node:path";

export const CAPSULE_VERSION = 1;
export const LEAN_CAPSULE_VERSION = 2;
export const DEFAULT_TTL_MS = 6 * 60 * 60 * 1000;
export const MAX_CAPSULE_BYTES = 128 * 1024;
export const MAX_NODES = 24;
export const ACTIONS = new Set([
  "next",
  "more",
  "less",
  "map",
  "full",
  "status",
  "reset",
  "close",
]);

const NODE_KINDS = new Set([
  "orientation",
  "mechanism",
  "example",
  "action",
  "warning",
  "checkpoint",
]);
const ROOT_KEYS = new Set([
  "version",
  "focus",
  "thesis",
  "nodes",
  "sequence",
  "final_synthesis",
  "requery_triggers",
]);
const NODE_KEYS = new Set([
  "id",
  "title",
  "kind",
  "parent_id",
  "brief",
  "detail",
  "warnings",
  "depends_on",
]);
const LEAN_ROOT_KEYS = new Set([
  "version",
  "focus",
  "thesis",
  "nodes",
  "sequence",
  "requery_triggers",
]);
const LEAN_NODE_KEYS = new Set([
  "id",
  "title",
  "kind",
  "parent_id",
  "brief",
  "extension",
  "warnings",
  "depends_on",
]);

function isObject(value) {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function rejectUnknownKeys(value, allowed, label) {
  for (const key of Object.keys(value)) {
    if (!allowed.has(key)) {
      throw new Error(`${label} contains unsupported field: ${key}`);
    }
  }
}

function requireString(value, label, maxLength) {
  if (typeof value !== "string" || value.trim().length === 0) {
    throw new Error(`${label} must be a non-empty string.`);
  }
  const normalized = value.trim();
  if (normalized.length > maxLength) {
    throw new Error(`${label} must be ${maxLength} characters or fewer.`);
  }
  return normalized;
}

function optionalString(value, label, maxLength) {
  if (value === null || value === undefined || value === "") {
    return "";
  }
  return requireString(value, label, maxLength);
}

function stringList(value, label, maxItems, maxLength) {
  if (!Array.isArray(value) || value.length > maxItems) {
    throw new Error(`${label} must be an array with at most ${maxItems} items.`);
  }
  return value.map((item, index) =>
    requireString(item, `${label}[${index}]`, maxLength),
  );
}

function requireNodeId(value, label) {
  const id = requireString(value, label, 64);
  if (!/^[a-z0-9][a-z0-9_-]*$/.test(id)) {
    throw new Error(
      `${label} must use lowercase letters, digits, hyphens, or underscores.`,
    );
  }
  return id;
}

function normalizeNode(raw, index) {
  if (!isObject(raw)) {
    throw new Error(`nodes[${index}] must be an object.`);
  }
  rejectUnknownKeys(raw, NODE_KEYS, `nodes[${index}]`);
  const kind = requireString(raw.kind, `nodes[${index}].kind`, 32);
  if (!NODE_KINDS.has(kind)) {
    throw new Error(`nodes[${index}].kind is unsupported: ${kind}`);
  }
  const parentId =
    raw.parent_id === null || raw.parent_id === undefined
      ? null
      : requireNodeId(raw.parent_id, `nodes[${index}].parent_id`);
  return {
    id: requireNodeId(raw.id, `nodes[${index}].id`),
    title: requireString(raw.title, `nodes[${index}].title`, 120),
    kind,
    parent_id: parentId,
    brief: requireString(raw.brief, `nodes[${index}].brief`, 1600),
    detail: optionalString(raw.detail, `nodes[${index}].detail`, 6000),
    warnings: stringList(raw.warnings ?? [], `nodes[${index}].warnings`, 8, 1000),
    depends_on: stringList(
      raw.depends_on ?? [],
      `nodes[${index}].depends_on`,
      8,
      64,
    ).map((id) => requireNodeId(id, `nodes[${index}].depends_on`)),
  };
}

function normalizeLeanNode(raw, index) {
  if (!isObject(raw)) {
    throw new Error(`nodes[${index}] must be an object.`);
  }
  rejectUnknownKeys(raw, LEAN_NODE_KEYS, `nodes[${index}]`);
  const kind = requireString(raw.kind, `nodes[${index}].kind`, 32);
  if (!NODE_KINDS.has(kind)) {
    throw new Error(`nodes[${index}].kind is unsupported: ${kind}`);
  }
  const parentId =
    raw.parent_id === null || raw.parent_id === undefined
      ? null
      : requireNodeId(raw.parent_id, `nodes[${index}].parent_id`);
  return {
    id: requireNodeId(raw.id, `nodes[${index}].id`),
    title: requireString(raw.title, `nodes[${index}].title`, 120),
    kind,
    parent_id: parentId,
    brief: requireString(raw.brief, `nodes[${index}].brief`, 1200),
    extension: optionalString(raw.extension, `nodes[${index}].extension`, 6000),
    warnings: stringList(raw.warnings ?? [], `nodes[${index}].warnings`, 8, 1000),
    depends_on: stringList(
      raw.depends_on ?? [],
      `nodes[${index}].depends_on`,
      8,
      64,
    ).map((id) => requireNodeId(id, `nodes[${index}].depends_on`)),
  };
}

function validateGraph(nodes, rawSequence) {
  const ids = nodes.map(({ id }) => id);
  if (new Set(ids).size !== ids.length) {
    throw new Error("capsule.nodes must use unique ids.");
  }
  const knownIds = new Set(ids);
  const sequence = stringList(rawSequence, "capsule.sequence", MAX_NODES, 64).map(
    (id) => requireNodeId(id, "capsule.sequence"),
  );
  if (
    sequence.length !== ids.length ||
    new Set(sequence).size !== sequence.length ||
    sequence.some((id) => !knownIds.has(id))
  ) {
    throw new Error("capsule.sequence must contain every node id exactly once.");
  }

  const position = new Map(sequence.map((id, index) => [id, index]));
  for (const node of nodes) {
    if (node.parent_id !== null) {
      if (!knownIds.has(node.parent_id)) {
        throw new Error(`${node.id}.parent_id references an unknown node.`);
      }
      if (position.get(node.parent_id) >= position.get(node.id)) {
        throw new Error(`${node.id}.parent_id must appear earlier in capsule.sequence.`);
      }
    }
    for (const dependency of node.depends_on) {
      if (!knownIds.has(dependency)) {
        throw new Error(`${node.id}.depends_on references an unknown node.`);
      }
      if (position.get(dependency) >= position.get(node.id)) {
        throw new Error(`${node.id}.depends_on must reference an earlier node.`);
      }
    }
  }
  return sequence;
}

export function validateCapsule(raw) {
  if (!isObject(raw)) {
    throw new Error("capsule must be an object.");
  }
  if (![CAPSULE_VERSION, LEAN_CAPSULE_VERSION].includes(raw.version)) {
    throw new Error(
      `capsule.version must equal ${CAPSULE_VERSION} or ${LEAN_CAPSULE_VERSION}.`,
    );
  }
  const lean = raw.version === LEAN_CAPSULE_VERSION;
  rejectUnknownKeys(raw, lean ? LEAN_ROOT_KEYS : ROOT_KEYS, "capsule");
  if (!Array.isArray(raw.nodes) || raw.nodes.length < 1 || raw.nodes.length > MAX_NODES) {
    throw new Error(`capsule.nodes must contain between 1 and ${MAX_NODES} nodes.`);
  }

  const nodes = raw.nodes.map(lean ? normalizeLeanNode : normalizeNode);
  const sequence = validateGraph(nodes, raw.sequence);

  const capsule = {
    version: raw.version,
    focus: requireString(raw.focus, "capsule.focus", 500),
    thesis: requireString(raw.thesis, "capsule.thesis", 4000),
    nodes,
    sequence,
    requery_triggers: stringList(
      raw.requery_triggers ?? [],
      "capsule.requery_triggers",
      12,
      500,
    ),
  };
  if (!lean) {
    capsule.final_synthesis = requireString(
      raw.final_synthesis,
      "capsule.final_synthesis",
      16000,
    );
  }
  if (Buffer.byteLength(JSON.stringify(capsule), "utf8") > MAX_CAPSULE_BYTES) {
    throw new Error(`capsule must be ${MAX_CAPSULE_BYTES} bytes or smaller.`);
  }
  return capsule;
}

function defaultDirectory() {
  return process.env.PARSNIP_BUFFER_DIR || path.join(os.tmpdir(), "parsnip-buffer-v1");
}

function uniqueWarnings(capsule) {
  return [...new Set(capsule.nodes.flatMap(({ warnings }) => warnings))];
}

function orderedNodes(capsule) {
  const byId = new Map(capsule.nodes.map((node) => [node.id, node]));
  return capsule.sequence.map((id) => byId.get(id));
}

function renderNode(record, action, expanded = false) {
  const nodes = orderedNodes(record.capsule);
  const node = nodes[record.cursor];
  const extra = record.capsule.version === LEAN_CAPSULE_VERSION
    ? node.extension
    : node.detail;
  const useDetail = expanded && extra.length > 0;
  const expandedContent = record.capsule.version === LEAN_CAPSULE_VERSION
    ? `${node.brief}\n\n${extra}`
    : extra;
  return {
    session_id: record.session_id,
    action,
    status: "node",
    focus: record.capsule.focus,
    thesis: record.capsule.thesis,
    node: {
      id: node.id,
      title: node.title,
      kind: node.kind,
      content: useDetail ? expandedContent : node.brief,
      detail_available: extra.length > 0,
      expanded: useDetail,
    },
    warnings: node.warnings,
    progress: {
      index: record.cursor + 1,
      total: nodes.length,
      remaining: nodes.length - record.cursor - 1,
      consolidated: record.consolidated,
    },
  };
}

function renderMap(record) {
  const nodes = orderedNodes(record.capsule);
  return {
    session_id: record.session_id,
    action: "map",
    status: "map",
    focus: record.capsule.focus,
    thesis: record.capsule.thesis,
    nodes: nodes.map((node, index) => ({
      id: node.id,
      title: node.title,
      kind: node.kind,
      status: index < record.cursor ? "seen" : index === record.cursor ? "current" : "parked",
    })),
    progress: {
      index: record.cursor + 1,
      total: nodes.length,
      remaining: nodes.length - record.cursor - 1,
      consolidated: record.consolidated,
    },
  };
}

function renderFull(record) {
  const content = record.capsule.version === LEAN_CAPSULE_VERSION
    ? orderedNodes(record.capsule)
        .map((node) => {
          const body = node.extension.length > 0
            ? `${node.brief}\n\n${node.extension}`
            : node.brief;
          return `${node.title}\n\n${body}`;
        })
        .join("\n\n")
    : record.capsule.final_synthesis;
  return {
    session_id: record.session_id,
    action: "full",
    status: "consolidated",
    focus: record.capsule.focus,
    thesis: record.capsule.thesis,
    content,
    warnings: uniqueWarnings(record.capsule),
    requery_triggers: record.capsule.requery_triggers,
    progress: {
      index: record.capsule.sequence.length,
      total: record.capsule.sequence.length,
      remaining: 0,
      consolidated: true,
    },
  };
}

export class CapsuleStore {
  constructor({ directory = defaultDirectory(), ttlMs = DEFAULT_TTL_MS, clock = Date.now } = {}) {
    if (!Number.isFinite(ttlMs) || ttlMs <= 0) {
      throw new Error("ttlMs must be a positive number.");
    }
    this.directory = directory;
    this.ttlMs = ttlMs;
    this.clock = clock;
  }

  async initialize() {
    await mkdir(this.directory, { recursive: true, mode: 0o700 });
    await chmod(this.directory, 0o700);
    await this.cleanupExpired();
  }

  recordPath(sessionId) {
    if (!/^[0-9a-f-]{36}$/.test(sessionId)) {
      throw new Error("session_id is invalid.");
    }
    return path.join(this.directory, `${sessionId}.json`);
  }

  async writeRecord(record) {
    const destination = this.recordPath(record.session_id);
    const temporary = `${destination}.${randomUUID()}.tmp`;
    await writeFile(temporary, `${JSON.stringify(record)}\n`, {
      encoding: "utf8",
      mode: 0o600,
    });
    await rename(temporary, destination);
    await chmod(destination, 0o600);
  }

  async readRecord(sessionId) {
    const filename = this.recordPath(sessionId);
    let record;
    try {
      record = JSON.parse(await readFile(filename, "utf8"));
    } catch (error) {
      if (error?.code === "ENOENT") {
        throw new Error("Buffered answer capsule was not found or has expired.");
      }
      throw error;
    }
    if (record.expires_at <= this.clock()) {
      await unlink(filename).catch(() => {});
      throw new Error("Buffered answer capsule has expired.");
    }
    return record;
  }

  async create(rawCapsule) {
    await this.initialize();
    const capsule = validateCapsule(rawCapsule);
    const now = this.clock();
    const record = {
      schema_version: 1,
      session_id: randomUUID(),
      created_at: now,
      updated_at: now,
      expires_at: now + this.ttlMs,
      cursor: 0,
      expanded: [],
      consolidated: false,
      capsule,
    };
    await this.writeRecord(record);
    return renderNode(record, "create", false);
  }

  async navigate(sessionId, action) {
    if (!ACTIONS.has(action)) {
      throw new Error(`Unsupported navigation action: ${action}`);
    }
    await this.initialize();
    if (action === "close") {
      await unlink(this.recordPath(sessionId)).catch((error) => {
        if (error?.code !== "ENOENT") throw error;
      });
      return { session_id: sessionId, action, status: "closed" };
    }

    const record = await this.readRecord(sessionId);
    const finalIndex = record.capsule.sequence.length - 1;
    let result;
    let mutated = false;

    if (action === "next") {
      if (record.cursor < finalIndex) {
        record.cursor += 1;
        mutated = true;
        result = renderNode(record, action, false);
      } else {
        record.consolidated = true;
        mutated = true;
        result = renderFull(record);
      }
    } else if (action === "more") {
      const nodeId = record.capsule.sequence[record.cursor];
      if (!record.expanded.includes(nodeId)) {
        record.expanded.push(nodeId);
        mutated = true;
      }
      result = renderNode(record, action, true);
    } else if (action === "less") {
      const nodeId = record.capsule.sequence[record.cursor];
      const nextExpanded = record.expanded.filter((id) => id !== nodeId);
      mutated = nextExpanded.length !== record.expanded.length;
      record.expanded = nextExpanded;
      result = renderNode(record, action, false);
    } else if (action === "map") {
      result = renderMap(record);
    } else if (action === "full") {
      record.cursor = finalIndex;
      record.consolidated = true;
      mutated = true;
      result = renderFull(record);
    } else if (action === "reset") {
      record.cursor = 0;
      record.expanded = [];
      record.consolidated = false;
      mutated = true;
      result = renderNode(record, action, false);
    } else {
      const nodeId = record.capsule.sequence[record.cursor];
      result = renderNode(record, action, record.expanded.includes(nodeId));
    }

    if (mutated) {
      record.updated_at = this.clock();
      record.expires_at = record.updated_at + this.ttlMs;
      await this.writeRecord(record);
    }
    return result;
  }

  async cleanupExpired() {
    await mkdir(this.directory, { recursive: true, mode: 0o700 });
    const entries = await readdir(this.directory, { withFileTypes: true });
    const now = this.clock();
    await Promise.all(
      entries
        .filter((entry) => entry.isFile() && entry.name.endsWith(".json"))
        .map(async (entry) => {
          const filename = path.join(this.directory, entry.name);
          try {
            const record = JSON.parse(await readFile(filename, "utf8"));
            if (!Number.isFinite(record.expires_at) || record.expires_at <= now) {
              await unlink(filename);
            }
          } catch {
            await unlink(filename).catch(() => {});
          }
        }),
    );
  }
}
