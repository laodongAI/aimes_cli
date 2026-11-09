from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from . import __version__
from .delivery_report import validate_delivery_text
from .skill_route import load_skill_body, route_skills
from .project_state import show_project_state, detect_mode, load_mode_registry, set_project_state
from .project_work import assess_project_lifecycle, start_task, update_task, list_tasks, show_session, bind_session_task
from .mode_route import explain_mode\nfrom .quality_check import inspect_project_quality

PROTOCOL_VERSION = "2024-11-05"
SERVER_NAME = "aimes-governance"

TOOLS = [
    {
        "name": "aimes_assess_project_lifecycle",
        "description": "Collect bounded, read-only project structure and Git evidence to suggest lifecycle candidates. Never changes project state and never treats AIMES initialization as proof of a new project.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "aimes_task_start",
        "description": "Create an independent task record and bind it to the calling AI tool session ID. Task progress is stored separately from project lifecycle state.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "title": {"type": "string", "minLength": 1, "maxLength": 500},
                "session_id": {"type": "string", "default": "default"},
                "task_id": {"type": "string"},
                "mode": {"type": "string"},
            },
            "required": ["title", "session_id"],
        },
    },
    {
        "name": "aimes_task_list",
        "description": "List project task records, optionally filtered by AI tool session ID.",
        "inputSchema": {"type": "object", "properties": {"session_id": {"type": "string"}}},
    },
    {
        "name": "aimes_task_update",
        "description": "Update an existing task's phase or status without changing project lifecycle or another session's task.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "task_id": {"type": "string"},
                "phase": {"type": "string", "enum": ["analysis","clarification","design","review","implementation","testing","acceptance","delivery"]},
                "status": {"type": "string", "enum": ["active","blocked","completed","cancelled"]},
            },
            "required": ["task_id"],
        },
    },
    {
        "name": "aimes_session_show",
        "description": "Read one AI tool session's current task pointer and task record.",
        "inputSchema": {"type": "object", "properties": {"session_id": {"type": "string", "default": "default"}}},
    },
    {
        "name": "aimes_session_bind",
        "description": "Bind one AI tool session to an existing task record.",
        "inputSchema": {
            "type": "object",
            "properties": {"session_id": {"type": "string"}, "task_id": {"type": "string"}},
            "required": ["session_id", "task_id"],
        },
    },
    {
        "name": "aimes_explain_engineering_mode",
        "description": "Explain the selected engineering mode route, inspect registered Skills and workflow definition availability, and report quality-profile mapping limitations. Read-only; does not execute workflows or quality gates.",
        "inputSchema": {
            "type": "object",
            "properties": {"mode": {"type": "string", "description": "Engineering mode ID; omit to use the currently selected mode."}},
        },
    },
    {
        "name": "aimes_quality_inspect",
        "description": "Run deterministic read-only engineering quality checks using the quality profile mapped to the selected engineering mode, or an explicitly supplied profile. Project-wide enforce/fail_on policy remains authoritative; AI findings are not included.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "mode": {"type": "string", "description": "Engineering mode ID; defaults to persisted current mode."},
                "profile": {"type": "string", "description": "Named quality profile ID; mutually exclusive with mode."}
            }
        }
    },
    {
        "name": "aimes_project_state",
        "description": "Read the persisted AIMES project lifecycle, current engineering mode, task phase, routed Skills and next actions. Read-only; does not inspect the current AI conversation.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "aimes_detect_engineering_mode",
        "description": "Suggest engineering mode candidates from explicit task text using deterministic trigger matching. Does not read the AI conversation, call a model, or persist state; ambiguous matches must be confirmed with the user.",
        "inputSchema": {
            "type": "object",
            "properties": {"task_text": {"type": "string", "description": "Task summary in Chinese or English"}},
            "required": ["task_text"],
        },
    },
    {
        "name": "aimes_set_project_state",
        "description": "Persist project lifecycle, engineering mode, task phase or task summary. Only call after explicit user selection/approval or when AIMES governance permits a sufficiently confident inference; use source=user for explicit user choices and source=ai for AI inference. Low-confidence guesses must not be persisted.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "lifecycle": {"type": "string", "enum": ["unknown","new","planning","design","development","testing","release","operation","paused","archived"]},
                "mode": {"type": "string"},
                "phase": {"type": "string", "enum": ["analysis","clarification","design","review","implementation","testing","acceptance","delivery"]},
                "task": {"type": "string", "maxLength": 500},
                "source": {"type": "string", "enum": ["user","ai","import"]},
                "confidence": {"type": "string", "enum": ["low","medium","high"]},
            },
        },
    },
    {
        "name": "aimes_skill_route",
        "description": "Route a task description to the AIMES project skills that must be read before working. Returns skill id, authoritative file path, matched triggers, required inputs and expected outputs.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "task_text": {"type": "string", "description": "Task description in Chinese or English"},
                "top": {"type": "integer", "description": "Maximum routes to return (default 3)"},
            },
            "required": ["task_text"],
        },
    },
    {
        "name": "aimes_read_skill",
        "description": "Read the authoritative SKILL.md content for one registered AIMES skill by name. Use after aimes_skill_route to actually load the selected skill contract.",
        "inputSchema": {
            "type": "object",
            "properties": {"skill_name": {"type": "string", "description": "Skill name as registered in .aimes/skills/registry.yaml"}},
            "required": ["skill_name"],
        },
    },
    {
        "name": "aimes_validate_delivery",
        "description": "Validate an AIMES Core 8.3 fixed-heading delivery report string (evidence semantics: VERIFIED requires PASS evidence, NOT_RUN cannot be written as PASS). Read-only.",
        "inputSchema": {
            "type": "object",
            "properties": {"report_text": {"type": "string", "description": "Full markdown delivery report"}},
            "required": ["report_text"],
        },
    },
]


