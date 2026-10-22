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


def diagnose_command(root: Path, *, diagnostic_id: str, test_argv_json: str, timeout_seconds: int = 300) -> dict[str, Any]:
    root = root.resolve()
    if not ID_RE.fullmatch(diagnostic_id):
        raise ValueError("诊断 ID 仅允许字母、数字、点、下划线和连字符")
    try:
        argv = json.loads(test_argv_json)
    except json.JSONDecodeError as exc:
        raise ValueError(f"--test-argv-json 不是有效 JSON：{exc}") from exc
    if not isinstance(argv, list) or not argv or any(not isinstance(arg, str) for arg in argv):
        raise ValueError("--test-argv-json 必须是非空字符串数组，例如 '[\"python\",\"-m\",\"unittest\"]'")
    if timeout_seconds < 1 or timeout_seconds > 1800:
        raise ValueError("--timeout-seconds 必须在 1 到 1800 之间")

    directory = root / REPAIR_DIR / "diagnostics"
    report_path = directory / f"{diagnostic_id}.json"
    if report_path.exists():
        raise ValueError(f"诊断记录已存在，拒绝覆盖：{report_path}")
    started = _now()
    try:
        result = subprocess.run(
            argv, cwd=root, text=True, encoding="utf-8", errors="replace",
            capture_output=True, check=False, timeout=timeout_seconds, shell=False,
        )
        stdout, stderr = result.stdout, result.stderr
        returncode = result.returncode
        timed_out = False
        launch_error = None
    except subprocess.TimeoutExpired as exc:
        stdout, stderr = str(exc.stdout or ""), str(exc.stderr or "")
        returncode, timed_out, launch_error = None, True, None
    except OSError as exc:
        stdout, stderr = "", str(exc)
        returncode, timed_out, launch_error = None, False, str(exc)

    combined = (stderr + "\n" + stdout)[-50000:]
    rules = [
        ("DEPENDENCY_OR_IMPORT", ("ModuleNotFoundError", "ImportError", "Cannot find module", "Module not found"),
         "检查依赖是否安装、导入路径/包名是否正确，并核对项目声明的依赖清单。"),
        ("SYNTAX_ERROR", ("SyntaxError", "IndentationError", "Unexpected token", "SyntaxError:"),
         "先定位报告中的文件与行号，修复语法/缩进问题，再运行最小范围的语法检查。"),
        ("ASSERTION_FAILURE", ("AssertionError", "Assertion failed", "Expected", "expected"),
         "对比预期值与实际值，检查业务分支、测试数据、边界条件及最近变更；不要为了通过测试而随意放宽断言。"),
        ("TYPE_OR_INTERFACE_ERROR", ("TypeError", "AttributeError", "KeyError", "NullReferenceException", "undefined is not a function"),
         "检查输入类型、空值处理、调用方与被调用方的接口契约，以及缺失字段/属性的路径。"),
        ("TEST_DISCOVERY_OR_COLLECTION", ("collected 0 items", "no tests ran", "test collection", "Cannot find any tests"),
         "先检查测试发现规则、文件命名、测试路径和依赖导入；确认测试确实被执行，不能把未发现测试当作通过。"),
        ("TIMEOUT", (), "检查死循环、阻塞 I/O、外部服务等待和测试夹具清理；缩小测试范围并设置合理超时。"),
    ]
    if timed_out:
        code = "TIMEOUT"
        advice = next(item[2] for item in rules if item[0] == code)
    elif launch_error:
        code = "COMMAND_LAUNCH_FAILED"
        advice = "确认命令已安装、可从当前环境调用，并检查工作目录与虚拟环境。诊断命令未能启动。"
    elif returncode == 0:
        code = "NO_FAILURE_DETECTED"
        advice = "指定命令返回 0。若原始问题仍存在，请运行针对该问题的复现用例；本结果不代表整个项目已通过验收。"
    else:
        match = next((item for item in rules if item[0] != "TIMEOUT" and any(token.casefold() in combined.casefold() for token in item[1])), None)
        code = match[0] if match else "UNCLASSIFIED_FAILURE"
        advice = match[2] if match else "先检查完整输出中的首个根因错误和最早相关调用栈，再让编码工具提出最小补丁；不要只修复最后一条连带错误。"

    status = "PASS" if returncode == 0 else "FAIL"
    report = {
        "schema_version": 1,
        "diagnostic_id": diagnostic_id,
        "created_at": started,
        "root": str(root),
        "command_argv": argv,
        "status": status,
        "returncode": returncode,
        "timeout": timed_out,
        "launch_error": launch_error,
        "finding": {"code": code, "summary": advice},
        "recommendations": [
            {"id": "inspect-evidence", "label": "检查原始输出、失败用例和相关调用栈", "mode": "manual"},
            {"id": "propose-patch", "label": "让 AI 编码工具生成最小 unified diff，再通过 repair-code propose 创建提案", "mode": "guided"},
            {"id": "review-apply-verify", "label": "人工审阅补丁后显式应用，并运行针对性测试与回归测试", "mode": "approval-gated"},
        ] if status == "FAIL" else [
            {"id": "check-original-issue", "label": "确认本次命令覆盖了原始问题的复现路径", "mode": "manual"},
        ],
        "stdout_tail": stdout[-16000:],
        "stderr_tail": stderr[-16000:],
        "note": "这是基于命令退出码与常见错误特征的辅助诊断，不等同于根因已确认；命令通过不代表原始问题已解决或整个项目通过验收；没有自动修改业务代码。",
    }
    directory.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {"ok": status == "PASS", **report, "report_path": str(report_path)}


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


