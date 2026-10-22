from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from .adapters import normalize_tools
from .core import CONFIG_REL, init_project, load_config, validate_project


_REMEDIATION = {
    "CONFIG_MISSING": {
        "title": "初始化 AIMES 项目配置",
        "options": [
            {"id": "init", "label": "根据指定工具生成配置与规则入口", "mode": "safe-auto", "requires_approval": True}
        ],
        "risk": "medium",
        "reason": "缺少项目配置，无法可靠推断应启用哪些工具适配器。",
    },
    "CONFIG_INVALID": {
        "title": "修复无效的 AIMES 配置",
        "options": [
            {"id": "manual-review", "label": "备份并人工修正 YAML/配置结构", "mode": "guided", "requires_approval": True}
        ],
        "risk": "high",
        "reason": "自动重建可能丢失项目自定义配置；当前只提供指导，不自动覆盖。",
    },
    "SCHEMA_UNSUPPORTED": {
        "title": "迁移配置 Schema 版本",
        "options": [
            {"id": "upgrade-preview", "label": "先运行 aimes upgrade 预览迁移方案", "mode": "guided", "requires_approval": True}
        ],
        "risk": "medium",
        "reason": "版本迁移可能改变配置语义，必须先预览差异。",
    },
    "CORE_PATH_MISSING": {
        "title": "补全治理核心路径",
        "options": [
            {"id": "regenerate-managed", "label": "根据现有配置重新生成 AIMES 管理文件", "mode": "safe-auto", "requires_approval": True}
        ],
        "risk": "medium",
        "reason": "修复需要写入治理文件；用户已有文件将按安全合并规则保留。",
    },
    "CORE_NOT_FOUND": {
        "title": "恢复缺失的治理核心文件",
        "options": [
            {"id": "regenerate-managed", "label": "从当前 AIMES 包内模板重新生成缺失文件", "mode": "safe-auto", "requires_approval": True}
        ],
        "risk": "low",
        "reason": "只补齐缺失文件；已有且无法证明未被修改的文件不会被覆盖。",
    },
    "ENTRY_MISSING": {
        "title": "恢复缺失的工具规则入口",
        "options": [
            {"id": "regenerate-managed", "label": "按当前适配器配置重新生成入口文件", "mode": "safe-auto", "requires_approval": True}
        ],
        "risk": "low",
        "reason": "只补齐缺失入口；已存在的自定义入口不会被覆盖。",
    },
    "MANIFEST_MISSING": {
        "title": "重建 AIMES 文件清单",
        "options": [
            {"id": "regenerate-managed", "label": "重新生成可确认归属的管理文件清单", "mode": "safe-auto", "requires_approval": True}
        ],
        "risk": "medium",
        "reason": "缺少清单时无法自动判定既有文件是否由 AIMES 管理；冲突文件将被保留。",
    },
    "MANIFEST_INVALID": {
        "title": "修复无效的文件清单",
        "options": [
            {"id": "manual-review", "label": "先备份损坏清单，再人工检查或移走后重新生成", "mode": "guided", "requires_approval": True}
        ],
        "risk": "high",
        "reason": "损坏清单可能包含重要的文件归属信息；不会自动覆盖。",
    },
    "MANAGED_FILE_MISSING": {
        "title": "恢复缺失的 AIMES 管理文件",
        "options": [
            {"id": "regenerate-managed", "label": "重新生成缺失的管理文件", "mode": "safe-auto", "requires_approval": True}
        ],
        "risk": "low",
        "reason": "只补齐缺失文件，不删除其他文件。",
    },
    "MANAGED_FILE_CHANGED": {
        "title": "处理与清单不一致的文件",
        "options": [
            {"id": "keep-user-edit", "label": "保留现有修改并复核差异", "mode": "manual", "requires_approval": False},
            {"id": "propose-template", "label": "生成独立候选文件供比较，不覆盖原文件", "mode": "guided", "requires_approval": True},
        ],
        "risk": "high",
        "reason": "文件变化可能是用户有意修改，不能直接重置或覆盖。",
    },
    "TOOL_UNKNOWN": {
        "title": "处理未知的工具适配器",
        "options": [
            {"id": "manual-review", "label": "确认工具 ID 并按受支持的适配器重新配置", "mode": "manual", "requires_approval": True}
        ],
        "risk": "high",
        "reason": "不能猜测未知工具的规则加载路径或能力。",
    },
    "TOOLS_INVALID": {
        "title": "修复工具适配器列表",
        "options": [
            {"id": "manual-review", "label": "核对 .aimes/config.yaml 中 tools 的结构", "mode": "manual", "requires_approval": True}
        ],
        "risk": "high",
        "reason": "自动补全可能误启用或移除适配器。",
    },
    "ADAPTER_MANUAL": {
        "title": "验证手动适配器",
        "options": [
            {"id": "runtime-probe", "label": "核实工具原生规则入口并运行隔离加载探针", "mode": "guided", "requires_approval": False}
        ],
        "risk": "low",
        "reason": "这是能力验证任务，不是简单配置缺失；不能仅靠写文件标记为已验证。",
    },
}


