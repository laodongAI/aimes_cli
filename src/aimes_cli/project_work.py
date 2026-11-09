from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import re
import subprocess
import tempfile
import uuid
from typing import Any

import yaml

from .project_state import read_project_state, load_mode_registry

TASKS_REL = Path(".aimes/tasks")
SESSIONS_REL = Path(".aimes/sessions")
TASK_STATUSES = {"active", "blocked", "completed", "cancelled"}
TASK_PHASES = {"analysis", "clarification", "design", "review", "implementation", "testing", "acceptance", "delivery"}
_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _safe(root: Path, relative: Path) -> Path:
    base = root.resolve()
    target = (base / relative).resolve()
    try:
        target.relative_to(base)
    except ValueError as exc:
        raise ValueError(f"Project work path escapes project root: {relative}") from exc
    return target


def _id(value: str, label: str) -> str:
    if not isinstance(value, str) or not _ID.fullmatch(value):
        raise ValueError(f"{label} must match {_ID.pattern}")
    return value


def _read(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise ValueError(f"Record not found: {path}")
    value = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(value, dict):
        raise ValueError(f"Record must be a YAML mapping: {path}")
    return value


def _validate_task_record(task: dict[str, Any], task_id: str) -> None:
    _id(task_id, "task_id")
    if type(task.get("schema_version")) is not int or task.get("schema_version") != 1:
        raise ValueError(f"Unsupported task schema version: {task_id}")
    if task.get("task_id") != task_id:
        raise ValueError(f"Task ID does not match record path: {task_id}")
    title = task.get("title")
    if not isinstance(title, str) or not title.strip() or len(title) > 500:
        raise ValueError(f"Invalid task title: {task_id}")
    status = task.get("status")
    if not isinstance(status, str) or status not in TASK_STATUSES:
        raise ValueError(f"Invalid task status: {task_id}")
    phase = task.get("phase")
    if not isinstance(phase, str) or phase not in TASK_PHASES:
        raise ValueError(f"Invalid task phase: {task_id}")
    _id(task.get("session_id"), "task session_id")
    mode = task.get("engineering_mode")
    if mode is not None and (not isinstance(mode, str) or not mode.strip()):
        raise ValueError(f"Invalid task engineering mode: {task_id}")


def _validate_session_record(session: dict[str, Any], session_id: str) -> None:
    if type(session.get("schema_version")) is not int or session.get("schema_version") != 1:
        raise ValueError(f"Unsupported session schema version: {session_id}")
    if session.get("session_id") != session_id:
        raise ValueError(f"Session ID does not match record path: {session_id}")
    task_id = session.get("current_task_id")
    if task_id is not None:
        _id(task_id, "current_task_id")


def _write(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_name = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent,
                                         prefix=".aimes-record-", suffix=".tmp", delete=False) as handle:
            temp_name = handle.name
            yaml.safe_dump(payload, handle, allow_unicode=True, sort_keys=False)
            handle.flush()
        Path(temp_name).replace(path)
    finally:
        if temp_name:
            Path(temp_name).unlink(missing_ok=True)


def start_task(root: Path, title: str, *, session_id: str = "default",
               mode: str | None = None, task_id: str | None = None) -> dict[str, Any]:
    root = root.resolve()
    if not isinstance(title, str) or not title.strip() or len(title.strip()) > 500:
        raise ValueError("Task title must contain 1 to 500 characters")
    session_id = _id(session_id, "session_id")
    task_id = _id(task_id or uuid.uuid4().hex[:12], "task_id")
    task_path = _safe(root, TASKS_REL / f"{task_id}.yaml")
    session_path = _safe(root, SESSIONS_REL / f"{session_id}.yaml")
    if mode is not None:
        if not isinstance(mode, str) or mode not in load_mode_registry(root):
            raise ValueError(f"Unknown engineering mode: {mode}")
    if task_path.exists():
        raise ValueError(f"Task already exists: {task_id}")
    if session_path.exists():
        session = _read(session_path)
        _validate_session_record(session, session_id)
    else:
        session = {"schema_version": 1, "session_id": session_id, "created_at": _now()}
    task = {
        "schema_version": 1, "task_id": task_id, "title": title.strip(),
        "status": "active", "phase": "analysis", "engineering_mode": mode,
        "session_id": session_id, "created_at": _now(), "updated_at": _now(),
    }
    session.update({"current_task_id": task_id, "updated_at": _now()})
    _write(task_path, task)
    try:
        _write(session_path, session)
    except OSError:
        task_path.unlink(missing_ok=True)
        raise
    return {"ok": True, "task": task, "session": session}


def update_task(root: Path, task_id: str, *, phase: str | None = None,
                status: str | None = None) -> dict[str, Any]:
    task_id = _id(task_id, "task_id")
    path = _safe(root, TASKS_REL / f"{task_id}.yaml")
    task = _read(path)
    _validate_task_record(task, task_id)
    if phase is None and status is None:
        raise ValueError("Specify phase or status")
    if phase is not None:
        if phase not in TASK_PHASES:
            raise ValueError(f"Invalid task phase: {phase}")
        task["phase"] = phase
    if status is not None:
        if status not in TASK_STATUSES:
            raise ValueError(f"Invalid task status: {status}")
        task["status"] = status
    task["updated_at"] = _now()
    _write(path, task)
    return {"ok": True, "task": task}


def show_task(root: Path, task_id: str) -> dict[str, Any]:
    task_id = _id(task_id, "task_id")
    task = _read(_safe(root, TASKS_REL / f"{task_id}.yaml"))
    if task.get("schema_version") != 1 or task.get("task_id") != task_id:
        raise ValueError(f"Invalid task record: {task_id}")
    return {"ok": True, "task": task}


def list_tasks(root: Path, *, session_id: str | None = None) -> dict[str, Any]:
    directory = _safe(root, TASKS_REL)
    if not directory.is_dir():
        return {"ok": True, "tasks": []}
    if session_id is not None:
        session_id = _id(session_id, "session_id")
    tasks = []
    for item_path in sorted(directory.glob("*.yaml")):
        path = _safe(root, TASKS_REL / item_path.name)
        task = _read(path)
        _validate_task_record(task, path.stem)
        if session_id is None or task.get("session_id") == session_id:
            tasks.append(task)
    return {"ok": True, "tasks": tasks}


def show_session(root: Path, session_id: str = "default") -> dict[str, Any]:
    session_id = _id(session_id, "session_id")
    session = _read(_safe(root, SESSIONS_REL / f"{session_id}.yaml"))
    _validate_session_record(session, session_id)
    task_id = session.get("current_task_id")
    current_task = show_task(root, task_id)["task"] if task_id else None
    return {"ok": True, "session": session, "current_task": current_task}


def bind_session_task(root: Path, session_id: str, task_id: str) -> dict[str, Any]:
    session_id = _id(session_id, "session_id")
    task_id = _id(task_id, "task_id")
    task = show_task(root, task_id)["task"]
    session_path = _safe(root, SESSIONS_REL / f"{session_id}.yaml")
    if session_path.exists():
        session = _read(session_path)
        if session.get("schema_version") != 1 or session.get("session_id") != session_id:
            raise ValueError(f"Invalid session record: {session_id}")
    else:
        session = {"schema_version": 1, "session_id": session_id, "created_at": _now()}
    session.update({"current_task_id": task_id, "updated_at": _now()})
    _write(session_path, session)
    return {"ok": True, "session": session, "current_task": task}


def assess_project_lifecycle(root: Path) -> dict[str, Any]:
    """Collect bounded, read-only repository evidence; return candidates, never mutate lifecycle."""
    root = root.resolve()
    if not root.is_dir():
        raise ValueError(f"Project root is not a directory: {root}")
    evidence: list[dict[str, str]] = []
    signals: dict[str, int] = {key: 0 for key in ("new", "planning", "design", "development", "testing", "release", "operation")}
    candidates = [
        ("README.md", "README.md"), ("pyproject.toml", "pyproject.toml"),
        ("package.json", "package.json"), ("Cargo.toml", "Cargo.toml"),
        ("go.mod", "go.mod"), ("pom.xml", "pom.xml"),
        ("src", "src"), ("app", "app"), ("backend", "backend"),
        ("frontend", "frontend"), ("web", "web"), ("server", "server"), ("client", "client"),
        ("docs/plan", "docs/plan"), ("docs/requirements", "docs/requirements"),
        ("docs/product", "docs/product"),
        ("docs/architecture", "docs/architecture"), ("docs/design", "docs/design"),
        ("tests", "tests"), ("test", "test"), ("pytest.ini", "pytest.ini"),
        ("Dockerfile", "Dockerfile"), (".github/workflows", ".github/workflows"),
        ("CHANGELOG.md", "CHANGELOG.md"), ("docs/release", "docs/release"),
        ("deploy", "deploy"), ("k8s", "k8s"), ("helm", "helm"),
    ]
    for relative, label in candidates:
        path = _safe(root, Path(relative))
        if path.exists():
            signal = None
            weight = 0
            if relative in {"README.md", "pyproject.toml", "package.json", "Cargo.toml", "go.mod", "pom.xml"}:
                signal, weight = "development", 1
            elif relative in {"src", "app", "backend", "frontend", "web", "server", "client"}:
                signal, weight = "development", 2
            elif relative in {"docs/plan", "docs/requirements", "docs/product"}:
                signal, weight = "planning", 2
            elif relative in {"docs/architecture", "docs/design"}:
                signal, weight = "design", 2
            elif relative in {"tests", "test", "pytest.ini"}:
                signal, weight = "testing", 2
            elif relative == ".github/workflows":
                signal, weight = "testing", 1
            elif relative in {"CHANGELOG.md", "docs/release"}:
                signal, weight = "release", 2
            elif relative in {"deploy", "k8s", "helm"}:
                signal, weight = "operation", 2
            item = {"source": label, "kind": "path_exists"}
            if signal:
                signals[signal] += weight
                item.update({"signal": signal, "weight": weight})
            evidence.append(item)
    git_dir = root / ".git"
    if git_dir.exists():
        evidence.append({"source": ".git", "kind": "git_repository"})
        try:
            completed = subprocess.run(["git", "-C", str(root), "log", "-1", "--format=%cI"],
                                       capture_output=True, text=True, timeout=3, check=False)
            if completed.returncode == 0 and completed.stdout.strip():
                evidence.append({"source": "git log -1", "kind": "commit_history",
                                 "detail": completed.stdout.strip(), "signal": "development", "weight": 1})
                signals["development"] += 1
        except (OSError, subprocess.TimeoutExpired):
            evidence.append({"source": "git log -1", "kind": "unavailable"})
        try:
            completed = subprocess.run(["git", "-C", str(root), "tag", "--list"],
                                       capture_output=True, text=True, timeout=3, check=False)
            tags = [line for line in completed.stdout.splitlines() if line.strip()]
            if completed.returncode == 0 and tags:
                evidence.append({"source": "git tags", "kind": "release_tags",
                                 "detail": ", ".join(tags[:5]), "signal": "release", "weight": 2})
                signals["release"] += 2
        except (OSError, subprocess.TimeoutExpired):
            evidence.append({"source": "git tags", "kind": "unavailable"})
    if not evidence:
        signals["new"] = 1
    ranked = sorted(signals.items(), key=lambda item: (-item[1], item[0]))
    positive = [(key, score) for key, score in ranked if score > 0]
    top_score = positive[0][1] if positive else 0
    top = [key for key, score in positive if score == top_score]
    confidence = "low"
    candidate = None
    if len(top) == 1 and top_score >= 3:
        candidate, confidence = top[0], "medium"
    elif len(top) > 1 or (top and top_score < 3):
        confidence = "low"
    return {
        "ok": True, "project_root": str(root), "current_lifecycle": read_project_state(root).get("project_lifecycle", "unknown"),
        "candidate": candidate, "confidence": confidence,
        "signals": signals, "evidence": evidence,
        "limitations": [
            "文件/目录存在只表示结构信号，不证明功能已完成或正在使用。",
            "本检查不读取源码正文、不执行项目命令、不联网，也不会自动修改项目生命周期。",
            "请结合项目负责人确认、任务记录、CI/发布结果和运行环境证据后再执行 aimes state set --lifecycle。",
        ],
    }