def inspect_patch(root: Path, repair_id: str) -> dict[str, Any]:
    """Return a read-only lifecycle snapshot, integrity checks, and safe next-step guidance."""
    root = root.resolve()
    manifest, folder = _load_manifest(root, repair_id)
    status = manifest.get("status", "UNKNOWN")
    issues: list[dict[str, str]] = []
    patch_path = folder / manifest.get("patch_file", "change.patch")
    patch_hash_ok = False
    if patch_path.is_file():
        patch_hash_ok = _sha(patch_path.read_bytes()) == manifest.get("patch_sha256")
        if not patch_hash_ok:
            issues.append({"code": "PATCH_HASH_MISMATCH", "path": str(patch_path), "message": "补丁内容与提案记录的 SHA-256 不一致。"})
    else:
        issues.append({"code": "PATCH_MISSING", "path": str(patch_path), "message": "提案补丁文件缺失。"})

    path_checks: list[dict[str, Any]] = []
    touched_paths = manifest.get("touched_paths", [])
    if not isinstance(touched_paths, list):
        raise ValueError("修复提案清单损坏：touched_paths 必须是数组")
    preimages = manifest.get("preimage_sha256", {})
    applied = manifest.get("applied_sha256", {})
    for raw_rel in touched_paths:
        if not isinstance(raw_rel, str):
            raise ValueError("修复提案清单损坏：目标路径必须是字符串")
        rel = _safe_relative(raw_rel)
        target = _within(root, rel)
        current_hash = _sha(target.read_bytes()) if target.is_file() else None
        expected = applied.get(rel) if status in {"APPLIED", "VERIFIED", "VERIFICATION_FAILED", "ROLLED_BACK"} else preimages.get(rel)
        matches = current_hash == expected
        entry = {
            "path": rel,
            "exists": target.is_file(),
            "expected_hash": expected,
            "current_hash": current_hash,
            "matches_expected": matches,
        }
        path_checks.append(entry)
        if status == "PROPOSED" and not matches:
            issues.append({"code": "PREIMAGE_CHANGED", "path": rel, "message": "提案创建后目标文件发生变化；应用前会拒绝覆盖。"})
        elif status in {"APPLIED", "VERIFIED", "VERIFICATION_FAILED"} and not matches:
            issues.append({"code": "POST_APPLY_CHANGED", "path": rel, "message": "补丁应用后目标文件再次变化；回滚会拒绝覆盖这些修改。"})
        elif status == "ROLLED_BACK" and not matches:
            # The expected hash here is the post-apply hash; changed state is expected after rollback.
            entry["matches_expected"] = None

    diagnostic = None
    finding = manifest.get("finding", "")
    if isinstance(finding, str) and ID_RE.fullmatch(finding):
        report_path = root / REPAIR_DIR / "diagnostics" / f"{finding}.json"
        if report_path.is_file():
            try:
                report = json.loads(report_path.read_text(encoding="utf-8"))
                diagnostic = {
                    "diagnostic_id": report.get("diagnostic_id", finding),
                    "status": report.get("status"),
                    "finding_code": (report.get("finding") or {}).get("code"),
                    "report_path": str(report_path),
                }
            except (OSError, json.JSONDecodeError):
                issues.append({"code": "DIAGNOSTIC_REPORT_INVALID", "path": str(report_path), "message": "关联诊断报告无法读取。"})
        else:
            diagnostic = {"diagnostic_id": finding, "status": "NOT_FOUND", "report_path": str(report_path)}

    actions = {
        "PROPOSED": [
            {"id": "review", "label": "人工审阅 change.patch 与 proposal.json", "command": None},
            {"id": "apply", "label": "确认审阅无误后应用补丁", "command": f"aimes repair-code apply {repair_id} --confirm APPLY-FIX"},
        ],
        "APPLIED": [
            {"id": "verify", "label": "运行针对性测试并记录结果", "command": f'aimes repair-code verify {repair_id} --test-argv-json \'["python","-m","unittest"]\''},
            {"id": "inspect", "label": "先检查变更与测试输出，再决定是否继续", "command": None},
        ],
        "VERIFICATION_FAILED": [
            {"id": "revise", "label": "根据失败证据生成新的最小补丁提案，或人工检查当前变更", "command": None},
            {"id": "rollback", "label": "如需撤销且文件未再变化，可回滚", "command": f"aimes repair-code rollback {repair_id} --confirm ROLLBACK-FIX"},
        ],
        "VERIFIED": [
            {"id": "acceptance", "label": "复跑原始失败用例与相关回归，并按任务验收标准确认", "command": None},
            {"id": "rollback", "label": "如确认需要撤销且文件未再变化，可回滚", "command": f"aimes repair-code rollback {repair_id} --confirm ROLLBACK-FIX"},
        ],
        "ROLLED_BACK": [
            {"id": "recheck", "label": "确认工作区已恢复，并保留本提案作为审计证据", "command": None},
        ],
    }
    if status not in actions:
        issues.append({"code": "UNKNOWN_STATUS", "path": str(folder / "proposal.json"), "message": f"未知提案状态：{status}"})
    return {
        "ok": not issues,
        "repair_id": repair_id,
        "status": status,
        "created_at": manifest.get("created_at"),
        "finding": finding,
        "rationale": manifest.get("rationale", ""),
        "patch_sha256": manifest.get("patch_sha256"),
        "patch_integrity_ok": patch_hash_ok,
        "touched_paths": path_checks,
        "issues": issues,
        "diagnostic": diagnostic,
        "verification": manifest.get("verification"),
        "rollback": manifest.get("rollback"),
        "next_actions": actions.get(status, []),
        "read_only": True,
        "note": "本命令只读取提案和工作区状态，不应用补丁、不执行测试、不回滚。VERIFIED 仅表示指定验证命令通过，不代表任务最终验收通过。",
    }


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
