#!/usr/bin/env python3
"""Compare one-shot, progressive, Parsnip, and locally buffered Codex usage."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shlex
import statistics
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Sequence


USAGE_FIELDS = (
    "input_tokens",
    "cached_input_tokens",
    "output_tokens",
    "reasoning_output_tokens",
)
RATE_FIELDS = (
    "input_per_million",
    "cached_input_per_million",
    "output_per_million",
)
REQUIRED_CASE_FIELDS = (
    "id",
    "category",
    "rubric",
    "baseline_prompt",
    "parsnip_prompt",
    "controls",
)
CONDITIONS = (
    "baseline",
    "viewport",
    "adaptive_viewport",
    "ordinary_followup",
    "ordinary",
    "parsnip",
    "buffered",
    "lean_buffered",
    "capture",
)
ORDINARY_PREFIX = (
    "Read and use the linked Parsnip skill for this controlled synthetic evaluation. "
    "Do not use other tools or read other repository files. Start at Level 1 and "
    "progressively "
)
CAPTURE_TARGET_OUTPUT_TOKENS = 450
CAPTURE_REASONING_EFFORT = "none"


@dataclass(frozen=True)
class ParsedRun:
    thread_id: str | None
    usage: dict[str, int]
    usage_events: int
    assistant_messages: tuple[str, ...]
    mcp_tool_calls: tuple[dict[str, Any], ...] = ()


def repository_root() -> Path:
    return Path(__file__).resolve().parents[1]


def is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def require_private_output(path: Path, repo_root: Path) -> Path:
    resolved = path.expanduser().resolve()
    if is_relative_to(resolved, repo_root.resolve()):
        raise ValueError(
            "Evaluation output must live outside the public repository; "
            f"received {resolved}"
        )
    return resolved


def load_cases(path: Path) -> list[dict[str, Any]]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, list) or not raw:
        raise ValueError("Cases file must contain a non-empty JSON array")

    cases: list[dict[str, Any]] = []
    seen: set[str] = set()
    for index, case in enumerate(raw):
        if not isinstance(case, dict):
            raise ValueError(f"Case {index} must be an object")
        missing = [field for field in REQUIRED_CASE_FIELDS if field not in case]
        if missing:
            raise ValueError(f"Case {index} is missing: {', '.join(missing)}")
        case_id = case["id"]
        if not isinstance(case_id, str) or not case_id:
            raise ValueError(f"Case {index} has an invalid id")
        if case_id in seen:
            raise ValueError(f"Duplicate case id: {case_id}")
        seen.add(case_id)
        if not isinstance(case["rubric"], list) or not all(
            isinstance(item, str) and item for item in case["rubric"]
        ):
            raise ValueError(f"Case {case_id} has an invalid rubric")
        if not isinstance(case["controls"], list) or not all(
            isinstance(item, str) and item for item in case["controls"]
        ):
            raise ValueError(f"Case {case_id} has invalid controls")
        for field in ("category", "baseline_prompt", "parsnip_prompt"):
            if not isinstance(case[field], str) or not case[field].strip():
                raise ValueError(f"Case {case_id} has an invalid {field}")
        cases.append(case)
    return cases


def parse_jsonl(text: str) -> ParsedRun:
    usage = {field: 0 for field in USAGE_FIELDS}
    usage_events = 0
    thread_id: str | None = None
    messages: list[str] = []
    mcp_tool_calls: list[dict[str, Any]] = []

    for line_number, raw_line in enumerate(text.splitlines(), start=1):
        line = raw_line.strip()
        if not line:
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid JSONL at line {line_number}: {exc}") from exc
        if not isinstance(event, dict):
            raise ValueError(f"JSONL line {line_number} is not an object")

        event_type = event.get("type")
        if event_type == "thread.started":
            candidate = event.get("thread_id")
            if not candidate and isinstance(event.get("thread"), dict):
                candidate = event["thread"].get("id")
            if isinstance(candidate, str) and candidate:
                thread_id = candidate
        elif event_type == "item.completed":
            item = event.get("item")
            if isinstance(item, dict) and item.get("type") == "agent_message":
                message = item.get("text")
                if isinstance(message, str) and message:
                    messages.append(message)
            elif isinstance(item, dict) and item.get("type") == "mcp_tool_call":
                mcp_tool_calls.append(item)
        elif event_type == "turn.completed":
            event_usage = event.get("usage")
            if isinstance(event_usage, dict):
                usage_events += 1
                for field in USAGE_FIELDS:
                    value = event_usage.get(field, 0)
                    if not isinstance(value, int) or value < 0:
                        raise ValueError(
                            f"turn.completed {field} must be a non-negative integer"
                        )
                    usage[field] += value

    return ParsedRun(
        thread_id, usage, usage_events, tuple(messages), tuple(mcp_tool_calls)
    )


def combine_runs(runs: Iterable[ParsedRun]) -> ParsedRun:
    usage = {field: 0 for field in USAGE_FIELDS}
    usage_events = 0
    thread_id: str | None = None
    messages: list[str] = []
    mcp_tool_calls: list[dict[str, Any]] = []
    for run in runs:
        if thread_id and run.thread_id and run.thread_id != thread_id:
            raise ValueError(
                f"Cannot combine different threads: {thread_id} and {run.thread_id}"
            )
        thread_id = run.thread_id or thread_id
        usage_events += run.usage_events
        messages.extend(run.assistant_messages)
        mcp_tool_calls.extend(run.mcp_tool_calls)
        for field in USAGE_FIELDS:
            usage[field] += run.usage[field]
    return ParsedRun(
        thread_id, usage, usage_events, tuple(messages), tuple(mcp_tool_calls)
    )


def ordinary_progressive_prompt(parsnip_prompt: str) -> str:
    if not parsnip_prompt.startswith(ORDINARY_PREFIX):
        raise ValueError("Parsnip prompt does not use the expected controlled prefix")
    task = parsnip_prompt[len(ORDINARY_PREFIX) :]
    return (
        "Controlled synthetic evaluation. Do not use tools, skills, or repository files. "
        "Start with the smallest independently useful part, then wait for my controls. "
        "I will send exactly two content controls; after the second, consolidate every "
        "remaining requirement compactly. Progressively "
        f"{task}"
    )


def buffered_prompt(parsnip_prompt: str) -> str:
    return (
        f"{parsnip_prompt}\n\n"
        "Explicitly use local answer buffering for this evaluation. Read the linked "
        "capsules reference, author the complete stable answer once, and call "
        "create_answer_capsule exactly once. Put every requested outcome in "
        "final_synthesis, split it into useful progressive nodes, and include material "
        "premise changes in requery_triggers. Do not navigate the capsule through chat. "
        "After creating it, return only the first buffered node and its warnings."
    )


def lean_buffered_prompt(parsnip_prompt: str) -> str:
    if not parsnip_prompt.startswith(ORDINARY_PREFIX):
        raise ValueError("Parsnip prompt does not use the expected controlled prefix")
    task = parsnip_prompt[len(ORDINARY_PREFIX) :]
    return (
        "Controlled synthetic evaluation with an explicit local-buffer request. "
        "Do not read skills, references, or repository files. Use only "
        "create_lean_answer_capsule, exactly once. Author the complete stable answer "
        "as three to eight ordered version-2 nodes. Each brief must stand alone; each "
        "extension must continue its brief without repeating it. Cover every requested "
        "outcome across the ordered nodes, attach material warnings, and list premise "
        "changes in requery_triggers. Do not author a duplicate final synthesis and do "
        "not navigate through chat. After the tool call, return only its first node. "
        f"Task: {task}"
    )


def load_rates(path: Path | None) -> dict[str, float] | None:
    if path is None:
        return None
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("Rates file must contain a JSON object")
    rates: dict[str, float] = {}
    for field in RATE_FIELDS:
        value = raw.get(field)
        if not isinstance(value, (int, float)) or value < 0:
            raise ValueError(f"Rates file requires a non-negative {field}")
        rates[field] = float(value)
    return rates


def estimated_cost_usd(usage: dict[str, int], rates: dict[str, float]) -> float:
    cached = usage["cached_input_tokens"]
    total_input = usage["input_tokens"]
    if cached > total_input:
        raise ValueError("cached_input_tokens cannot exceed input_tokens")
    uncached = total_input - cached
    cost = (
        uncached * rates["input_per_million"]
        + cached * rates["cached_input_per_million"]
        + usage["output_tokens"] * rates["output_per_million"]
    ) / 1_000_000
    return cost


def reported_token_total(usage: dict[str, int]) -> int:
    # Keep reasoning output diagnostic-only here. The event does not state that it
    # is additive, so adding it could double-count provider-reported output.
    return usage["input_tokens"] + usage["output_tokens"]


def safe_ratio(numerator: float, denominator: float) -> float | None:
    if denominator == 0:
        return None
    return numerator / denominator


def build_start_command(
    codex: str,
    repo_root: Path,
    prompt: str,
    model: str | None,
    *,
    ephemeral: bool,
) -> list[str]:
    command = [
        codex,
        "exec",
        "--json",
        "--color",
        "never",
        "--sandbox",
        "read-only",
        "-C",
        str(repo_root),
    ]
    if model:
        command.extend(("--model", model))
    if ephemeral:
        command.append("--ephemeral")
    command.append(prompt)
    return command


def attach_parsnip_locator(prompt: str, repo_root: Path) -> str:
    skill_path = repo_root / "plugins" / "parsnip" / "skills" / "parsnip" / "SKILL.md"
    locator = f"[$parsnip:parsnip]({skill_path})"
    return f"{locator}\n{prompt}"


def build_resume_command(
    codex: str,
    thread_id: str,
    prompt: str,
    model: str | None,
) -> list[str]:
    command = [codex, "exec", "resume", "--json"]
    if model:
        command.extend(("--model", model))
    command.extend((thread_id, prompt))
    return command


def normalize_buffer_action(control: str) -> str:
    normalized = " ".join(control.lower().split())
    aliases = {
        "continue": "next",
        "go deeper": "more",
        "show everything": "full",
        "full answer": "full",
        "finish compactly": "full",
    }
    action = aliases.get(normalized, normalized)
    if action not in {"next", "more", "less", "map", "full"}:
        raise ValueError(f"Control has no local buffer equivalent: {control}")
    return action


def build_buffer_cli_command(
    repo_root: Path, session_id: str, action: str
) -> list[str]:
    launcher = repo_root / "plugins" / "parsnip" / "mcp" / "launch.sh"
    return [
        "/bin/sh",
        str(launcher),
        "cli",
        "navigate",
        session_id,
        action,
    ]


def build_capture_run_command(
    repo_root: Path,
    prompt_file: Path,
    model: str | None,
    timeout_seconds: int,
) -> list[str]:
    launcher = repo_root / "plugins" / "parsnip" / "mcp" / "launch.sh"
    command = [
        "/bin/sh",
        str(launcher),
        "capture",
        "run",
        "--allow-model-call",
        "--prompt-file",
        str(prompt_file),
        "--cwd",
        str(repo_root),
        "--timeout-ms",
        str(timeout_seconds * 1000),
        "--target-output-tokens",
        str(CAPTURE_TARGET_OUTPUT_TOKENS),
        "--effort",
        CAPTURE_REASONING_EFFORT,
    ]
    if model:
        command.extend(("--model", model))
    return command


def build_viewport_file_command(
    repo_root: Path,
    response_file: Path,
    thread_id: str | None = None,
    *,
    resumable: bool = False,
) -> list[str]:
    launcher = repo_root / "plugins" / "parsnip" / "mcp" / "launch.sh"
    command = [
        "/bin/sh",
        str(launcher),
        "capture",
        "viewport-file",
        str(response_file),
    ]
    if thread_id:
        command.extend(("--thread-id", thread_id))
        command.extend(("--resumable", "true" if resumable else "false"))
    return command


def build_capture_navigation_command(
    repo_root: Path, session_id: str, action: str
) -> list[str]:
    launcher = repo_root / "plugins" / "parsnip" / "mcp" / "launch.sh"
    return [
        "/bin/sh",
        str(launcher),
        "capture",
        "navigate",
        session_id,
        action,
    ]


def build_capture_route_command(
    repo_root: Path, session_id: str, request: str
) -> list[str]:
    launcher = repo_root / "plugins" / "parsnip" / "mcp" / "launch.sh"
    return [
        "/bin/sh",
        str(launcher),
        "capture",
        "route",
        session_id,
        request,
    ]


def build_capture_reentry_command(
    repo_root: Path,
    session_id: str,
    request_file: Path,
    model: str | None,
    timeout_seconds: int,
    *,
    ordinary_followup: bool = False,
) -> list[str]:
    launcher = repo_root / "plugins" / "parsnip" / "mcp" / "launch.sh"
    command = [
        "/bin/sh",
        str(launcher),
        "capture",
        "reenter",
        session_id,
        "--allow-model-call",
        "--prompt-file",
        str(request_file),
        "--cwd",
        str(repo_root),
        "--timeout-ms",
        str(timeout_seconds * 1000),
    ]
    if ordinary_followup:
        command.append("--ordinary-followup")
    if model:
        command.extend(("--model", model))
    return command


def _find_session_id(value: Any) -> str | None:
    if isinstance(value, dict):
        candidate = value.get("session_id")
        if isinstance(candidate, str) and candidate:
            return candidate
        for nested in value.values():
            found = _find_session_id(nested)
            if found:
                return found
    elif isinstance(value, list):
        for nested in value:
            found = _find_session_id(nested)
            if found:
                return found
    return None


def capsule_session_id(
    run: ParsedRun, tool_name: str = "create_answer_capsule"
) -> str:
    for item in run.mcp_tool_calls:
        called_tool = item.get("tool") or item.get("name")
        if called_tool != tool_name:
            continue
        result = item.get("result")
        found = _find_session_id(result)
        if found:
            return found
    raise RuntimeError(
        f"Buffered condition did not return a {tool_name} session id"
    )


def run_local_json_command(
    command: Sequence[str],
    cwd: Path,
    stdout_path: Path,
    stderr_path: Path,
    timeout_seconds: int,
) -> dict[str, Any]:
    completed = subprocess.run(
        command,
        cwd=cwd,
        text=True,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        timeout=timeout_seconds,
        check=False,
    )
    stdout_path.write_text(completed.stdout, encoding="utf-8")
    stderr_path.write_text(completed.stderr, encoding="utf-8")
    if completed.returncode != 0:
        raise RuntimeError(
            f"Local buffer exited with {completed.returncode}; see {stderr_path}"
        )
    try:
        result = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Invalid local buffer JSON in {stdout_path}: {exc}") from exc
    if not isinstance(result, dict):
        raise RuntimeError(f"Local buffer result is not an object in {stdout_path}")
    return result


def render_buffer_result(result: dict[str, Any]) -> str:
    status = result.get("status")
    if status == "section" and isinstance(result.get("section"), dict):
        return str(result["section"].get("content", ""))
    if status == "node" and isinstance(result.get("node"), dict):
        node = result["node"]
        text = f"{node.get('title', '')}\n\n{node.get('content', '')}".strip()
        warnings = result.get("warnings")
        if isinstance(warnings, list) and warnings:
            text += "\n\nWarnings:\n" + "\n".join(
                f"- {warning}" for warning in warnings
            )
        return text
    if status == "map" and isinstance(result.get("nodes"), list):
        return "\n".join(
            f"{'→' if node.get('status') == 'current' else '-'} "
            f"{node.get('title', '')} [{node.get('status', '')}]"
            for node in result["nodes"]
            if isinstance(node, dict)
        )
    if status == "map" and isinstance(result.get("sections"), list):
        return "\n".join(
            f"{'→' if section.get('status') == 'current' else '-'} "
            f"{section.get('title', '')} [{section.get('status', '')}]"
            for section in result["sections"]
            if isinstance(section, dict)
        )
    if status == "consolidated":
        text = str(result.get("content", ""))
        warnings = result.get("warnings")
        if isinstance(warnings, list) and warnings:
            text += "\n\nWarnings:\n" + "\n".join(
                f"- {warning}" for warning in warnings
            )
        return text
    if status == "model_required":
        routing = result.get("routing")
        escalation = result.get("escalation")
        intent = routing.get("intent") if isinstance(routing, dict) else "semantic request"
        current = escalation.get("current") if isinstance(escalation, dict) else None
        title = current.get("title") if isinstance(current, dict) else "current section"
        return f"[Model escalation required: {intent} from {title}]"
    return json.dumps(result, sort_keys=True)


def parsed_capture_start(result: dict[str, Any]) -> ParsedRun:
    usage = result.get("capture_usage")
    if not isinstance(usage, dict):
        raise RuntimeError("Capture condition did not report app-server token usage")
    normalized: dict[str, int] = {}
    for field in USAGE_FIELDS:
        value = usage.get(field)
        if not isinstance(value, int) or value < 0:
            raise RuntimeError(f"Capture condition reported invalid {field}")
        normalized[field] = value
    source = result.get("source")
    thread_id = source.get("thread_id") if isinstance(source, dict) else None
    if not isinstance(thread_id, str) or not thread_id:
        raise RuntimeError("Capture condition did not report an app-server thread id")
    return ParsedRun(
        thread_id,
        normalized,
        1,
        (render_buffer_result(result),),
    )


def complete_capture_locally(
    start_result: dict[str, Any],
    *,
    controls: Sequence[str],
    repo_root: Path,
    run_dir: Path,
    timeout_seconds: int,
    expected_protocol: str = "marker-v1",
    artifact_prefix: str = "capture",
    route_controls: bool = False,
) -> tuple[ParsedRun, list[str], int, bool, bool]:
    session_id = start_result.get("session_id")
    expected_hash = start_result.get("response_sha256")
    expected_raw_hash = start_result.get("raw_response_sha256")
    captured_raw_hash = start_result.get("capture_raw_sha256")
    if not isinstance(session_id, str) or not session_id:
        raise RuntimeError("Capture condition did not return a session id")
    if not isinstance(expected_hash, str) or len(expected_hash) != 64:
        raise RuntimeError("Capture condition did not return a canonical-response hash")
    if not isinstance(expected_raw_hash, str) or len(expected_raw_hash) != 64:
        raise RuntimeError("Capture condition did not return a raw-response hash")
    if not isinstance(captured_raw_hash, str) or len(captured_raw_hash) != 64:
        raise RuntimeError("Capture condition did not return a capture-client raw hash")

    start = parsed_capture_start(start_result)
    results: list[dict[str, Any]] = []
    actions: list[str] = []
    cleanup_calls = 0
    try:
        for index, control in enumerate(controls, start=1):
            command = (
                build_capture_route_command(repo_root, session_id, control)
                if route_controls
                else build_capture_navigation_command(
                    repo_root, session_id, normalize_buffer_action(control)
                )
            )
            result = run_local_json_command(
                    command,
                    repo_root,
                    run_dir / f"{artifact_prefix}-local-{index:02d}.json",
                    run_dir / f"{artifact_prefix}-local-{index:02d}.stderr.log",
                    timeout_seconds,
            )
            results.append(result)
            routing = result.get("routing") if route_controls else None
            operation = routing.get("operation") if isinstance(routing, dict) else None
            actions.append(
                str(operation) if operation else normalize_buffer_action(control)
            )
        last = results[-1] if results else {}
        if last.get("status") != "consolidated":
            actions.append("full")
            index = len(results) + 1
            results.append(
                run_local_json_command(
                    build_capture_navigation_command(repo_root, session_id, "full"),
                    repo_root,
                    run_dir / f"{artifact_prefix}-local-{index:02d}.json",
                    run_dir / f"{artifact_prefix}-local-{index:02d}.stderr.log",
                    timeout_seconds,
                )
            )
    finally:
        cleanup = subprocess.run(
            build_capture_navigation_command(repo_root, session_id, "close"),
            cwd=repo_root,
            text=True,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            timeout=timeout_seconds,
            check=False,
        )
        (run_dir / f"{artifact_prefix}-local-close.json").write_text(
            cleanup.stdout, encoding="utf-8"
        )
        (run_dir / f"{artifact_prefix}-local-close.stderr.log").write_text(
            cleanup.stderr, encoding="utf-8"
        )
        if cleanup.returncode == 0:
            cleanup_calls = 1

    full = results[-1] if results else {}
    content = full.get("content")
    exact_full_verified = (
        full.get("status") == "consolidated"
        and isinstance(content, str)
        and full.get("response_sha256") == expected_hash
        and hashlib.sha256(content.encode("utf-8")).hexdigest() == expected_hash
    )
    protocol_verified = (
        start_result.get("protocol") == expected_protocol
        and expected_raw_hash == captured_raw_hash
        and full.get("protocol") == expected_protocol
        and full.get("raw_response_sha256") == expected_raw_hash
    )
    completed = ParsedRun(
        start.thread_id,
        start.usage,
        start.usage_events,
        start.assistant_messages
        + tuple(render_buffer_result(result) for result in results),
    )
    return (
        completed,
        actions,
        cleanup_calls,
        exact_full_verified,
        protocol_verified,
    )


def complete_adaptive_viewport(
    start_result: dict[str, Any],
    *,
    controls: Sequence[str],
    model: str | None,
    repo_root: Path,
    run_dir: Path,
    timeout_seconds: int,
    artifact_prefix: str = "adaptive",
    ordinary_followup: bool = False,
) -> tuple[ParsedRun, list[str], int, bool, bool, bool, bool, int, dict[str, int]]:
    initial_session_id = start_result.get("session_id")
    initial_hash = start_result.get("response_sha256")
    if not isinstance(initial_session_id, str) or not initial_session_id:
        raise RuntimeError("Adaptive viewport did not return an initial session id")
    if not isinstance(initial_hash, str) or len(initial_hash) != 64:
        raise RuntimeError("Adaptive viewport did not return an initial response hash")

    start = parsed_capture_start(start_result)
    current_session_id = initial_session_id
    current_thread_id = start.thread_id
    current_hash = initial_hash
    session_ids = [initial_session_id]
    results: list[dict[str, Any]] = []
    actions: list[str] = []
    reentry_runs: list[ParsedRun] = []
    reentry_usage = {field: 0 for field in USAGE_FIELDS}
    protocol_verified = start_result.get("protocol") == "viewport-v1"
    lineage_verified = True
    cleanup_calls = 0
    initial_full: dict[str, Any] | None = None
    try:
        for index, control in enumerate(controls, start=1):
            request_file = run_dir / f"{artifact_prefix}-request-{index:02d}.md"
            request_file.write_text(control, encoding="utf-8")
            result = run_local_json_command(
                build_capture_reentry_command(
                    repo_root,
                    current_session_id,
                    request_file,
                    model,
                    timeout_seconds,
                    ordinary_followup=ordinary_followup,
                ),
                repo_root,
                run_dir / f"{artifact_prefix}-local-{index:02d}.json",
                run_dir / f"{artifact_prefix}-local-{index:02d}.stderr.log",
                timeout_seconds + 5,
            )
            results.append(result)
            protocol_verified = protocol_verified and result.get("protocol") == "viewport-v1"
            if result.get("codex_turns") == 1:
                usage = result.get("reentry_usage")
                source = result.get("source")
                thread_id = source.get("thread_id") if isinstance(source, dict) else None
                parent_thread_id = (
                    source.get("parent_thread_id") if isinstance(source, dict) else None
                )
                lineage_verified = lineage_verified and (
                    isinstance(thread_id, str)
                    and bool(thread_id)
                    and parent_thread_id == current_thread_id
                    and thread_id != current_thread_id
                )
                if not lineage_verified or not isinstance(usage, dict):
                    raise RuntimeError("Adaptive re-entry did not preserve its thread lineage")
                normalized_usage: dict[str, int] = {}
                for field in USAGE_FIELDS:
                    value = usage.get(field)
                    if not isinstance(value, int) or value < 0:
                        raise RuntimeError(f"Adaptive re-entry reported invalid {field}")
                    normalized_usage[field] = value
                    reentry_usage[field] += value
                reentry_runs.append(ParsedRun(thread_id, normalized_usage, 1, ()))
                current_thread_id = thread_id
                next_session_id = result.get("session_id")
                next_hash = result.get("response_sha256")
                if not isinstance(next_session_id, str) or not isinstance(next_hash, str):
                    raise RuntimeError("Adaptive re-entry did not return a fresh viewport")
                current_session_id = next_session_id
                current_hash = next_hash
                session_ids.append(next_session_id)
                actions.append(
                    "ordinary_followup" if ordinary_followup else "model_reentry"
                )
            else:
                routing = result.get("routing")
                operation = routing.get("operation") if isinstance(routing, dict) else None
                if not isinstance(operation, str):
                    raise RuntimeError("Adaptive local route did not report its operation")
                actions.append(operation)

        final_index = len(results) + 1
        final = run_local_json_command(
            build_capture_navigation_command(repo_root, current_session_id, "full"),
            repo_root,
            run_dir / f"{artifact_prefix}-local-{final_index:02d}.json",
            run_dir / f"{artifact_prefix}-local-{final_index:02d}.stderr.log",
            timeout_seconds,
        )
        results.append(final)
        actions.append("full")
        protocol_verified = protocol_verified and final.get("protocol") == "viewport-v1"
        if current_session_id == initial_session_id:
            initial_full = final
        else:
            initial_full = run_local_json_command(
                build_capture_navigation_command(repo_root, initial_session_id, "full"),
                repo_root,
                run_dir / f"{artifact_prefix}-initial-full.json",
                run_dir / f"{artifact_prefix}-initial-full.stderr.log",
                timeout_seconds,
            )
    finally:
        for index, session_id in enumerate(dict.fromkeys(session_ids), start=1):
            cleanup = subprocess.run(
                build_capture_navigation_command(repo_root, session_id, "close"),
                cwd=repo_root,
                text=True,
                stdin=subprocess.DEVNULL,
                capture_output=True,
                timeout=timeout_seconds,
                check=False,
            )
            (run_dir / f"{artifact_prefix}-close-{index:02d}.json").write_text(
                cleanup.stdout, encoding="utf-8"
            )
            (run_dir / f"{artifact_prefix}-close-{index:02d}.stderr.log").write_text(
                cleanup.stderr, encoding="utf-8"
            )
            if cleanup.returncode == 0:
                cleanup_calls += 1

    final = results[-1]
    final_content = final.get("content")
    exact_full_verified = (
        final.get("status") == "consolidated"
        and isinstance(final_content, str)
        and final.get("response_sha256") == current_hash
        and hashlib.sha256(final_content.encode("utf-8")).hexdigest() == current_hash
    )
    initial_content = initial_full.get("content") if isinstance(initial_full, dict) else None
    initial_exact_full_verified = (
        isinstance(initial_full, dict)
        and initial_full.get("status") == "consolidated"
        and isinstance(initial_content, str)
        and initial_full.get("response_sha256") == initial_hash
        and hashlib.sha256(initial_content.encode("utf-8")).hexdigest() == initial_hash
    )
    combined_usage = dict(start.usage)
    for run in reentry_runs:
        for field in USAGE_FIELDS:
            combined_usage[field] += run.usage[field]
    completed = ParsedRun(
        start.thread_id,
        combined_usage,
        start.usage_events + len(reentry_runs),
        start.assistant_messages
        + tuple(render_buffer_result(result) for result in results),
    )
    return (
        completed,
        actions,
        cleanup_calls,
        initial_exact_full_verified,
        exact_full_verified,
        protocol_verified,
        lineage_verified,
        len(reentry_runs),
        reentry_usage,
    )


def complete_buffer_locally(
    start: ParsedRun,
    *,
    create_tool: str,
    controls: Sequence[str],
    artifact_prefix: str,
    repo_root: Path,
    run_dir: Path,
    timeout_seconds: int,
) -> tuple[ParsedRun, list[str], int]:
    session_id = capsule_session_id(start, create_tool)
    results: list[dict[str, Any]] = []
    actions = [normalize_buffer_action(control) for control in controls]
    cleanup_calls = 0
    try:
        for index, action in enumerate(actions, start=1):
            results.append(
                run_local_json_command(
                    build_buffer_cli_command(repo_root, session_id, action),
                    repo_root,
                    run_dir / f"{artifact_prefix}-local-{index:02d}.json",
                    run_dir / f"{artifact_prefix}-local-{index:02d}.stderr.log",
                    timeout_seconds,
                )
            )
        last = results[-1] if results else {}
        progress = last.get("progress") if isinstance(last.get("progress"), dict) else {}
        if last.get("status") != "consolidated" and not progress.get("consolidated"):
            actions.append("full")
            index = len(results) + 1
            results.append(
                run_local_json_command(
                    build_buffer_cli_command(repo_root, session_id, "full"),
                    repo_root,
                    run_dir / f"{artifact_prefix}-local-{index:02d}.json",
                    run_dir / f"{artifact_prefix}-local-{index:02d}.stderr.log",
                    timeout_seconds,
                )
            )
    finally:
        cleanup = subprocess.run(
            build_buffer_cli_command(repo_root, session_id, "close"),
            cwd=repo_root,
            text=True,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            timeout=timeout_seconds,
            check=False,
        )
        (run_dir / f"{artifact_prefix}-local-close.json").write_text(
            cleanup.stdout, encoding="utf-8"
        )
        (run_dir / f"{artifact_prefix}-local-close.stderr.log").write_text(
            cleanup.stderr, encoding="utf-8"
        )
        if cleanup.returncode == 0:
            cleanup_calls = 1

    completed = ParsedRun(
        start.thread_id,
        start.usage,
        start.usage_events,
        start.assistant_messages
        + tuple(render_buffer_result(result) for result in results),
        start.mcp_tool_calls,
    )
    return completed, actions, cleanup_calls


def run_jsonl_command(
    command: Sequence[str],
    cwd: Path,
    stdout_path: Path,
    stderr_path: Path,
    timeout_seconds: int,
) -> ParsedRun:
    completed = subprocess.run(
        command,
        cwd=cwd,
        text=True,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        timeout=timeout_seconds,
        check=False,
    )
    stdout_path.write_text(completed.stdout, encoding="utf-8")
    stderr_path.write_text(completed.stderr, encoding="utf-8")
    if completed.returncode != 0:
        raise RuntimeError(
            f"Codex exited with {completed.returncode}; see {stderr_path}"
        )
    parsed = parse_jsonl(completed.stdout)
    if parsed.usage_events == 0:
        raise RuntimeError(f"No turn.completed usage found in {stdout_path}")
    return parsed


def create_run_directory(output_root: Path, case_id: str) -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    candidate = output_root / f"{stamp}-{case_id}"
    suffix = 2
    while candidate.exists():
        candidate = output_root / f"{stamp}-{case_id}-{suffix}"
        suffix += 1
    candidate.mkdir(parents=True)
    return candidate


def render_review(case: dict[str, Any], runs: dict[str, ParsedRun]) -> str:
    rubric = "\n".join(f"- {item}" for item in case["rubric"])
    labels = {
        "baseline": "Concise one-shot output",
        "viewport": "Transparent viewport action transcript",
        "adaptive_viewport": "Adaptive viewport action transcript",
        "ordinary_followup": "Ordinary follow-up action transcript",
        "ordinary": "Ordinary progressive cumulative output",
        "parsnip": "Parsnip progressive cumulative output",
        "buffered": "Parsnip buffered cumulative output",
        "lean_buffered": "Lean buffered cumulative output",
        "capture": "Capture-and-carve cumulative output",
    }
    sections = [
        f"# Private paired review: {case['id']}\n\n"
        "## Predeclared rubric\n\n"
        f"{rubric}\n"
    ]
    for condition in CONDITIONS:
        if condition not in runs:
            continue
        messages = runs[condition].assistant_messages
        if condition in {"viewport", "adaptive_viewport", "ordinary_followup"} and messages:
            controls = list(case["controls"])
            if not controls or normalize_buffer_action(controls[-1]) != "full":
                controls.append("full")
            stage_names = [
                "Initial viewport",
                *(f"After “{control}”" for control in controls),
            ]
            rendered = []
            for index, message in enumerate(messages):
                stage = stage_names[index] if index < len(stage_names) else f"Response {index + 1}"
                rendered.append(f"### {stage}\n\n{message}")
            text = "\n\n---\n\n".join(rendered)
        else:
            text = "\n\n---\n\n".join(messages) or "[No agent message]"
        sections.append(f"\n## {labels[condition]}\n\n{text}\n")
    return "".join(sections)


def summarize_condition(
    run: ParsedRun,
    rates: dict[str, float] | None,
    *,
    local_navigation_calls: int = 0,
    local_cleanup_calls: int = 0,
    exact_full_verified: bool | None = None,
    marker_protocol_verified: bool | None = None,
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "assistant_turns": run.usage_events,
        "codex_turns": run.usage_events,
        "usage": run.usage,
        "reported_token_total": reported_token_total(run.usage),
        "visible_word_proxy": sum(
            len(message.split()) for message in run.assistant_messages
        ),
        "local_navigation_calls": local_navigation_calls,
        "local_cleanup_calls": local_cleanup_calls,
        "post_initial_codex_turns": max(run.usage_events - 1, 0),
    }
    if local_navigation_calls:
        result["zero_model_navigation_verified"] = run.usage_events == 1
    if exact_full_verified is not None:
        result["exact_full_verified"] = exact_full_verified
    if marker_protocol_verified is not None:
        result["marker_protocol_verified"] = marker_protocol_verified
    if rates is not None:
        result["estimated_cost_usd"] = estimated_cost_usd(run.usage, rates)
    return result


def aggregate_summaries(
    summaries: Sequence[dict[str, Any]],
    selected_conditions: Sequence[str] = CONDITIONS,
) -> dict[str, Any]:
    usage_by_condition = {
        condition: {field: 0 for field in USAGE_FIELDS}
        for condition in selected_conditions
    }
    reported_ratios = {
        condition: [] for condition in selected_conditions if condition != "baseline"
    }
    cost_ratios = {
        condition: [] for condition in selected_conditions if condition != "baseline"
    }
    for summary in summaries:
        for condition in selected_conditions:
            for field in USAGE_FIELDS:
                usage_by_condition[condition][field] += summary[condition]["usage"][field]
        for condition in selected_conditions:
            if condition == "baseline":
                continue
            ratio = summary["ratios"][condition]["reported_token_ratio"]
            if ratio is not None:
                reported_ratios[condition].append(ratio)
            cost_ratio = summary["ratios"][condition].get("estimated_cost_ratio")
            if cost_ratio is not None:
                cost_ratios[condition].append(cost_ratio)

    baseline_total = reported_token_total(usage_by_condition["baseline"])
    condition_totals: dict[str, Any] = {}
    for condition in selected_conditions:
        usage = usage_by_condition[condition]
        total = reported_token_total(usage)
        condition_summary: dict[str, Any] = {
            "usage": usage,
            "reported_token_total": total,
            "assistant_turns": sum(
                summary[condition]["assistant_turns"] for summary in summaries
            ),
            "local_navigation_calls": sum(
                summary[condition].get("local_navigation_calls", 0)
                for summary in summaries
            ),
            "ratio_to_baseline": safe_ratio(total, baseline_total),
        }
        if condition != "baseline":
            values = reported_ratios[condition]
            condition_summary["median_case_ratio_to_baseline"] = (
                statistics.median(values) if values else None
            )
        if summaries and "estimated_cost_usd" in summaries[0][condition]:
            cost = sum(summary[condition]["estimated_cost_usd"] for summary in summaries)
            condition_summary["estimated_cost_usd"] = cost
            baseline_cost = sum(
                summary["baseline"]["estimated_cost_usd"] for summary in summaries
            )
            condition_summary["estimated_cost_ratio_to_baseline"] = safe_ratio(
                cost, baseline_cost
            )
            if condition != "baseline":
                values = cost_ratios[condition]
                condition_summary["median_case_estimated_cost_ratio_to_baseline"] = (
                    statistics.median(values) if values else None
                )
        condition_totals[condition] = condition_summary

    aggregate: dict[str, Any] = {
        "case_count": len(summaries),
        "conditions": condition_totals,
        "baseline_usage": usage_by_condition["baseline"],
        "baseline_reported_token_total": baseline_total,
        "baseline_assistant_turns": condition_totals["baseline"]["assistant_turns"],
    }
    for primary in (
        "parsnip",
        "viewport",
        "adaptive_viewport",
        "ordinary_followup",
        "capture",
    ):
        if primary not in condition_totals:
            continue
        primary_summary = condition_totals[primary]
        aggregate.update(
            {
                f"{primary}_usage": usage_by_condition[primary],
                f"{primary}_reported_token_total": primary_summary[
                    "reported_token_total"
                ],
                f"{primary}_total_reported_token_ratio": primary_summary[
                    "ratio_to_baseline"
                ],
                f"{primary}_median_case_reported_token_ratio": primary_summary[
                    "median_case_ratio_to_baseline"
                ],
                f"{primary}_assistant_turns": primary_summary["assistant_turns"],
            }
        )
        if "estimated_cost_usd" in primary_summary:
            aggregate.update(
                {
                    "baseline_estimated_cost_usd": condition_totals["baseline"][
                        "estimated_cost_usd"
                    ],
                    f"{primary}_estimated_cost_usd": primary_summary[
                        "estimated_cost_usd"
                    ],
                    f"{primary}_total_estimated_cost_ratio": primary_summary[
                        "estimated_cost_ratio_to_baseline"
                    ],
                    f"{primary}_median_case_estimated_cost_ratio": primary_summary[
                        "median_case_estimated_cost_ratio_to_baseline"
                    ],
                }
            )
    if "parsnip" in condition_totals:
        aggregate.update(
            {
                "total_reported_token_ratio": condition_totals["parsnip"][
                    "ratio_to_baseline"
                ],
                "median_case_reported_token_ratio": condition_totals["parsnip"][
                    "median_case_ratio_to_baseline"
                ],
                "parsnip_reported_token_total": condition_totals["parsnip"][
                    "reported_token_total"
                ],
                "parsnip_assistant_turns": condition_totals["parsnip"][
                    "assistant_turns"
                ],
            }
        )
    return aggregate


def _run_legacy_case(
    case: dict[str, Any],
    args: argparse.Namespace,
    repo_root: Path,
    output_root: Path,
    rates: dict[str, float] | None,
) -> dict[str, Any]:
    run_dir = create_run_directory(output_root, case["id"])

    baseline_command = build_start_command(
        args.codex,
        repo_root,
        case["baseline_prompt"],
        args.model,
        ephemeral=True,
    )
    baseline = run_jsonl_command(
        baseline_command,
        repo_root,
        run_dir / "baseline.jsonl",
        run_dir / "baseline.stderr.log",
        args.timeout,
    )

    ordinary_start_command = build_start_command(
        args.codex,
        repo_root,
        ordinary_progressive_prompt(case["parsnip_prompt"]),
        args.model,
        ephemeral=False,
    )
    ordinary_runs = [
        run_jsonl_command(
            ordinary_start_command,
            repo_root,
            run_dir / "ordinary-00.jsonl",
            run_dir / "ordinary-00.stderr.log",
            args.timeout,
        )
    ]
    ordinary_thread_id = ordinary_runs[0].thread_id
    if not ordinary_thread_id:
        raise RuntimeError("Ordinary progressive start did not emit a thread id")
    for index, control in enumerate(case["controls"], start=1):
        ordinary_runs.append(
            run_jsonl_command(
                build_resume_command(
                    args.codex, ordinary_thread_id, control, args.model
                ),
                repo_root,
                run_dir / f"ordinary-{index:02d}.jsonl",
                run_dir / f"ordinary-{index:02d}.stderr.log",
                args.timeout,
            )
        )
    ordinary = combine_runs(ordinary_runs)

    parsnip_start_command = build_start_command(
        args.codex,
        repo_root,
        attach_parsnip_locator(case["parsnip_prompt"], repo_root),
        args.model,
        ephemeral=False,
    )
    parsnip_runs = [
        run_jsonl_command(
            parsnip_start_command,
            repo_root,
            run_dir / "parsnip-00.jsonl",
            run_dir / "parsnip-00.stderr.log",
            args.timeout,
        )
    ]
    thread_id = parsnip_runs[0].thread_id
    if not thread_id:
        raise RuntimeError("Parsnip start did not emit a thread id")

    for index, control in enumerate(case["controls"], start=1):
        command = build_resume_command(args.codex, thread_id, control, args.model)
        parsnip_runs.append(
            run_jsonl_command(
                command,
                repo_root,
                run_dir / f"parsnip-{index:02d}.jsonl",
                run_dir / f"parsnip-{index:02d}.stderr.log",
                args.timeout,
            )
        )

    parsnip = combine_runs(parsnip_runs)

    buffered_start = run_jsonl_command(
        build_start_command(
            args.codex,
            repo_root,
            attach_parsnip_locator(
                buffered_prompt(case["parsnip_prompt"]), repo_root
            ),
            args.model,
            ephemeral=True,
        ),
        repo_root,
        run_dir / "buffered-00.jsonl",
        run_dir / "buffered-00.stderr.log",
        args.timeout,
    )
    buffered, buffer_actions, cleanup_calls = complete_buffer_locally(
        buffered_start,
        create_tool="create_answer_capsule",
        controls=case["controls"],
        artifact_prefix="buffered",
        repo_root=repo_root,
        run_dir=run_dir,
        timeout_seconds=args.timeout,
    )

    lean_start = run_jsonl_command(
        build_start_command(
            args.codex,
            repo_root,
            lean_buffered_prompt(case["parsnip_prompt"]),
            args.model,
            ephemeral=True,
        ),
        repo_root,
        run_dir / "lean-buffered-00.jsonl",
        run_dir / "lean-buffered-00.stderr.log",
        args.timeout,
    )
    lean_buffered, lean_actions, lean_cleanup_calls = complete_buffer_locally(
        lean_start,
        create_tool="create_lean_answer_capsule",
        controls=case["controls"],
        artifact_prefix="lean-buffered",
        repo_root=repo_root,
        run_dir=run_dir,
        timeout_seconds=args.timeout,
    )

    runs = {
        "baseline": baseline,
        "ordinary": ordinary,
        "parsnip": parsnip,
        "buffered": buffered,
        "lean_buffered": lean_buffered,
    }
    condition_summaries = {
        condition: summarize_condition(run, rates)
        for condition, run in runs.items()
    }
    condition_summaries["buffered"] = summarize_condition(
        buffered,
        rates,
        local_navigation_calls=len(buffer_actions),
        local_cleanup_calls=cleanup_calls,
    )
    condition_summaries["lean_buffered"] = summarize_condition(
        lean_buffered,
        rates,
        local_navigation_calls=len(lean_actions),
        local_cleanup_calls=lean_cleanup_calls,
    )
    ratios: dict[str, dict[str, float | None]] = {}
    baseline_summary = condition_summaries["baseline"]
    for condition in CONDITIONS[1:]:
        condition_summary = condition_summaries[condition]
        ratios[condition] = {
            "reported_token_ratio": safe_ratio(
                condition_summary["reported_token_total"],
                baseline_summary["reported_token_total"],
            )
        }
        if rates is not None:
            ratios[condition]["estimated_cost_ratio"] = safe_ratio(
                condition_summary["estimated_cost_usd"],
                baseline_summary["estimated_cost_usd"],
            )

    parsnip_summary = condition_summaries["parsnip"]
    summary: dict[str, Any] = {
        "case_id": case["id"],
        "category": case["category"],
        "model": args.model or "configured default",
        "rubric": case["rubric"],
        "controls": case["controls"],
        **condition_summaries,
        "ratios": ratios,
        "reported_token_ratio": ratios["parsnip"]["reported_token_ratio"],
        "buffer_actions": buffer_actions,
        "lean_buffer_actions": lean_actions,
        "usage_metadata": "verified from turn.completed events",
        "billable_cost": (
            "estimated from supplied rates"
            if rates is not None
            else "unverified; no rates supplied"
        ),
        "output_directory": str(run_dir),
    }
    if rates is not None:
        summary["estimated_cost_ratio"] = ratios["parsnip"][
            "estimated_cost_ratio"
        ]

    (run_dir / "review.md").write_text(
        render_review(case, runs), encoding="utf-8"
    )
    (run_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return summary


def run_case(
    case: dict[str, Any],
    args: argparse.Namespace,
    repo_root: Path,
    output_root: Path,
    rates: dict[str, float] | None,
) -> dict[str, Any]:
    selected = tuple(args.conditions)
    run_dir = create_run_directory(output_root, case["id"])
    runs: dict[str, ParsedRun] = {}
    local_metadata: dict[str, Any] = {}

    if "baseline" in selected:
        if args.reuse_baseline_jsonl:
            baseline_path = require_private_output(args.reuse_baseline_jsonl, repo_root)
            runs["baseline"] = parse_jsonl(baseline_path.read_text(encoding="utf-8"))
            if (
                runs["baseline"].usage_events != 1
                or not runs["baseline"].assistant_messages
                or not runs["baseline"].thread_id
            ):
                raise RuntimeError(
                    "Reused baseline must contain one completed turn, a final answer, and a thread id"
                )
        else:
            runs["baseline"] = run_jsonl_command(
                build_start_command(
                    args.codex,
                    repo_root,
                    case["baseline_prompt"],
                    args.model,
                    ephemeral=not any(
                        condition in selected
                        for condition in (
                            "viewport",
                            "adaptive_viewport",
                            "ordinary_followup",
                        )
                    ),
                ),
                repo_root,
                run_dir / "baseline.jsonl",
                run_dir / "baseline.stderr.log",
                args.timeout,
            )

    if "viewport" in selected:
        baseline = runs["baseline"]
        if not baseline.assistant_messages:
            raise RuntimeError("Baseline did not return an answer for viewport reuse")
        if not baseline.thread_id:
            raise RuntimeError("Baseline did not emit a thread id for viewport accounting")
        response = baseline.assistant_messages[-1]
        response_file = run_dir / "viewport-response.md"
        response_file.write_text(response, encoding="utf-8")
        start_result = run_local_json_command(
            build_viewport_file_command(
                repo_root,
                response_file,
                baseline.thread_id,
                resumable=not bool(args.reuse_baseline_jsonl),
            ),
            repo_root,
            run_dir / "viewport-00.json",
            run_dir / "viewport-00.stderr.log",
            args.timeout,
        )
        start_result["capture_usage"] = baseline.usage
        start_result["capture_raw_sha256"] = hashlib.sha256(
            response.encode("utf-8")
        ).hexdigest()
        source = start_result.get("source")
        start_result["source"] = {
            **(source if isinstance(source, dict) else {}),
            "thread_id": baseline.thread_id,
        }
        (
            completed,
            actions,
            cleanup_calls,
            exact_full_verified,
            viewport_protocol_verified,
        ) = complete_capture_locally(
            start_result,
            controls=case["controls"],
            repo_root=repo_root,
            run_dir=run_dir,
            timeout_seconds=args.timeout,
            expected_protocol="viewport-v1",
            artifact_prefix="viewport",
            route_controls=True,
        )
        runs["viewport"] = completed
        local_metadata["viewport"] = (
            actions,
            cleanup_calls,
            exact_full_verified,
            viewport_protocol_verified,
        )

    if "adaptive_viewport" in selected:
        if args.reuse_baseline_jsonl:
            raise RuntimeError(
                "Adaptive viewport re-entry requires a newly retained baseline thread"
            )
        baseline = runs["baseline"]
        if not baseline.assistant_messages or not baseline.thread_id:
            raise RuntimeError("Baseline did not return a resumable answer for adaptive viewport")
        response = baseline.assistant_messages[-1]
        response_file = run_dir / "adaptive-response.md"
        response_file.write_text(response, encoding="utf-8")
        start_result = run_local_json_command(
            build_viewport_file_command(
                repo_root,
                response_file,
                baseline.thread_id,
                resumable=True,
            ),
            repo_root,
            run_dir / "adaptive-00.json",
            run_dir / "adaptive-00.stderr.log",
            args.timeout,
        )
        start_result["capture_usage"] = baseline.usage
        start_result["capture_raw_sha256"] = hashlib.sha256(
            response.encode("utf-8")
        ).hexdigest()
        (
            completed,
            actions,
            cleanup_calls,
            initial_exact_full_verified,
            exact_full_verified,
            adaptive_protocol_verified,
            thread_lineage_verified,
            model_reentry_turns,
            reentry_usage,
        ) = complete_adaptive_viewport(
            start_result,
            controls=case["controls"],
            model=args.model,
            repo_root=repo_root,
            run_dir=run_dir,
            timeout_seconds=args.timeout,
        )
        runs["adaptive_viewport"] = completed
        local_metadata["adaptive_viewport"] = (
            actions,
            cleanup_calls,
            initial_exact_full_verified,
            exact_full_verified,
            adaptive_protocol_verified,
            thread_lineage_verified,
            model_reentry_turns,
            reentry_usage,
        )

    if "ordinary_followup" in selected:
        if args.reuse_baseline_jsonl:
            raise RuntimeError(
                "Ordinary follow-up requires a newly retained baseline thread"
            )
        baseline = runs["baseline"]
        if not baseline.assistant_messages or not baseline.thread_id:
            raise RuntimeError(
                "Baseline did not return a resumable answer for ordinary follow-up"
            )
        response = baseline.assistant_messages[-1]
        response_file = run_dir / "ordinary-followup-response.md"
        response_file.write_text(response, encoding="utf-8")
        start_result = run_local_json_command(
            build_viewport_file_command(
                repo_root,
                response_file,
                baseline.thread_id,
                resumable=True,
            ),
            repo_root,
            run_dir / "ordinary-followup-00.json",
            run_dir / "ordinary-followup-00.stderr.log",
            args.timeout,
        )
        start_result["capture_usage"] = baseline.usage
        start_result["capture_raw_sha256"] = hashlib.sha256(
            response.encode("utf-8")
        ).hexdigest()
        (
            completed,
            actions,
            cleanup_calls,
            initial_exact_full_verified,
            exact_full_verified,
            viewport_protocol_verified,
            thread_lineage_verified,
            model_followup_turns,
            followup_usage,
        ) = complete_adaptive_viewport(
            start_result,
            controls=case["controls"],
            model=args.model,
            repo_root=repo_root,
            run_dir=run_dir,
            timeout_seconds=args.timeout,
            artifact_prefix="ordinary-followup",
            ordinary_followup=True,
        )
        runs["ordinary_followup"] = completed
        local_metadata["ordinary_followup"] = (
            actions,
            cleanup_calls,
            initial_exact_full_verified,
            exact_full_verified,
            viewport_protocol_verified,
            thread_lineage_verified,
            model_followup_turns,
            followup_usage,
        )

    if "ordinary" in selected:
        ordinary_runs = [
            run_jsonl_command(
                build_start_command(
                    args.codex,
                    repo_root,
                    ordinary_progressive_prompt(case["parsnip_prompt"]),
                    args.model,
                    ephemeral=False,
                ),
                repo_root,
                run_dir / "ordinary-00.jsonl",
                run_dir / "ordinary-00.stderr.log",
                args.timeout,
            )
        ]
        thread_id = ordinary_runs[0].thread_id
        if not thread_id:
            raise RuntimeError("Ordinary progressive start did not emit a thread id")
        for index, control in enumerate(case["controls"], start=1):
            ordinary_runs.append(
                run_jsonl_command(
                    build_resume_command(args.codex, thread_id, control, args.model),
                    repo_root,
                    run_dir / f"ordinary-{index:02d}.jsonl",
                    run_dir / f"ordinary-{index:02d}.stderr.log",
                    args.timeout,
                )
            )
        runs["ordinary"] = combine_runs(ordinary_runs)

    if "parsnip" in selected:
        parsnip_runs = [
            run_jsonl_command(
                build_start_command(
                    args.codex,
                    repo_root,
                    attach_parsnip_locator(case["parsnip_prompt"], repo_root),
                    args.model,
                    ephemeral=False,
                ),
                repo_root,
                run_dir / "parsnip-00.jsonl",
                run_dir / "parsnip-00.stderr.log",
                args.timeout,
            )
        ]
        thread_id = parsnip_runs[0].thread_id
        if not thread_id:
            raise RuntimeError("Parsnip start did not emit a thread id")
        for index, control in enumerate(case["controls"], start=1):
            parsnip_runs.append(
                run_jsonl_command(
                    build_resume_command(args.codex, thread_id, control, args.model),
                    repo_root,
                    run_dir / f"parsnip-{index:02d}.jsonl",
                    run_dir / f"parsnip-{index:02d}.stderr.log",
                    args.timeout,
                )
            )
        runs["parsnip"] = combine_runs(parsnip_runs)

    if "buffered" in selected:
        start = run_jsonl_command(
            build_start_command(
                args.codex,
                repo_root,
                attach_parsnip_locator(
                    buffered_prompt(case["parsnip_prompt"]), repo_root
                ),
                args.model,
                ephemeral=True,
            ),
            repo_root,
            run_dir / "buffered-00.jsonl",
            run_dir / "buffered-00.stderr.log",
            args.timeout,
        )
        completed, actions, cleanup_calls = complete_buffer_locally(
            start,
            create_tool="create_answer_capsule",
            controls=case["controls"],
            artifact_prefix="buffered",
            repo_root=repo_root,
            run_dir=run_dir,
            timeout_seconds=args.timeout,
        )
        runs["buffered"] = completed
        local_metadata["buffered"] = (actions, cleanup_calls)

    if "lean_buffered" in selected:
        start = run_jsonl_command(
            build_start_command(
                args.codex,
                repo_root,
                lean_buffered_prompt(case["parsnip_prompt"]),
                args.model,
                ephemeral=True,
            ),
            repo_root,
            run_dir / "lean-buffered-00.jsonl",
            run_dir / "lean-buffered-00.stderr.log",
            args.timeout,
        )
        completed, actions, cleanup_calls = complete_buffer_locally(
            start,
            create_tool="create_lean_answer_capsule",
            controls=case["controls"],
            artifact_prefix="lean-buffered",
            repo_root=repo_root,
            run_dir=run_dir,
            timeout_seconds=args.timeout,
        )
        runs["lean_buffered"] = completed
        local_metadata["lean_buffered"] = (actions, cleanup_calls)

    if "capture" in selected:
        prompt_file = run_dir / "capture-request.md"
        prompt_file.write_text(case["baseline_prompt"], encoding="utf-8")
        start_result = run_local_json_command(
            build_capture_run_command(
                repo_root, prompt_file, args.model, args.timeout
            ),
            repo_root,
            run_dir / "capture-00.json",
            run_dir / "capture-00.stderr.log",
            args.timeout + 5,
        )
        (
            completed,
            actions,
            cleanup_calls,
            exact_full_verified,
            marker_protocol_verified,
        ) = complete_capture_locally(
            start_result,
            controls=case["controls"],
            repo_root=repo_root,
            run_dir=run_dir,
            timeout_seconds=args.timeout,
        )
        runs["capture"] = completed
        local_metadata["capture"] = (
            actions,
            cleanup_calls,
            exact_full_verified,
            marker_protocol_verified,
        )

    condition_summaries = {
        condition: summarize_condition(runs[condition], rates)
        for condition in selected
    }
    for condition in ("buffered", "lean_buffered"):
        if condition in local_metadata:
            actions, cleanup_calls = local_metadata[condition]
            condition_summaries[condition] = summarize_condition(
                runs[condition],
                rates,
                local_navigation_calls=len(actions),
                local_cleanup_calls=cleanup_calls,
            )
    if "capture" in local_metadata:
        (
            actions,
            cleanup_calls,
            exact_full_verified,
            marker_protocol_verified,
        ) = local_metadata["capture"]
        condition_summaries["capture"] = summarize_condition(
            runs["capture"],
            rates,
            local_navigation_calls=len(actions),
            local_cleanup_calls=cleanup_calls,
            exact_full_verified=exact_full_verified,
            marker_protocol_verified=marker_protocol_verified,
        )
    if "viewport" in local_metadata:
        (
            actions,
            cleanup_calls,
            exact_full_verified,
            viewport_protocol_verified,
        ) = local_metadata["viewport"]
        condition_summaries["viewport"] = summarize_condition(
            runs["viewport"],
            rates,
            local_navigation_calls=len(actions),
            local_cleanup_calls=cleanup_calls,
            exact_full_verified=exact_full_verified,
        )
        condition_summaries["viewport"]["viewport_protocol_verified"] = (
            viewport_protocol_verified
        )
        condition_summaries["viewport"]["shared_baseline_turn_verified"] = (
            runs["viewport"].thread_id == runs["baseline"].thread_id
            and runs["viewport"].usage == runs["baseline"].usage
        )
        condition_summaries["viewport"]["model_escalation_requests"] = sum(
            action == "model_required" for action in actions
        )
        condition_summaries["viewport"]["all_intents_satisfied_locally"] = all(
            action != "model_required" for action in actions
        )
    if "adaptive_viewport" in local_metadata:
        (
            actions,
            cleanup_calls,
            initial_exact_full_verified,
            exact_full_verified,
            adaptive_protocol_verified,
            thread_lineage_verified,
            model_reentry_turns,
            reentry_usage,
        ) = local_metadata["adaptive_viewport"]
        condition_summaries["adaptive_viewport"] = summarize_condition(
            runs["adaptive_viewport"],
            rates,
            local_cleanup_calls=cleanup_calls,
            exact_full_verified=exact_full_verified,
        )
        condition_summaries["adaptive_viewport"].update(
            {
                "local_interaction_calls": len(actions),
                "initial_exact_full_verified": initial_exact_full_verified,
                "viewport_protocol_verified": adaptive_protocol_verified,
                "retained_baseline_thread_verified": (
                    runs["adaptive_viewport"].thread_id == runs["baseline"].thread_id
                ),
                "thread_lineage_verified": thread_lineage_verified,
                "model_reentry_turns": model_reentry_turns,
                "reentry_usage": reentry_usage,
                "reentry_reported_token_total": reported_token_total(reentry_usage),
            }
        )
    if "ordinary_followup" in local_metadata:
        (
            actions,
            cleanup_calls,
            initial_exact_full_verified,
            exact_full_verified,
            viewport_protocol_verified,
            thread_lineage_verified,
            model_followup_turns,
            followup_usage,
        ) = local_metadata["ordinary_followup"]
        condition_summaries["ordinary_followup"] = summarize_condition(
            runs["ordinary_followup"],
            rates,
            local_cleanup_calls=cleanup_calls,
            exact_full_verified=exact_full_verified,
        )
        condition_summaries["ordinary_followup"].update(
            {
                "local_interaction_calls": len(actions),
                "initial_exact_full_verified": initial_exact_full_verified,
                "viewport_protocol_verified": viewport_protocol_verified,
                "retained_baseline_thread_verified": (
                    runs["ordinary_followup"].thread_id == runs["baseline"].thread_id
                ),
                "thread_lineage_verified": thread_lineage_verified,
                "model_followup_turns": model_followup_turns,
                "followup_usage": followup_usage,
                "followup_reported_token_total": reported_token_total(followup_usage),
            }
        )

    baseline_summary = condition_summaries["baseline"]
    ratios: dict[str, dict[str, float | None]] = {}
    for condition in selected:
        if condition == "baseline":
            continue
        condition_summary = condition_summaries[condition]
        ratios[condition] = {
            "reported_token_ratio": safe_ratio(
                condition_summary["reported_token_total"],
                baseline_summary["reported_token_total"],
            )
        }
        if rates is not None:
            ratios[condition]["estimated_cost_ratio"] = safe_ratio(
                condition_summary["estimated_cost_usd"],
                baseline_summary["estimated_cost_usd"],
            )

    summary: dict[str, Any] = {
        "case_id": case["id"],
        "category": case["category"],
        "model": args.model or "configured default",
        "rubric": case["rubric"],
        "controls": case["controls"],
        "selected_conditions": list(selected),
        **condition_summaries,
        "ratios": ratios,
        "usage_metadata": "verified from Codex or app-server usage events",
        "billable_cost": (
            "estimated from supplied rates"
            if rates is not None
            else "unverified; no rates supplied"
        ),
        "output_directory": str(run_dir),
        "baseline_reused": bool(args.reuse_baseline_jsonl),
    }
    for condition, metadata in local_metadata.items():
        summary[f"{condition}_actions"] = metadata[0]
    if "parsnip" in ratios:
        summary["reported_token_ratio"] = ratios["parsnip"][
            "reported_token_ratio"
        ]
        if rates is not None:
            summary["estimated_cost_ratio"] = ratios["parsnip"][
                "estimated_cost_ratio"
            ]
    if "capture" in ratios:
        summary["capture_reported_token_ratio"] = ratios["capture"][
            "reported_token_ratio"
        ]
        if rates is not None:
            summary["capture_estimated_cost_ratio"] = ratios["capture"][
                "estimated_cost_ratio"
            ]
    if "viewport" in ratios:
        summary["viewport_reported_token_ratio"] = ratios["viewport"][
            "reported_token_ratio"
        ]
        if rates is not None:
            summary["viewport_estimated_cost_ratio"] = ratios["viewport"][
                "estimated_cost_ratio"
            ]
    if "adaptive_viewport" in ratios:
        summary["adaptive_viewport_reported_token_ratio"] = ratios[
            "adaptive_viewport"
        ]["reported_token_ratio"]
        if rates is not None:
            summary["adaptive_viewport_estimated_cost_ratio"] = ratios[
                "adaptive_viewport"
            ]["estimated_cost_ratio"]
    if "ordinary_followup" in ratios:
        summary["ordinary_followup_reported_token_ratio"] = ratios[
            "ordinary_followup"
        ]["reported_token_ratio"]
        if rates is not None:
            summary["ordinary_followup_estimated_cost_ratio"] = ratios[
                "ordinary_followup"
            ]["estimated_cost_ratio"]

    (run_dir / "review.md").write_text(
        render_review(case, runs), encoding="utf-8"
    )
    (run_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return summary


def select_cases(
    cases: list[dict[str, Any]], selected_ids: list[str] | None, run_all: bool
) -> list[dict[str, Any]]:
    if run_all:
        return cases
    if not selected_ids:
        raise ValueError("Choose at least one --case or pass --all")
    by_id = {case["id"]: case for case in cases}
    missing = [case_id for case_id in selected_ids if case_id not in by_id]
    if missing:
        raise ValueError(f"Unknown case id(s): {', '.join(missing)}")
    return [by_id[case_id] for case_id in selected_ids]


def select_conditions(selected: Sequence[str] | None) -> tuple[str, ...]:
    if not selected:
        return CONDITIONS
    chosen = tuple(condition for condition in CONDITIONS if condition in selected)
    if "baseline" not in chosen:
        raise ValueError("Selected conditions must include baseline for paired ratios")
    return chosen


def _legacy_dry_run_commands(
    cases: list[dict[str, Any]], args: argparse.Namespace, repo_root: Path
) -> list[dict[str, Any]]:
    plans: list[dict[str, Any]] = []
    for case in cases:
        plans.append(
            {
                "case_id": case["id"],
                "baseline": shlex.join(
                    build_start_command(
                        args.codex,
                        repo_root,
                        case["baseline_prompt"],
                        args.model,
                        ephemeral=True,
                    )
                ),
                "ordinary_start": shlex.join(
                    build_start_command(
                        args.codex,
                        repo_root,
                        ordinary_progressive_prompt(case["parsnip_prompt"]),
                        args.model,
                        ephemeral=False,
                    )
                ),
                "parsnip_start": shlex.join(
                    build_start_command(
                        args.codex,
                        repo_root,
                        attach_parsnip_locator(case["parsnip_prompt"], repo_root),
                        args.model,
                        ephemeral=False,
                    )
                ),
                "buffered_start": shlex.join(
                    build_start_command(
                        args.codex,
                        repo_root,
                        attach_parsnip_locator(
                            buffered_prompt(case["parsnip_prompt"]), repo_root
                        ),
                        args.model,
                        ephemeral=True,
                    )
                ),
                "lean_buffered_start": shlex.join(
                    build_start_command(
                        args.codex,
                        repo_root,
                        lean_buffered_prompt(case["parsnip_prompt"]),
                        args.model,
                        ephemeral=True,
                    )
                ),
                "resume_controls": [
                    shlex.join(
                        build_resume_command(
                            args.codex, "<thread-id>", control, args.model
                        )
                    )
                    for control in case["controls"]
                ],
                "buffered_local_controls": [
                    shlex.join(
                        build_buffer_cli_command(
                            repo_root,
                            "<capsule-session-id>",
                            normalize_buffer_action(control),
                        )
                    )
                    for control in case["controls"]
                ],
                "buffered_local_consolidation": shlex.join(
                    build_buffer_cli_command(
                        repo_root, "<capsule-session-id>", "full"
                    )
                ),
                "lean_buffered_local_controls": [
                    shlex.join(
                        build_buffer_cli_command(
                            repo_root,
                            "<lean-capsule-session-id>",
                            normalize_buffer_action(control),
                        )
                    )
                    for control in case["controls"]
                ],
            }
        )
    return plans


def dry_run_commands(
    cases: list[dict[str, Any]], args: argparse.Namespace, repo_root: Path
) -> list[dict[str, Any]]:
    plans: list[dict[str, Any]] = []
    for case in cases:
        plan: dict[str, Any] = {
            "case_id": case["id"],
            "selected_conditions": list(args.conditions),
        }
        if "baseline" in args.conditions:
            if args.reuse_baseline_jsonl:
                plan["baseline"] = f"Reuse {args.reuse_baseline_jsonl}"
            else:
                plan["baseline"] = shlex.join(
                    build_start_command(
                        args.codex,
                        repo_root,
                        case["baseline_prompt"],
                        args.model,
                        ephemeral=not any(
                            condition in args.conditions
                            for condition in (
                                "viewport",
                                "adaptive_viewport",
                                "ordinary_followup",
                            )
                        ),
                    )
                )
        if "viewport" in args.conditions:
            plan["viewport_source"] = "Reuse the exact baseline final answer"
            plan["viewport_ingest"] = shlex.join(
                build_viewport_file_command(
                    repo_root,
                    Path("<private-run-dir>/viewport-response.md"),
                    "<baseline-thread-id>",
                    resumable=True,
                )
            )
            plan["viewport_natural_requests"] = [
                shlex.join(
                    build_capture_route_command(
                        repo_root,
                        "<viewport-session-id>",
                        control,
                    )
                )
                for control in case["controls"]
            ]
        if "adaptive_viewport" in args.conditions:
            plan["adaptive_viewport_source"] = (
                "Retain and reuse the exact baseline thread and final answer"
            )
            plan["adaptive_viewport_ingest"] = shlex.join(
                build_viewport_file_command(
                    repo_root,
                    Path("<private-run-dir>/adaptive-response.md"),
                    "<baseline-thread-id>",
                    resumable=True,
                )
            )
            plan["adaptive_natural_requests"] = [
                shlex.join(
                    build_capture_reentry_command(
                        repo_root,
                        "<current-viewport-session-id>",
                        Path(f"<private-run-dir>/adaptive-request-{index:02d}.md"),
                        args.model,
                        args.timeout,
                    )
                )
                for index, _control in enumerate(case["controls"], start=1)
            ]
        if "ordinary_followup" in args.conditions:
            plan["ordinary_followup_source"] = (
                "Fork the retained baseline with the same visible slice and raw request"
            )
            plan["ordinary_followup_ingest"] = shlex.join(
                build_viewport_file_command(
                    repo_root,
                    Path("<private-run-dir>/ordinary-followup-response.md"),
                    "<baseline-thread-id>",
                    resumable=True,
                )
            )
            plan["ordinary_followup_natural_requests"] = [
                shlex.join(
                    build_capture_reentry_command(
                        repo_root,
                        "<current-viewport-session-id>",
                        Path(
                            f"<private-run-dir>/ordinary-followup-request-{index:02d}.md"
                        ),
                        args.model,
                        args.timeout,
                        ordinary_followup=True,
                    )
                )
                for index, _control in enumerate(case["controls"], start=1)
            ]
        if "ordinary" in args.conditions:
            plan["ordinary_start"] = shlex.join(
                build_start_command(
                    args.codex,
                    repo_root,
                    ordinary_progressive_prompt(case["parsnip_prompt"]),
                    args.model,
                    ephemeral=False,
                )
            )
            plan["ordinary_resume_controls"] = [
                shlex.join(
                    build_resume_command(
                        args.codex, "<thread-id>", control, args.model
                    )
                )
                for control in case["controls"]
            ]
        if "parsnip" in args.conditions:
            plan["parsnip_start"] = shlex.join(
                build_start_command(
                    args.codex,
                    repo_root,
                    attach_parsnip_locator(case["parsnip_prompt"], repo_root),
                    args.model,
                    ephemeral=False,
                )
            )
            plan["parsnip_resume_controls"] = [
                shlex.join(
                    build_resume_command(
                        args.codex, "<thread-id>", control, args.model
                    )
                )
                for control in case["controls"]
            ]
        if "buffered" in args.conditions:
            plan["buffered_start"] = shlex.join(
                build_start_command(
                    args.codex,
                    repo_root,
                    attach_parsnip_locator(
                        buffered_prompt(case["parsnip_prompt"]), repo_root
                    ),
                    args.model,
                    ephemeral=True,
                )
            )
        if "lean_buffered" in args.conditions:
            plan["lean_buffered_start"] = shlex.join(
                build_start_command(
                    args.codex,
                    repo_root,
                    lean_buffered_prompt(case["parsnip_prompt"]),
                    args.model,
                    ephemeral=True,
                )
            )
        for condition, session_id, builder in (
            ("buffered", "<capsule-session-id>", build_buffer_cli_command),
            (
                "lean_buffered",
                "<lean-capsule-session-id>",
                build_buffer_cli_command,
            ),
        ):
            if condition in args.conditions:
                plan[f"{condition}_local_controls"] = [
                    shlex.join(
                        builder(
                            repo_root,
                            session_id,
                            normalize_buffer_action(control),
                        )
                    )
                    for control in case["controls"]
                ]
        if "capture" in args.conditions:
            plan["capture_start"] = shlex.join(
                build_capture_run_command(
                    repo_root,
                    Path("<private-run-dir>/capture-request.md"),
                    args.model,
                    args.timeout,
                )
            )
            plan["capture_local_controls"] = [
                shlex.join(
                    build_capture_navigation_command(
                        repo_root,
                        "<capture-session-id>",
                        normalize_buffer_action(control),
                    )
                )
                for control in case["controls"]
            ]
            plan["capture_local_consolidation"] = shlex.join(
                build_capture_navigation_command(
                    repo_root, "<capture-session-id>", "full"
                )
            )
        plans.append(plan)
    return plans


def build_parser() -> argparse.ArgumentParser:
    default_output = os.environ.get(
        "PARSNIP_EVAL_OUTPUT_DIR", str(Path.home() / ".parsnip-private-evals")
    )
    parser = argparse.ArgumentParser(
        description=(
            "Compare concise one-shot, ordinary progressive, Parsnip progressive, "
            "rich buffered, lean buffered, transparent/adaptive viewport, ordinary "
            "follow-up, and capture-and-carve Parsnip usage."
        )
    )
    parser.add_argument(
        "--cases",
        type=Path,
        default=Path(__file__).with_name("usage_cases.json"),
        help="JSON file containing synthetic paired cases.",
    )
    parser.add_argument("--case", action="append", dest="case_ids")
    parser.add_argument(
        "--condition",
        action="append",
        choices=CONDITIONS,
        dest="condition_ids",
        help="Run only selected paired conditions; repeat and include baseline.",
    )
    parser.add_argument("--all", action="store_true", help="Run every case.")
    parser.add_argument("--list", action="store_true", help="List case ids and exit.")
    parser.add_argument("--dry-run", action="store_true", help="Print commands only.")
    parser.add_argument("--output-dir", type=Path, default=Path(default_output))
    parser.add_argument(
        "--reuse-baseline-jsonl",
        type=Path,
        help="Reuse one private completed baseline JSONL for a single selected case.",
    )
    parser.add_argument("--rates", type=Path, help="Optional JSON per-million rates.")
    parser.add_argument(
        "--model", help="Use the same explicit model in every model-backed condition."
    )
    parser.add_argument("--codex", default="codex", help="Codex executable path.")
    parser.add_argument(
        "--timeout", type=int, default=900, help="Timeout per Codex turn in seconds."
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        repo_root = repository_root()
        cases = load_cases(args.cases)
        if args.list:
            for case in cases:
                print(f"{case['id']}\t{case['category']}")
            return 0
        chosen = select_cases(cases, args.case_ids, args.all)
        args.conditions = select_conditions(args.condition_ids)
        if args.reuse_baseline_jsonl and len(chosen) != 1:
            raise ValueError("--reuse-baseline-jsonl requires exactly one selected case")
        output_root = require_private_output(args.output_dir, repo_root)
        rates = load_rates(args.rates)
        if args.dry_run:
            print(json.dumps(dry_run_commands(chosen, args, repo_root), indent=2))
            return 0
        output_root.mkdir(parents=True, exist_ok=True)
        summaries = [
            run_case(case, args, repo_root, output_root, rates) for case in chosen
        ]
        report = {
            "cases": summaries,
            "aggregate": aggregate_summaries(summaries, args.conditions),
        }
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        report_path = output_root / f"{stamp}-cohort-summary.json"
        report_path.write_text(
            json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        report["cohort_summary"] = str(report_path)
        print(json.dumps(report, indent=2, sort_keys=True))
        return 0
    except (OSError, ValueError, RuntimeError, subprocess.TimeoutExpired) as exc:
        parser.exit(2, f"error: {exc}\n")


if __name__ == "__main__":
    sys.exit(main())
