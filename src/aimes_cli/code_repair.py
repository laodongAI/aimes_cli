from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPAIR_DIR = Path(".aimes/repairs")
ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,79}$")
DIFF_RE = re.compile(r"^diff --git a/(\S+) b/(\S+)$")
BLOCKED_PARTS = {".git", ".aimes", ".venv", "venv", "node_modules", "__pycache__"}
BLOCKED_SUFFIXES = {".pyc", ".pyo"}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _safe_relative(value: str) -> str:
    value = value.replace("\\", "/")
    if not value or value.startswith("/") or re.match(r"^[A-Za-z]:", value):
        raise ValueError(f"补丁包含绝对路径或空路径：{value!r}")
    raw_parts = value.split("/")
    if any(part in ("", ".", "..") for part in raw_parts):
        raise ValueError(f"补丁路径包含不安全片段：{value!r}")
    if any(part.lower() in BLOCKED_PARTS for part in raw_parts):
        raise ValueError(f"补丁不能修改治理元数据或依赖/运行目录：{value!r}")
    if Path(value).suffix.lower() in BLOCKED_SUFFIXES:
        raise ValueError(f"补丁不能修改编译缓存文件：{value!r}")
    if any(ord(ch) < 32 for ch in value):
        raise ValueError("补丁路径包含控制字符")
    return Path(*raw_parts).as_posix()


def _parse_patch(raw: str) -> list[str]:
    if not raw.strip():
        raise ValueError("补丁文件为空")
    if "\x00" in raw:
        raise ValueError("不接受包含 NUL 的补丁")
    touched: list[str] = []
    old_path: str | None = None
    new_path: str | None = None
    for line in raw.splitlines():
        if line.startswith("GIT binary patch") or line.startswith("Binary files "):
            raise ValueError("当前版本不接受二进制补丁")
        if line.startswith("rename from ") or line.startswith("rename to ") or line.startswith("copy from ") or line.startswith("copy to "):
            raise ValueError("当前版本不接受重命名/复制补丁")
        match = DIFF_RE.match(line)
        if match:
            left = _safe_relative(match.group(1))
            right = _safe_relative(match.group(2))
            if left != right:
                raise ValueError("当前版本仅接受同一路径的文件修改/新增，不接受重命名")
            touched.append(left)
        elif line.startswith("--- "):
            old_path = line[4:].split("\t", 1)[0]
            if old_path != "/dev/null" and old_path.startswith("a/"):
                old_path = _safe_relative(old_path[2:])
        elif line.startswith("+++ "):
            new_path = line[4:].split("\t", 1)[0]
            if new_path == "/dev/null":
                raise ValueError("当前版本不接受删除文件的补丁")
            if new_path.startswith("b/"):
                new_path = _safe_relative(new_path[2:])
            if old_path not in (None, "/dev/null") and new_path not in (None, "/dev/null") and old_path != new_path:
                raise ValueError("补丁中的旧路径和新路径不一致")
    if not touched:
        raise ValueError("没有找到有效的 git unified diff（需要 diff --git a/path b/path）")
    return sorted(set(touched))


def _within(root: Path, rel: str) -> Path:
    unresolved = root / rel
    cursor = root
    for part in Path(rel).parts:
        cursor = cursor / part
        if cursor.is_symlink():
            raise ValueError(f"目标路径包含符号链接：{rel}")
    candidate = unresolved.resolve()
    try:
        candidate.relative_to(root.resolve())
    except ValueError as exc:
        raise ValueError(f"目标路径越过项目根目录：{rel}") from exc
    return candidate


def _manifest_path(root: Path, repair_id: str) -> Path:
    if not ID_RE.fullmatch(repair_id):
        raise ValueError("修复 ID 仅允许字母、数字、点、下划线和连字符")
    return root / REPAIR_DIR / repair_id / "proposal.json"


def _load_manifest(root: Path, repair_id: str) -> tuple[dict[str, Any], Path]:
    manifest_path = _manifest_path(root, repair_id)
    if not manifest_path.is_file():
        raise ValueError(f"找不到修复提案：{repair_id}")
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"修复提案清单无法读取：{exc}") from exc
    return manifest, manifest_path.parent


def _git(root: Path, args: list[str]) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            ["git", *args], cwd=root, text=True, encoding="utf-8",
            errors="replace", capture_output=True, check=False, timeout=60,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ValueError(f"无法执行 Git 补丁检查：{exc}") from exc


