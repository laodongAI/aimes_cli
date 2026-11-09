from __future__ import annotations

import sys
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from collections.abc import Iterable

from .adapters import ADAPTERS, ADAPTER_REGISTRY, normalize_tools


VERSION_TIMEOUT_SECONDS = 4
MAX_VERSION_OUTPUT = 500


def _probe_command(command: str, *, probe_version: bool) -> dict[str, Any]:
    executable = shutil.which(command)
    if not executable:
        return {
            "command": command,
            "available": False,
            "executable": None,
            "version": None,
            "version_status": "not_available",
        }

    result: dict[str, Any] = {
        "command": command,
        "available": True,
        "executable": str(Path(executable)),
        "version": None,
        "version_status": "not_probed",
    }
    # Only known CLI harnesses are queried with --version. An IDE launcher may
    # ignore unknown flags and open a GUI, so IDE/hosted launchers are discovery-only.
    if not probe_version:
        result["version_status"] = "skipped_non_cli"
        return result

    # Windows batch launchers require shell interpretation. Do not invoke them
    # through a shell: availability is still useful, but version stays unknown.
    if Path(executable).suffix.lower() in {".cmd", ".bat"}:
        result["version_status"] = "skipped_windows_script"
        return result

    try:
        completed = subprocess.run(
            [executable, "--version"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=VERSION_TIMEOUT_SECONDS,
            check=False,
        )
    except subprocess.TimeoutExpired:
        result["version_status"] = "timeout"
        return result
    except OSError as exc:
        result["version_status"] = "execution_error"
        result["version_error"] = str(exc)[:MAX_VERSION_OUTPUT]
        return result

    output = (completed.stdout or completed.stderr or "").strip()
    result["version_status"] = "reported" if completed.returncode == 0 and output else "unavailable"
    if output:
        result["version"] = output[:MAX_VERSION_OUTPUT]
    if completed.returncode != 0:
        result["version_exit_code"] = completed.returncode
    return result


def detect_adapters(tools: Iterable[str] | None = None) -> dict[str, Any]:
    """Read-only PATH and --version checks; never starts an interactive agent session."""
    selected = normalize_tools(list(tools)) if tools is not None else list(ADAPTERS)
    records = []
    for tool_id in selected:
        adapter = ADAPTERS[tool_id]
        commands = [_probe_command(command, probe_version=adapter.host_type == "cli") for command in adapter.detection_commands]
        if not adapter.detection_commands:
            availability = "not_detectable"
        elif any(item["available"] for item in commands):
            availability = "available"
        else:
            availability = "not_found"
        records.append({
            "id": tool_id,
            "name": adapter.label,
            "host": {"id": adapter.host_id, "type": adapter.host_type},
            "harness": {"id": adapter.harness_id},
            "availability": availability,
            "commands": commands,
            "capabilities": dict(adapter.capabilities),
        })

    return {
        "schema_version": 1,
        "ok": True,
        "detector": "aimes-read-only-runtime-detect",
        "registry_version": ADAPTER_REGISTRY.get("registry_version"),
        "detected_at": datetime.now(timezone.utc).isoformat(),
        "platform": sys.platform,
        "scope": "PATH executable discovery and optional --version output only; no agent session, feature, authentication, or runtime rule-loading verification",
        "adapters": records,
        "summary": {
            "available": sum(item["availability"] == "available" for item in records),
            "not_found": sum(item["availability"] == "not_found" for item in records),
            "not_detectable": sum(item["availability"] == "not_detectable" for item in records),
        },
    }
