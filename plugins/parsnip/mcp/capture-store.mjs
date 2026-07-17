import { createHash, randomUUID } from "node:crypto";
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

export const CAPTURE_VERSION = 2;
export const DEFAULT_CAPTURE_TTL_MS = 6 * 60 * 60 * 1000;
export const MAX_CAPTURE_BYTES = 512 * 1024;
export const MAX_CAPTURE_SECTIONS = 24;
export const MAX_ROUTE_REQUEST_BYTES = 8 * 1024;
export const CAPTURE_ACTIONS = new Set([
  "next",
  "more",
  "less",
  "map",
  "full",
  "status",
  "reset",
  "close",
]);

function defaultDirectory() {
  return process.env.PARSNIP_CAPTURE_DIR || path.join(os.tmpdir(), "parsnip-capture-v1");
}

const ROUTE_STOP_WORDS = new Set([
  "a", "about", "again", "an", "and", "are", "can", "could", "do", "for",
  "give", "i", "in", "is", "it", "me", "of", "on", "please", "show", "tell",
  "that", "the", "there", "this", "to", "us", "was", "we", "were", "what",
  "when", "where", "which", "with", "would", "you",
]);

function normalizedRouteText(value) {
  return value
    .toLocaleLowerCase("en-US")
    .replace(/[’']/g, "")
    .replace(/[^\p{L}\p{N}]+/gu, " ")
    .trim()
    .replace(/\s+/g, " ");
}

function routeTokens(value) {
  return normalizedRouteText(value)
    .split(" ")
    .filter((token) => token.length >= 3 && !ROUTE_STOP_WORDS.has(token))
    .map((token) => token.length > 4 && token.endsWith("s") ? token.slice(0, -1) : token);
}

function routeResult(intent, operation, confidence, reason, extra = {}) {
  return { intent, operation, confidence, reason, ...extra };
}

export function classifyViewportRequest(record, request) {
  if (typeof request !== "string" || request.trim().length === 0) {
    throw new Error("route request must be non-empty.");
  }
  if (Buffer.byteLength(request, "utf8") > MAX_ROUTE_REQUEST_BYTES) {
    throw new Error(`route request must be ${MAX_ROUTE_REQUEST_BYTES} bytes or smaller.`);
  }
  if (record?.protocol !== "viewport-v1" || !Array.isArray(record.sections)) {
    return routeResult(
      "semantic_request",
      "model_required",
      1,
      "Only transparent viewports support intent-aware local routing.",
    );
  }

  const normalized = normalizedRouteText(request);
  if (/^(?:show |give |display )?(?:me )?(?:the )?(?:full|whole|complete|entire)(?: answer| response| plan| thing)?(?: please)?$/.test(normalized)
    || /^(?:show|display)(?: me)? everything(?: please)?$/.test(normalized)) {
    return routeResult("consolidate", "full", 0.99, "The request explicitly asks for the complete answer.");
  }
  if (/^(?:show |give |display )?(?:me )?(?:the )?(?:map|outline|overview|contents|table of contents)(?: please)?$/.test(normalized)) {
    return routeResult("orient", "map", 0.99, "The request asks for an overview of the buffered answer.");
  }
  if (/^(?:start over|restart|back to the start|from the beginning)$/.test(normalized)) {
    return routeResult("restart", "reset", 0.99, "The request asks to restart the reveal sequence.");
  }
  if (/^(?:less|shorter|collapse|back up|zoom out)$/.test(normalized)) {
    return routeResult("reduce", "less", 0.96, "The request asks to reduce the current view.");
  }

  const semanticExpansion = /\b(?:why|how come|rationale|reasoning|explain|elaborate|deeper|in depth|more detail|what if|tradeoffs?|compare|walk me through|explore that|give (?:me )?an? example)\b/.test(normalized);
  const execution = /^(?:lets|let us) (?:do|implement|apply|execute|try|build) (?:it|that)|^(?:do|implement|apply|execute|try|build) (?:it|that)$/.test(normalized);
  if (semanticExpansion || execution) {
    return routeResult(
      execution ? "execute" : "semantic_expansion",
      "model_required",
      0.98,
      execution
        ? "The request asks for action beyond revealing the buffered answer."
        : "The request asks for new semantic depth, which exact adjacent spans cannot guarantee.",
    );
  }

  const query = new Set(routeTokens(request));
  let best = null;
  for (let index = 0; index < record.sections.length; index += 1) {
    const section = record.sections[index];
    const titleTokens = new Set(routeTokens(section.title));
    const contentTokens = new Set(routeTokens(
      record.response.slice(section.start, section.brief_end),
    ));
    let titleMatches = 0;
    let contentMatches = 0;
    for (const token of query) {
      if (titleTokens.has(token)) titleMatches += 1;
      else if (contentTokens.has(token)) contentMatches += 1;
    }
    const score = titleMatches * 4 + contentMatches;
    if (score > 0 && (!best || score > best.score)) {
      best = { index, score, titleMatches, contentMatches };
    }
  }
  const retrievalLanguage = /^(?:show|remind|take|jump|go|return|back|what|where|when|which|who|how much)\b/.test(normalized)
    || /\b(?:section|part|budget|owner|deadline|action|risk|safety|test|example)\b/.test(normalized);
  if (best && (best.titleMatches > 0 || (retrievalLanguage && best.score >= 2))) {
    return routeResult(
      "retrieve",
      "jump",
      Math.min(0.99, 0.78 + best.score * 0.03),
      "The requested subject already exists as an exact buffered section.",
      { section_index: best.index },
    );
  }

  if (/^(?:ok|okay|sure|yes|yep|yeah|continue|next|go on|keep going|and then|then|more|more please|interesting|not bad|sounds good|hmm|hmm ok|whats next)$/.test(normalized)) {
    return routeResult("continue", "next", 0.96, "The utterance is a natural continuation signal.");
  }

  return routeResult(
    "semantic_request",
    "model_required",
    0.65,
    "The local router cannot prove that an exact buffered span satisfies the request.",
  );
}

function scanLines(text) {
  const lines = [];
  let start = 0;
  while (start < text.length) {
    const newline = text.indexOf("\n", start);
    const end = newline === -1 ? text.length : newline + 1;
    const contentEnd = newline === -1
      ? end
      : newline > start && text[newline - 1] === "\r"
        ? newline - 1
        : newline;
    lines.push({ start, end, text: text.slice(start, contentEnd) });
    start = end;
  }
  return lines;
}

function markdownHeadings(lines) {
  const headings = [];
  let fence = null;
  for (let index = 0; index < lines.length; index += 1) {
    const line = lines[index].text;
    const fenceMatch = line.match(/^ {0,3}(`{3,}|~{3,})/);
    if (fenceMatch) {
      const marker = fenceMatch[1];
      if (fence === null) {
        fence = { character: marker[0], length: marker.length };
      } else if (marker[0] === fence.character && marker.length >= fence.length) {
        fence = null;
      }
      continue;
    }
    if (fence !== null) continue;
    const match = line.match(/^ {0,3}(#{1,6})[ \t]+(.+?)[ \t]*#*[ \t]*$/);
    if (match) {
      headings.push({
        lineIndex: index,
        start: lines[index].start,
        level: match[1].length,
        title: match[2].trim(),
      });
    }
  }
  return headings;
}

function chooseSectionHeadings(headings) {
  return headings.filter(({ level }) => level === 2);
}

function firstContentEnd(lines, start, end) {
  const sectionLines = lines.filter((line) => line.start >= start && line.start < end);
  let index = 0;
  while (
    index < sectionLines.length &&
    (sectionLines[index].text.trim() === "" || /^ {0,3}#{1,6}[ \t]+/.test(sectionLines[index].text))
  ) {
    index += 1;
  }
  if (index >= sectionLines.length) return end;

  const first = sectionLines[index].text;
  const fenceMatch = first.match(/^ {0,3}(`{3,}|~{3,})/);
  if (fenceMatch) {
    const character = fenceMatch[1][0];
    const length = fenceMatch[1].length;
    for (let cursor = index + 1; cursor < sectionLines.length; cursor += 1) {
      const close = sectionLines[cursor].text.match(/^ {0,3}(`{3,}|~{3,})/);
      if (close && close[1][0] === character && close[1].length >= length) {
        return sectionLines[cursor].end;
      }
    }
    return end;
  }

  let cursor = index;
  while (cursor + 1 < sectionLines.length && sectionLines[cursor + 1].text.trim() !== "") {
    cursor += 1;
  }
  return sectionLines[cursor].end;
}

export function carveMarkdown(raw) {
  if (typeof raw !== "string" || raw.length === 0) {
    throw new Error("response must be a non-empty string.");
  }
  if (Buffer.byteLength(raw, "utf8") > MAX_CAPTURE_BYTES) {
    throw new Error(`response must be ${MAX_CAPTURE_BYTES} bytes or smaller.`);
  }

  const lines = scanLines(raw);
  const selected = chooseSectionHeadings(markdownHeadings(lines));
  if (selected.length === 0) {
    return [{ title: "Complete answer", start: 0, brief_end: raw.length, end: raw.length }];
  }

  const kept = selected.slice(0, MAX_CAPTURE_SECTIONS);
  return kept.map((heading, index) => {
    const start = index === 0 ? 0 : heading.start;
    const end = index + 1 < kept.length ? kept[index + 1].start : raw.length;
    return {
      title: heading.title.slice(0, 160),
      start,
      brief_end: firstContentEnd(lines, heading.start, end),
      end,
    };
  });
}

function indivisible(raw) {
  return [{ title: "Complete answer", start: 0, brief_end: raw.length, end: raw.length }];
}

function markerCompilation(raw) {
  const lines = scanLines(raw);
  const events = new Map();
  let fence = null;
  let markerLike = false;

  for (let index = 0; index < lines.length; index += 1) {
    const line = lines[index].text;
    const fenceMatch = line.match(/^ {0,3}(`{3,}|~{3,})/);
    if (fenceMatch) {
      const marker = fenceMatch[1];
      if (fence === null) {
        fence = { character: marker[0], length: marker.length };
      } else if (marker[0] === fence.character && marker.length >= fence.length) {
        fence = null;
      }
      continue;
    }
    if (fence !== null) continue;
    if (!line.includes("<!--p:")) continue;
    markerLike = true;
    const section = line.match(/^<!--p:s (.{1,80})-->$/);
    if (section) {
      const title = section[1].trim();
      if (!title || title.includes("--") || title.includes("<") || title.includes(">")) {
        return { markerLike, valid: false };
      }
      events.set(index, { type: "section", title });
    } else if (line === "<!--p:d-->") {
      events.set(index, { type: "detail" });
    } else {
      return { markerLike, valid: false };
    }
  }

  if (!markerLike) return { markerLike: false, valid: false };

  let response = "";
  const sections = [];
  let current = null;
  for (let index = 0; index < lines.length; index += 1) {
    const event = events.get(index);
    if (!event) {
      response += raw.slice(lines[index].start, lines[index].end);
      continue;
    }
    if (event.type === "section") {
      if (!event.title || sections.length >= MAX_CAPTURE_SECTIONS) {
        return { markerLike: true, valid: false };
      }
      if (current) current.end = response.length;
      current = {
        title: event.title,
        start: sections.length === 0 ? 0 : response.length,
        brief_end: null,
        end: null,
      };
      sections.push(current);
      continue;
    }
    if (!current || current.brief_end !== null) {
      return { markerLike: true, valid: false };
    }
    current.brief_end = response.length;
  }
  if (!current || sections.length === 0) return { markerLike: true, valid: false };
  current.end = response.length;
  for (const section of sections) {
    if (section.brief_end === null) section.brief_end = section.end;
    if (!response.slice(section.start, section.brief_end).trim()) {
      return { markerLike: true, valid: false };
    }
  }
  return { markerLike: true, valid: true, response, sections };
}

export function compileCapturedResponse(raw) {
  if (typeof raw !== "string" || raw.length === 0) {
    throw new Error("response must be a non-empty string.");
  }
  if (Buffer.byteLength(raw, "utf8") > MAX_CAPTURE_BYTES) {
    throw new Error(`response must be ${MAX_CAPTURE_BYTES} bytes or smaller.`);
  }
  const marker = markerCompilation(raw);
  let response = raw;
  let sections;
  let protocol;
  if (marker.valid) {
    response = marker.response;
    sections = marker.sections;
    protocol = "marker-v1";
  } else if (marker.markerLike) {
    sections = indivisible(raw);
    protocol = "indivisible";
  } else {
    sections = carveMarkdown(raw);
    protocol = sections.length > 1 || sections[0].title !== "Complete answer"
      ? "markdown-v1"
      : "indivisible";
  }
  return {
    raw_response: raw,
    response,
    sections,
    protocol,
    raw_response_sha256: createHash("sha256").update(raw, "utf8").digest("hex"),
    response_sha256: createHash("sha256").update(response, "utf8").digest("hex"),
  };
}

function viewportBlocks(raw) {
  const lines = scanLines(raw);
  const blocks = [];
  let start = null;
  let end = null;
  let fence = null;

  function finish() {
    if (start !== null && end !== null) blocks.push({ start, end });
    start = null;
    end = null;
  }

  for (const line of lines) {
    const fenceMatch = line.text.match(/^ {0,3}(`{3,}|~{3,})/);
    if (start === null && line.text.trim() !== "") start = line.start;
    if (fence !== null) {
      end = line.end;
      if (
        fenceMatch
        && fenceMatch[1][0] === fence.character
        && fenceMatch[1].length >= fence.length
      ) {
        fence = null;
      }
      continue;
    }
    if (fenceMatch) {
      fence = { character: fenceMatch[1][0], length: fenceMatch[1].length };
      end = line.end;
      continue;
    }
    if (line.text.trim() === "") {
      finish();
    } else {
      end = line.end;
    }
  }
  finish();
  return blocks;
}

function viewportTitle(raw, block, index) {
  const text = raw.slice(block.start, block.end).trim();
  const heading = text.match(/^ {0,3}#{1,6}[ \t]+(.+?)[ \t]*#*[ \t]*$/);
  if (heading) return heading[1].trim().slice(0, 80);
  const compact = text
    .replace(/[`*_>#\[\]]/g, "")
    .replace(/\s+/g, " ")
    .trim();
  return compact ? compact.slice(0, 80) : `Part ${index + 1}`;
}

function precedesStructuredBlock(raw, block, nextBlock) {
  const text = raw.slice(block.start, block.end).trim();
  if (/^ {0,3}(?:`{3,}|~{3,}|[-+*][ \t]+|\d+[.)][ \t]+|\|)/.test(text)) {
    return false;
  }
  const next = raw.slice(nextBlock.start, nextBlock.end).trimStart();
  return /^(?:`{3,}|~{3,}|[-+*][ \t]+|\d+[.)][ \t]+|\|)/.test(next);
}

export function compileViewportResponse(raw) {
  if (typeof raw !== "string" || raw.length === 0) {
    throw new Error("response must be a non-empty string.");
  }
  if (Buffer.byteLength(raw, "utf8") > MAX_CAPTURE_BYTES) {
    throw new Error(`response must be ${MAX_CAPTURE_BYTES} bytes or smaller.`);
  }
  const blocks = viewportBlocks(raw);
  if (blocks.length === 0) {
    return {
      raw_response: raw,
      response: raw,
      sections: indivisible(raw),
      protocol: "indivisible",
      raw_response_sha256: createHash("sha256").update(raw, "utf8").digest("hex"),
      response_sha256: createHash("sha256").update(raw, "utf8").digest("hex"),
    };
  }

  const units = [];
  for (let index = 0; index < blocks.length; index += 1) {
    const block = blocks[index];
    const text = raw.slice(block.start, block.end).trim();
    const headingOnly = /^ {0,3}#{1,6}[ \t]+(.+?)[ \t]*#*[ \t]*$/.test(text);
    if (
      index + 1 < blocks.length
      && (headingOnly || precedesStructuredBlock(raw, block, blocks[index + 1]))
    ) {
      units.push({
        start: block.start,
        end: blocks[index + 1].end,
        title: viewportTitle(raw, block, units.length),
      });
      index += 1;
    } else {
      units.push({
        start: block.start,
        end: block.end,
        title: viewportTitle(raw, block, units.length),
      });
    }
  }

  const kept = units.slice(0, MAX_CAPTURE_SECTIONS);
  const sections = kept.map((unit, index) => {
    const end = kept[index + 1] ? kept[index + 1].start : raw.length;
    return {
      title: unit.title,
      start: index === 0 ? 0 : unit.start,
      brief_end: end,
      end,
    };
  });
  return {
    raw_response: raw,
    response: raw,
    sections,
    protocol: "viewport-v1",
    raw_response_sha256: createHash("sha256").update(raw, "utf8").digest("hex"),
    response_sha256: createHash("sha256").update(raw, "utf8").digest("hex"),
  };
}

function captureMetadata(record) {
  return {
    protocol: record.protocol || "indivisible",
    response_sha256: record.response_sha256,
    raw_response_sha256: record.raw_response_sha256 || record.response_sha256,
  };
}

function renderSection(record, action, expanded) {
  const section = record.sections[record.cursor];
  return {
    session_id: record.session_id,
    action,
    status: "section",
    section: {
      title: section.title,
      content: record.response.slice(section.start, expanded ? section.end : section.brief_end),
      detail_available: section.brief_end < section.end,
      expanded,
      exact_span: {
        start: section.start,
        end: expanded ? section.end : section.brief_end,
      },
    },
    source: record.source,
    ...captureMetadata(record),
    progress: {
      index: record.cursor + 1,
      total: record.sections.length,
      remaining: record.sections.length - record.cursor - 1,
      consolidated: record.consolidated,
    },
  };
}

function renderMap(record) {
  return {
    session_id: record.session_id,
    action: "map",
    status: "map",
    ...captureMetadata(record),
    sections: record.sections.map((section, index) => ({
      title: section.title,
      status: index < record.cursor ? "seen" : index === record.cursor ? "current" : "parked",
      detail_available: section.brief_end < section.end,
    })),
    progress: {
      index: record.cursor + 1,
      total: record.sections.length,
      remaining: record.sections.length - record.cursor - 1,
      consolidated: record.consolidated,
    },
  };
}

function renderFull(record) {
  return {
    session_id: record.session_id,
    action: "full",
    status: "consolidated",
    content: record.response,
    exact_span: { start: 0, end: record.response.length },
    ...captureMetadata(record),
    source: record.source,
    progress: {
      index: record.sections.length,
      total: record.sections.length,
      remaining: 0,
      consolidated: true,
    },
  };
}

function renderViewportExpansion(record, start) {
  const section = record.sections[record.cursor];
  return {
    session_id: record.session_id,
    action: "more",
    status: "section",
    section: {
      title: section.title,
      content: record.response.slice(start, section.end),
      detail_available: false,
      expanded: true,
      exact_span: { start, end: section.end },
    },
    source: record.source,
    ...captureMetadata(record),
    progress: {
      index: record.cursor + 1,
      total: record.sections.length,
      remaining: record.sections.length - record.cursor - 1,
      consolidated: record.consolidated,
    },
  };
}

function renderModelRoute(record, request, routing) {
  const section = record.sections[record.cursor];
  const threadId = record.source?.thread_id;
  const resumable = typeof threadId === "string"
    && threadId.length > 0
    && record.source?.resumable === "true";
  return {
    session_id: record.session_id,
    action: "route",
    status: "model_required",
    routing,
    request,
    escalation: {
      resumable,
      ...(resumable ? { thread_id: threadId } : {}),
      current: {
        title: section.title,
        index: record.cursor,
        total: record.sections.length,
        content: record.response.slice(section.start, section.brief_end),
        exact_span: { start: section.start, end: section.brief_end },
      },
      response_sha256: record.response_sha256,
    },
    source: record.source,
    ...captureMetadata(record),
    progress: {
      index: record.cursor + 1,
      total: record.sections.length,
      remaining: record.sections.length - record.cursor - 1,
      consolidated: record.consolidated,
    },
  };
}

function attachRouting(result, request, routing) {
  return {
    ...result,
    action: "route",
    request,
    routing: { ...routing, local: true },
  };
}

export class CaptureStore {
  constructor({
    directory = defaultDirectory(),
    ttlMs = DEFAULT_CAPTURE_TTL_MS,
    clock = Date.now,
  } = {}) {
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
    await writeFile(temporary, `${JSON.stringify(record)}\n`, { encoding: "utf8", mode: 0o600 });
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
        throw new Error("Captured answer was not found or has expired.");
      }
      throw error;
    }
    if (record.expires_at <= this.clock()) {
      await unlink(filename).catch(() => {});
      throw new Error("Captured answer has expired.");
    }
    return record;
  }

  async create(response, source = {}, { mode = "capture" } = {}) {
    await this.initialize();
    if (!["capture", "viewport"].includes(mode)) {
      throw new Error(`Unsupported capture mode: ${mode}`);
    }
    const compiled = mode === "viewport"
      ? compileViewportResponse(response)
      : compileCapturedResponse(response);
    const now = this.clock();
    const cleanSource = Object.fromEntries(
      Object.entries(source)
        .filter(([key, value]) => /^[a-z_]+$/.test(key) && typeof value === "string")
        .map(([key, value]) => [key, value.slice(0, 500)]),
    );
    const record = {
      schema_version: CAPTURE_VERSION,
      session_id: randomUUID(),
      created_at: now,
      updated_at: now,
      expires_at: now + this.ttlMs,
      cursor: 0,
      expanded: [],
      consolidated: false,
      raw_response: compiled.raw_response,
      response: compiled.response,
      raw_response_sha256: compiled.raw_response_sha256,
      response_sha256: compiled.response_sha256,
      protocol: compiled.protocol,
      sections: compiled.sections,
      source: cleanSource,
    };
    await this.writeRecord(record);
    return renderSection(record, "capture", false);
  }

  async navigate(sessionId, action) {
    if (!CAPTURE_ACTIONS.has(action)) {
      throw new Error(`Unsupported capture action: ${action}`);
    }
    await this.initialize();
    if (action === "close") {
      await unlink(this.recordPath(sessionId)).catch((error) => {
        if (error?.code !== "ENOENT") throw error;
      });
      return { session_id: sessionId, action, status: "closed" };
    }

    const record = await this.readRecord(sessionId);
    const finalIndex = record.sections.length - 1;
    let result;
    let mutated = false;

    if (action === "next") {
      if (record.cursor < finalIndex) {
        record.cursor += 1;
        mutated = true;
      }
      result = renderSection(record, action, false);
    } else if (action === "more") {
      if (record.protocol === "viewport-v1" && record.cursor < finalIndex) {
        const start = record.sections[record.cursor].start;
        record.cursor += 1;
        mutated = true;
        result = renderViewportExpansion(record, start);
      } else {
        if (!record.expanded.includes(record.cursor)) {
          record.expanded.push(record.cursor);
          mutated = true;
        }
        result = renderSection(record, action, true);
      }
    } else if (action === "less") {
      const nextExpanded = record.expanded.filter((index) => index !== record.cursor);
      mutated = nextExpanded.length !== record.expanded.length;
      record.expanded = nextExpanded;
      result = renderSection(record, action, false);
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
      result = renderSection(record, action, false);
    } else {
      result = renderSection(record, action, record.expanded.includes(record.cursor));
    }

    if (mutated) {
      record.updated_at = this.clock();
      record.expires_at = record.updated_at + this.ttlMs;
      await this.writeRecord(record);
    }
    return result;
  }

  async route(sessionId, request) {
    await this.initialize();
    const record = await this.readRecord(sessionId);
    const routing = classifyViewportRequest(record, request);
    if (routing.operation === "model_required") {
      return renderModelRoute(record, request, { ...routing, local: false });
    }
    if (routing.operation === "jump") {
      record.cursor = routing.section_index;
      record.consolidated = false;
      record.updated_at = this.clock();
      record.expires_at = record.updated_at + this.ttlMs;
      await this.writeRecord(record);
      return attachRouting(renderSection(record, "route", false), request, routing);
    }
    return attachRouting(await this.navigate(sessionId, routing.operation), request, routing);
  }

  async cleanupExpired() {
    await mkdir(this.directory, { recursive: true, mode: 0o700 });
    const entries = await readdir(this.directory, { withFileTypes: true });
    const now = this.clock();
    await Promise.all(entries
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
      }));
  }
}