def _registry_path(root: Path) -> Path:
    return root / ".aimes/skills/registry.yaml"


def _tool_result(payload: dict[str, Any]) -> dict[str, Any]:
    return {"content": [{"type": "text", "text": json.dumps(payload, ensure_ascii=False, indent=2)}], "isError": False}


def _tool_error(message: str) -> dict[str, Any]:
    return {"content": [{"type": "text", "text": message}], "isError": True}


def call_tool(root: Path, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    registry = _registry_path(root)
    try:
        if name == "aimes_assess_project_lifecycle":
            return _tool_result(assess_project_lifecycle(root))
        if name == "aimes_quality_inspect":
            return _tool_result(inspect_project_quality(root, profile_id=arguments.get("profile"), mode_id=arguments.get("mode")))
        if name == "aimes_task_start":
            return _tool_result(start_task(root, arguments.get("title"),
                session_id=arguments.get("session_id", "default"),
                mode=arguments.get("mode"), task_id=arguments.get("task_id")))
        if name == "aimes_task_list":
            return _tool_result(list_tasks(root, session_id=arguments.get("session_id")))
        if name == "aimes_task_update":
            return _tool_result(update_task(root, arguments.get("task_id"),
                phase=arguments.get("phase"), status=arguments.get("status")))
        if name == "aimes_session_show":
            return _tool_result(show_session(root, arguments.get("session_id", "default")))
        if name == "aimes_session_bind":
            return _tool_result(bind_session_task(root, arguments.get("session_id"),
                arguments.get("task_id")))
    except (ValueError, OSError, TypeError) as exc:
        return _tool_error(str(exc))
    if name == "aimes_explain_engineering_mode":
        try:
            return _tool_result(explain_mode(root, arguments.get("mode")))
        except (ValueError, OSError) as exc:
            return _tool_error(str(exc))
    if name == "aimes_project_state":
        try:
            return _tool_result(show_project_state(root))
        except (ValueError, OSError) as exc:
            return _tool_error(str(exc))
    if name == "aimes_detect_engineering_mode":
        task_text = arguments.get("task_text")
        if not isinstance(task_text, str) or not task_text.strip():
            return _tool_error("task_text must be a non-empty string.")
        try:
            return _tool_result(detect_mode(task_text, load_mode_registry(root)))
        except (ValueError, OSError) as exc:
            return _tool_error(str(exc))
    if name == "aimes_set_project_state":
        mode = arguments.get("mode")
        if mode is not None and "source" not in arguments:
            return _tool_error("source is required when setting an engineering mode; use user, ai or import.")
        try:
            return _tool_result(set_project_state(
                root, lifecycle=arguments.get("lifecycle"), mode=mode,
                phase=arguments.get("phase"), task=arguments.get("task"),
                source=arguments.get("source", "user"),
                confidence=arguments.get("confidence"),
            ))
        except (ValueError, OSError) as exc:
            return _tool_error(str(exc))
    if name == "aimes_skill_route":
        if not registry.is_file():
            return _tool_error(f"Skill registry not found: {registry}. Run `aimes init` in this project first.")
        top = int(arguments.get("top", 3))
        if not isinstance(arguments.get("task_text"), str) or not arguments["task_text"].strip():
            return _tool_error("task_text must be a non-empty string.")
        return _tool_result(route_skills(registry, arguments["task_text"], top))
    if name == "aimes_read_skill":
        if not registry.is_file():
            return _tool_error(f"Skill registry not found: {registry}. Run `aimes init` in this project first.")
        try:
            skill_doc = load_skill_body(root, registry, str(arguments.get("skill_name", "")))
        except (ValueError, FileNotFoundError) as exc:
            return _tool_error(str(exc))
        return _tool_result({"file": skill_doc["path"], "registry_entry": skill_doc["skill"], "content": skill_doc["content"]})
    if name == "aimes_validate_delivery":
        report_text = arguments.get("report_text")
        if not isinstance(report_text, str) or not report_text.strip():
            return _tool_error("report_text must be a non-empty string.")
        return _tool_result(validate_delivery_text(report_text, "mcp:aimes_validate_delivery", root))
    raise ValueError(f"Unknown tool: {name}")


def handle_request(root: Path, message: dict[str, Any]) -> dict[str, Any] | None:
    method = message.get("method")
    msg_id = message.get("id")
    params = message.get("params") or {}
    if method == "initialize":
        return {
            "jsonrpc": "2.0", "id": msg_id,
            "result": {
                "protocolVersion": PROTOCOL_VERSION,
                "capabilities": {"tools": {}},
                "serverInfo": {"name": SERVER_NAME, "version": __version__},
                "instructions": "AIMES governance routing for this project. At task start call aimes_project_state and aimes_session_show with a stable per-tool session_id; after selecting an engineering mode call aimes_explain_engineering_mode to inspect the Skill/workflow/quality route; use aimes_task_start/update to track each task independently, and call aimes_assess_project_lifecycle when lifecycle is unknown; infer the current engineering mode from the live user request (the CLI/MCP cannot inspect conversation content), use aimes_detect_engineering_mode only as a deterministic hint, ask the user when ambiguous, and persist only approved or sufficiently confident (medium/high) state with aimes_set_project_state; never persist low-confidence guesses. Then call aimes_skill_route before project-changing work, read routed SKILL.md with aimes_read_skill, and validate delivery reports with aimes_validate_delivery.",
            },
        }
    if method in ("notifications/initialized", "initialized"):
        return None
    if method == "ping":
        return {"jsonrpc": "2.0", "id": msg_id, "result": {}}
    if method == "tools/list":
        return {"jsonrpc": "2.0", "id": msg_id, "result": {"tools": TOOLS}}
    if method == "tools/call":
        try:
            result = call_tool(root, str(params.get("name")), params.get("arguments") or {})
        except ValueError as exc:
            return {"jsonrpc": "2.0", "id": msg_id, "error": {"code": -32602, "message": str(exc)}}
        return {"jsonrpc": "2.0", "id": msg_id, "result": result}
    if msg_id is not None:
        return {"jsonrpc": "2.0", "id": msg_id, "error": {"code": -32601, "message": f"Method not found: {method}"}}
    return None


def serve_stdio(root: Path, stdin=None, stdout=None) -> int:
    stdin = stdin or sys.stdin
    stdout = stdout or sys.stdout
    for line in stdin:
        line = line.strip()
        if not line:
            continue
        try:
            message = json.loads(line)
        except json.JSONDecodeError:
            response = {"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "Parse error"}}
            stdout.write(json.dumps(response, ensure_ascii=False) + "\n")
            stdout.flush()
            continue
        if not isinstance(message, dict):
            continue
        try:
            response = handle_request(root, message)
        except Exception as exc:  # a crashed server helps nobody; report as JSON-RPC error
            response = {"jsonrpc": "2.0", "id": message.get("id"), "error": {"code": -32603, "message": f"Internal error: {exc}"}}
        if response is not None:
            stdout.write(json.dumps(response, ensure_ascii=False) + "\n")
            stdout.flush()
    return 0
