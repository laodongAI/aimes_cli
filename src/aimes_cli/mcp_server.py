from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from . import __version__
from .delivery_report import validate_delivery_text
from .skill_route import load_skill_body, route_skills

PROTOCOL_VERSION = "2024-11-05"
SERVER_NAME = "aimes-governance"

TOOLS = [
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
                "instructions": "AIMES governance routing for this project. Call aimes_skill_route before project-changing work, read the routed SKILL.md with aimes_read_skill, and validate delivery reports with aimes_validate_delivery.",
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