def build_repair_plan(root: Path) -> dict[str, Any]:
    root = root.resolve()
    validation = validate_project(root)
    findings = validation.get("findings", [])
    actions = []
    for index, finding in enumerate(findings, start=1):
        code = finding.get("code", "UNKNOWN")
        remediation = _REMEDIATION.get(code, {
            "title": "人工分析未分类问题",
            "options": [{"id": "manual-review", "label": "查看证据后制定修复方案", "mode": "manual", "requires_approval": True}],
            "risk": "unknown",
            "reason": "该诊断类型没有经过验证的自动修复器。",
        })
        actions.append({
            "issue_id": f"ISSUE-{index:03d}",
            "code": code,
            "level": finding.get("level", "warning"),
            "message": finding.get("message", ""),
            "title": remediation["title"],
            "risk": remediation["risk"],
            "reason": remediation["reason"],
            "options": remediation["options"],
            "auto_repair_available": any(option["mode"] == "safe-auto" for option in remediation["options"]),
        })
    return {
        "ok": validation.get("ok", False),
        "root": str(root),
        "diagnosis": validation,
        "issue_count": len(actions),
        "repair_actions": actions,
        "recommended_mode": "preview-then-apply" if actions else "no-action-needed",
        "safety_policy": {
            "default_is_preview": True,
            "user_modified_files_are_never_force_overwritten": True,
            "destructive_or_remote_actions_are_not_performed": True,
            "unknown_findings_require_manual_review": True,
        },
    }


def apply_safe_repairs(root: Path, *, confirm: str | None, tools: str | None = None) -> dict[str, Any]:
    root = root.resolve()
    if (confirm or "").strip().casefold() != "repair":
        raise ValueError("执行修复必须显式确认：--apply --confirm REPAIR（不区分大小写）")

    config_path = root / CONFIG_REL
    preflight = validate_project(root)
    blocking_codes = {"CONFIG_INVALID", "SCHEMA_UNSUPPORTED", "TOOLS_INVALID", "MANIFEST_INVALID"}
    blocked = sorted({item.get("code") for item in preflight.get("findings", []) if item.get("code") in blocking_codes})
    if blocked:
        raise ValueError(
            "检测到不能安全自动修复的配置/清单问题：" + ", ".join(blocked)
            + "。请先备份并人工处理；本次未执行任何写入。"
        )
    selected_tools: list[str] = []
    scope = "project"
    if config_path.is_file():
        try:
            config = load_config(root)
        except Exception as exc:
            raise ValueError(f"配置文件无法安全解析，未执行修复：{exc}") from exc
        raw_tools = config.get("tools", [])
        if not isinstance(raw_tools, list):
            raise ValueError("配置中的 tools 不是列表；请先人工修复配置，未执行任何写入")
        ids = [item.get("id") for item in raw_tools if isinstance(item, dict) and item.get("id")]
        if tools:
            ids.extend(normalize_tools(tools))
        selected_tools = list(dict.fromkeys(normalize_tools(ids))) if ids else []
        project_config = config.get("project", {})
        scope = project_config.get("scope", "project") if isinstance(project_config, dict) else "project"
    elif tools:
        selected_tools = normalize_tools(tools)
    else:
        raise ValueError("项目缺少 .aimes/config.yaml；请提供 --tools 指定需要配置的适配器，例如 --tools codex-cli")

    if not selected_tools:
        raise ValueError("未找到可安全复用的工具适配器；请通过 --tools 明确指定，未执行任何写入")

    before = build_repair_plan(root)
    result = init_project(root, selected_tools, scope=scope, dry_run=False)
    after = build_repair_plan(root)
    remaining = list(after["repair_actions"])
    # A conflict is still an unresolved remediation item even if safe merge removes the file from
    # the managed manifest and the next ordinary validation no longer reports its old hash.
    for index, conflict in enumerate(result.get("conflicts", []), start=1):
        remaining.append({
            "issue_id": f"REPAIR-CONFLICT-{index:03d}",
            "code": "REPAIR_CONFLICT_PRESERVED",
            "level": "warning",
            "message": f"Preserved existing file due to ownership/content conflict: {conflict.get('path')}",
            "title": "复核被保留的现有文件",
            "risk": "high",
            "reason": "文件可能包含用户自定义内容；AIMES 未覆盖它。",
            "options": [{"id": "review-diff", "label": "比较原文件与候选文件后人工决定", "mode": "manual", "requires_approval": True}],
            "auto_repair_available": False,
        })
    before_codes = {item["code"] for item in before["repair_actions"]}
    remaining_codes = {item["code"] for item in remaining}
    resolved = sorted(before_codes - remaining_codes)
    return {
        "ok": not remaining and result.get("ok", False),
        "root": str(root),
        "mode": "safe-auto-repair",
        "selected_tools": selected_tools,
        "before_issue_count": before["issue_count"],
        "resolved_issue_codes": resolved,
        "remaining_issue_count": len(remaining),
        "remaining_actions": remaining,
        "write_result": result,
        "note": "已重新诊断。只对 AIMES 能够安全管理的文件应用常规初始化/合并规则；不覆盖用户修改，不删除文件，不执行远端操作。冲突保留项仍视为未解决，需人工比较后处理。",
    }