def propose_patch(root: Path, patch_file: Path, *, repair_id: str, finding: str, rationale: str = "") -> dict[str, Any]:
    root = root.resolve()
    patch_file = patch_file.resolve()
    if not patch_file.is_file():
        raise ValueError(f"补丁文件不存在：{patch_file}")
    raw_bytes = patch_file.read_bytes()
    try:
        raw = raw_bytes.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError("补丁必须是 UTF-8 文本 unified diff") from exc
    touched = _parse_patch(raw)
    destination = root / REPAIR_DIR / repair_id
    manifest_path = destination / "proposal.json"
    if destination.exists():
        raise ValueError(f"修复提案目录已存在，拒绝覆盖：{destination}")
    preimages: dict[str, str | None] = {}
    for rel in touched:
        target = _within(root, rel)
        if target.is_symlink():
            raise ValueError(f"拒绝修改符号链接：{rel}")
        if target.exists() and not target.is_file():
            raise ValueError(f"目标不是普通文件：{rel}")
        preimages[rel] = _sha(target.read_bytes()) if target.is_file() else None

    check = _git(root, ["apply", "--check", "--", str(patch_file)])
    # Git may reject absolute patch arguments after -- depending on platform; retry with stdin.
    if check.returncode != 0:
        try:
            check = subprocess.run(
                ["git", "apply", "--check", "--"],
                cwd=root, input=raw, text=True, encoding="utf-8", errors="replace",
                capture_output=True, check=False, timeout=60,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise ValueError(f"无法预检补丁：{exc}") from exc
    if check.returncode != 0:
        raise ValueError("补丁预检失败，未创建提案：" + (check.stderr.strip() or check.stdout.strip() or "git apply --check failed"))

    destination.mkdir(parents=True, exist_ok=False)
    try:
        (destination / "change.patch").write_bytes(raw_bytes)
        manifest = {
            "schema_version": 1,
            "repair_id": repair_id,
            "status": "PROPOSED",
            "created_at": _now(),
            "finding": finding.strip(),
            "rationale": rationale.strip(),
            "patch_file": "change.patch",
            "patch_sha256": _sha(raw_bytes),
            "touched_paths": touched,
            "preimage_sha256": preimages,
            "backup_dir": "backup",
            "applied_sha256": {},
            "verification": None,
            "safety": {
                "explicit_apply_confirmation_required": True,
                "rejects_deletions_binary_and_renames": True,
                "does_not_run_shell_commands": True,
                "preimage_hashes_checked_before_apply": True,
            },
        }
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    except Exception:
        shutil.rmtree(destination, ignore_errors=True)
        raise
    return {
        "ok": True, "repair_id": repair_id, "status": "PROPOSED",
        "finding": finding, "rationale": rationale,
        "touched_paths": touched, "preimage_sha256": preimages,
        "patch_sha256": manifest["patch_sha256"],
        "apply_hint": f"aimes repair-code apply {repair_id} --root . --confirm APPLY-FIX",
        "note": "已保存修复提案，尚未修改业务文件。请先审阅 change.patch，再显式确认应用。",
    }


def apply_patch(root: Path, repair_id: str, *, confirm: str | None) -> dict[str, Any]:
    root = root.resolve()
    if (confirm or "").strip().casefold() != "apply-fix":
        raise ValueError("应用补丁必须显式确认：--confirm APPLY-FIX（不区分大小写）")
    manifest, folder = _load_manifest(root, repair_id)
    if manifest.get("status") != "PROPOSED":
        raise ValueError(f"提案状态为 {manifest.get('status')!r}，只有 PROPOSED 可以应用")
    patch_path = folder / manifest.get("patch_file", "change.patch")
    if not patch_path.is_file() or _sha(patch_path.read_bytes()) != manifest.get("patch_sha256"):
        raise ValueError("补丁文件缺失或哈希不匹配；拒绝应用")
    touched = manifest.get("touched_paths")
    preimages = manifest.get("preimage_sha256")
    if not isinstance(touched, list) or not touched or not isinstance(preimages, dict):
        raise ValueError("提案清单结构无效")
    for rel in touched:
        safe = _safe_relative(rel)
        target = _within(root, safe)
        if target.is_symlink() or (target.exists() and not target.is_file()):
            raise ValueError(f"目标路径已变成符号链接或非普通文件：{rel}")
        current = _sha(target.read_bytes()) if target.is_file() else None
        if current != preimages.get(rel):
            raise ValueError(f"目标文件在提案后发生变化，拒绝覆盖：{rel}")
    raw = patch_path.read_text(encoding="utf-8")
    check = subprocess.run(["git", "apply", "--check", "--"], cwd=root, input=raw, text=True, capture_output=True, check=False, timeout=60)
    if check.returncode != 0:
        raise ValueError("补丁应用前检查失败，未修改文件：" + (check.stderr.strip() or check.stdout.strip()))
    backup = folder / manifest.get("backup_dir", "backup")
    backup.mkdir(parents=True, exist_ok=False)
    try:
        for rel in touched:
            target = _within(root, rel)
            if target.is_file():
                backup_target = backup / rel
                backup_target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(target, backup_target)
        result = subprocess.run(
            ["git", "apply", "--"],
            cwd=root, input=raw, text=True, encoding="utf-8", errors="replace",
            capture_output=True, check=False, timeout=60,
        )
        if result.returncode != 0:
            raise ValueError("Git 应用补丁失败：" + (result.stderr.strip() or result.stdout.strip()))
        applied = {}
        for rel in touched:
            target = _within(root, rel)
            applied[rel] = _sha(target.read_bytes()) if target.is_file() else None
        manifest["status"] = "APPLIED"
        manifest["applied_at"] = _now()
        manifest["applied_sha256"] = applied
        manifest["apply_stdout"] = result.stdout[-4000:]
        manifest["apply_stderr"] = result.stderr[-4000:]
        _manifest_path(root, repair_id).write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    except Exception:
        # Restore only the paths touched by this proposal. Do not remove or overwrite a file whose
        # current state no longer matches the expected applied state after git apply failed.
        for rel in touched:
            target = _within(root, rel)
            backup_target = backup / rel
            if backup_target.is_file():
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(backup_target, target)
            elif not preimages.get(rel) and target.is_file():
                target.unlink()
        raise
    return {
        "ok": True, "repair_id": repair_id, "status": "APPLIED",
        "touched_paths": touched, "backup_dir": str(backup),
        "note": "补丁已应用并保存应用前备份。业务测试尚未运行；请执行 repair-code verify 记录验证结果。",
    }


def verify_patch(root: Path, repair_id: str, *, test_argv_json: str, timeout_seconds: int = 300) -> dict[str, Any]:
    root = root.resolve()
    manifest, _ = _load_manifest(root, repair_id)
    if manifest.get("status") != "APPLIED":
        raise ValueError("只有 APPLIED 状态的修复提案可以验证")
    try:
        argv = json.loads(test_argv_json)
    except json.JSONDecodeError as exc:
        raise ValueError(f"--test-argv-json 不是有效 JSON：{exc}") from exc
    if not isinstance(argv, list) or not argv or any(not isinstance(arg, str) for arg in argv):
        raise ValueError("--test-argv-json 必须是非空字符串数组，例如 '[\"python\",\"-m\",\"unittest\"]'")
    if timeout_seconds < 1 or timeout_seconds > 1800:
        raise ValueError("--timeout-seconds 必须在 1 到 1800 之间")
    try:
        result = subprocess.run(
            argv, cwd=root, text=True, encoding="utf-8", errors="replace",
            capture_output=True, check=False, timeout=timeout_seconds, shell=False,
        )
        record = {
            "status": "PASS" if result.returncode == 0 else "FAIL",
            "argv": argv, "returncode": result.returncode,
            "started_at": _now(), "stdout_tail": result.stdout[-12000:],
            "stderr_tail": result.stderr[-12000:], "timeout": False,
        }
    except OSError as exc:
        record = {
            "status": "FAIL", "argv": argv, "returncode": None,
            "started_at": _now(), "stdout_tail": "",
            "stderr_tail": str(exc)[-12000:], "timeout": False,
        }
    except subprocess.TimeoutExpired as exc:
        record = {
            "status": "FAIL", "argv": argv, "returncode": None,
            "started_at": _now(),
            "stdout_tail": str(exc.stdout or "")[-12000:],
            "stderr_tail": str(exc.stderr or "")[-12000:],
            "timeout": True,
        }
    manifest["verification"] = record
    manifest["status"] = "VERIFIED" if record["status"] == "PASS" else "VERIFICATION_FAILED"
    manifest["verified_at"] = _now()
    _manifest_path(root, repair_id).write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {"ok": record["status"] == "PASS", "repair_id": repair_id, **record,
            "note": "测试通过仅代表指定命令返回 0；请结合原始诊断与回归覆盖判断修复是否真正解决问题。失败时补丁仍保留，可进一步修复或在确认后回滚。"}


def rollback_patch(root: Path, repair_id: str, *, confirm: str | None) -> dict[str, Any]:
    root = root.resolve()
    if (confirm or "").strip().casefold() != "rollback-fix":
        raise ValueError("回滚补丁必须显式确认：--confirm ROLLBACK-FIX（不区分大小写）")
    manifest, folder = _load_manifest(root, repair_id)
    if manifest.get("status") not in {"APPLIED", "VERIFICATION_FAILED", "VERIFIED"}:
        raise ValueError(f"提案状态为 {manifest.get('status')!r}，不能回滚")
    backup = folder / manifest.get("backup_dir", "backup")
    applied = manifest.get("applied_sha256", {})
    restored, removed = [], []
    for rel in manifest.get("touched_paths", []):
        target = _within(root, _safe_relative(rel))
        current = _sha(target.read_bytes()) if target.is_file() else None
        if current != applied.get(rel):
            raise ValueError(f"文件在应用补丁后又发生变化，为保护新修改拒绝回滚：{rel}")
    for rel in manifest.get("touched_paths", []):
        target = _within(root, rel)
        backup_target = backup / rel
        if backup_target.is_file():
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(backup_target, target)
            restored.append(rel)
        elif target.is_file():
            target.unlink()
            removed.append(rel)
    manifest["status"] = "ROLLED_BACK"
    manifest["rolled_back_at"] = _now()
    manifest["rollback"] = {"restored_paths": restored, "removed_paths": removed}
    _manifest_path(root, repair_id).write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {"ok": True, "repair_id": repair_id, "status": "ROLLED_BACK", "restored_paths": restored, "removed_paths": removed,
            "note": "已恢复应用前备份；提案、补丁和验证记录仍保留用于审计。"}
