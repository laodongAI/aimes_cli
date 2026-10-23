from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml

from . import __version__, GOVERNANCE_VERSION
from .core import CONFIG_REL, MANIFEST_REL, load_config, proposed_files, sha256_text


def audit_project_version(root: Path) -> dict[str, Any]:
    """Read-only audit of the project manifest version and every AIMES-managed file."""
    root = root.resolve()
    config_path = root / CONFIG_REL
    manifest_path = root / MANIFEST_REL
    findings: list[dict[str, str]] = []
    current_files: list[str] = []
    outdated_files: list[str] = []
    modified_files: list[str] = []
    missing_files: list[str] = []
    unreadable_files: list[str] = []
    extra_managed_files: list[str] = []
    manifest_hash_mismatch_files: list[str] = []

    def finding(level: str, code: str, message: str) -> None:
        findings.append({"level": level, "code": code, "message": message})

    if not config_path.is_file():
        finding("warning", "AIMES_NOT_INITIALIZED", "当前目录未找到 .aimes/config.yaml，项目尚未初始化 AIMES。")
        return {
            "ok": False, "root": str(root), "status": "NOT_INITIALIZED",
            "installed_cli_version": __version__, "project_cli_version": None,
            "governance_version": GOVERNANCE_VERSION, "summary": {"current": 0, "outdated": 0, "modified": 0, "missing": 0, "unreadable": 0, "extra": 0},
            "current_files": [], "outdated_files": [], "modified_files": [], "missing_files": [],
            "unreadable_files": [], "extra_managed_files": [], "manifest_hash_mismatch_files": [],
            "findings": findings, "message": "请在项目根目录初始化 AIMES，或使用 --root 指定正确的项目目录。",
        }

    try:
        config = load_config(root)
        if config is None:
            raise ValueError("AIMES config missing")
        tools = [item.get("id") for item in config.get("tools", []) if isinstance(item, dict) and item.get("id")]
        scope = config.get("project", {}).get("scope", "project")
    except (OSError, ValueError, TypeError, AttributeError, yaml.YAMLError) as exc:
        finding("error", "AIMES_CONFIG_INVALID", f"无法解析 AIMES 配置：{exc}")
        return {
            "ok": False, "root": str(root), "status": "CONFIG_INVALID",
            "installed_cli_version": __version__, "project_cli_version": None,
            "governance_version": GOVERNANCE_VERSION, "summary": {"current": 0, "outdated": 0, "modified": 0, "missing": 0, "unreadable": 0, "extra": 0},
            "current_files": [], "outdated_files": [], "modified_files": [], "missing_files": [],
            "unreadable_files": [], "extra_managed_files": [], "manifest_hash_mismatch_files": [],
            "findings": findings, "message": "配置无法解析；版本一致性无法可靠判定。",
        }

    if not manifest_path.is_file():
        manifest = None
        old_hashes: dict[str, str] = {}
        project_version = None
        finding("error", "AIMES_MANIFEST_MISSING", "缺少 .aimes/manifest.json，无法证明项目文件的 AIMES 管理基线。")
    else:
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            if not isinstance(manifest, dict) or not isinstance(manifest.get("managed_files"), list):
                raise ValueError("manifest must contain a managed_files list")
            project_version = str(manifest.get("aimes_cli_version", "unknown"))
            old_hashes = {}
            for item in manifest["managed_files"]:
                if not isinstance(item, dict) or not isinstance(item.get("path"), str) or not isinstance(item.get("sha256"), str):
                    continue
                rel = item["path"].replace(chr(92), "/")
                candidate = Path(rel)
                try:
                    if candidate.is_absolute() or ".." in candidate.parts:
                        raise ValueError("managed file path escapes project root")
                    (root / candidate).resolve().relative_to(root)
                except (OSError, ValueError):
                    finding("error", "AIMES_MANIFEST_PATH_UNSAFE", f"Manifest 包含越界管理路径，已跳过：{rel}")
                    continue
                old_hashes[rel] = item["sha256"]
        except (OSError, UnicodeError, ValueError, TypeError, KeyError) as exc:
            manifest = None
            old_hashes = {}
            project_version = None
            finding("error", "AIMES_MANIFEST_INVALID", f"Manifest 无效，无法建立可靠的逐文件基线：{exc}")

    try:
        expected = {path: content for path, content in proposed_files(root, tools, scope).items() if path != MANIFEST_REL.as_posix()}
    except (OSError, ValueError, TypeError, KeyError, yaml.YAMLError) as exc:
        finding("error", "AIMES_TEMPLATE_READ_FAILED", f"无法读取当前 CLI 模板：{exc}")
        return {
            "ok": False, "root": str(root), "status": "AUDIT_BLOCKED",
            "installed_cli_version": __version__, "project_cli_version": project_version,
            "governance_version": GOVERNANCE_VERSION, "summary": {"current": 0, "outdated": 0, "modified": 0, "missing": 0, "unreadable": 0, "extra": 0},
            "current_files": [], "outdated_files": [], "modified_files": [], "missing_files": [],
            "unreadable_files": [], "extra_managed_files": [], "manifest_hash_mismatch_files": [],
            "findings": findings, "message": "当前模板无法读取；未对项目文件做任何修改。",
        }

    expected_paths = set(expected)
    managed_paths = set(old_hashes)
    for rel, expected_content in sorted(expected.items()):
        target = root / rel
        if not target.is_file():
            missing_files.append(rel)
            finding("error", "AIMES_FILE_MISSING", f"当前版本需要的管理文件缺失：{rel}")
            continue
        try:
            actual = target.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            unreadable_files.append(rel)
            finding("error", "AIMES_FILE_UNREADABLE", f"无法读取管理文件 {rel}：{exc}")
            continue
        actual_hash = sha256_text(actual)
        if actual == expected_content:
            current_files.append(rel)
            if rel in old_hashes and old_hashes[rel] != actual_hash:
                manifest_hash_mismatch_files.append(rel)
                finding("warning", "AIMES_MANIFEST_HASH_STALE", f"文件内容与当前模板一致，但 Manifest 中的哈希不一致：{rel}")
        elif rel in old_hashes and actual_hash == old_hashes[rel]:
            outdated_files.append(rel)
            finding("warning", "AIMES_FILE_OUTDATED", f"文件仍匹配旧 Manifest，但与当前 CLI 模板不同：{rel}")
        else:
            modified_files.append(rel)
            finding("warning", "AIMES_FILE_CUSTOMIZED", f"文件与当前模板不同，且无法由旧 Manifest 证明为未修改；可能包含用户自定义内容：{rel}")

    for rel in sorted(managed_paths - expected_paths):
        target = root / rel
        if not target.is_file():
            missing_files.append(rel)
            finding("warning", "AIMES_LEGACY_FILE_MISSING", f"旧 Manifest 中记录的管理文件缺失：{rel}")
            continue
        try:
            actual_hash = sha256_text(target.read_text(encoding="utf-8"))
        except (OSError, UnicodeError) as exc:
            unreadable_files.append(rel)
            finding("warning", "AIMES_LEGACY_FILE_UNREADABLE", f"无法读取旧管理文件 {rel}：{exc}")
            continue
        if actual_hash == old_hashes[rel]:
            extra_managed_files.append(rel)
            finding("warning", "AIMES_LEGACY_FILE", f"文件仍由旧 Manifest 管理，但不属于当前配置生成的文件集合；不会自动删除：{rel}")
        else:
            modified_files.append(rel)
            finding("warning", "AIMES_LEGACY_FILE_CUSTOMIZED", f"旧管理文件不属于当前模板集合且内容已变化；保留供人工审查：{rel}")

    version_matches = project_version == __version__
    if project_version is None:
        status = "MANIFEST_INVALID" if manifest_path.exists() else "INCOMPLETE"
    elif missing_files or unreadable_files:
        status = "INCOMPLETE"
    elif modified_files:
        status = "CUSTOMIZED"
    elif outdated_files or extra_managed_files or manifest_hash_mismatch_files or not version_matches:
        status = "UPDATE_AVAILABLE"
    else:
        status = "CURRENT"

    if any(item["level"] == "error" and item["code"].startswith("AIMES_MANIFEST") for item in findings):
        status = "MANIFEST_INVALID"
    if project_version is not None and not version_matches:
        finding("warning", "AIMES_VERSION_MISMATCH", f"项目 Manifest 版本 {project_version}，当前 CLI 版本 {__version__}。")
    if status == "CURRENT":
        message = "Manifest 版本与当前 CLI 一致，所有当前版本管理文件均与模板匹配。"
    elif status == "CUSTOMIZED":
        message = "检测到自定义或已修改的 AIMES 管理文件。它们不会被自动覆盖；请结合升级计划逐项审查。"
    elif status == "UPDATE_AVAILABLE":
        message = "项目 AIMES 版本或部分管理文件与当前 CLI 模板不一致。请先运行 aimes upgrade --dry-run；本审计未修改任何文件。"
    else:
        message = "项目 AIMES 文件不完整或审计受阻。请检查 findings；本审计未修改任何文件。"

    return {
        "ok": status == "CURRENT", "root": str(root), "status": status,
        "installed_cli_version": __version__, "project_cli_version": project_version,
        "governance_version": GOVERNANCE_VERSION, "summary": {
            "current": len(current_files), "outdated": len(outdated_files), "modified": len(modified_files),
            "missing": len(missing_files), "unreadable": len(unreadable_files), "extra": len(extra_managed_files),
            "manifest_hash_mismatch": len(manifest_hash_mismatch_files), "expected": len(expected),
        },
        "current_files": current_files, "outdated_files": outdated_files, "modified_files": modified_files,
        "missing_files": missing_files, "unreadable_files": unreadable_files,
        "extra_managed_files": extra_managed_files, "manifest_hash_mismatch_files": manifest_hash_mismatch_files,
        "findings": findings, "message": message,
        "note": "只读审计；模板一致性不代表 AI 工具运行时已加载或遵循这些规则。",
    }
