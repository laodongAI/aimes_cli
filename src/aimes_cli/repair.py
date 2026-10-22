from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from .adapters import normalize_tools
from .core import CONFIG_REL, init_project, load_config, validate_project
from .docs_check import check_docs


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
    "RECORD_PATH_MISSING": {
        "title": "补齐任务或交接记录文件",
        "options": [{"id": "manual-review", "label": "核对 records 路径；确认格式后再从模板创建", "mode": "guided", "requires_approval": True}],
        "risk": "medium",
        "reason": "任务/交接文件格式取决于项目约定；不会自动创建空文件或猜测格式。",
    },
    "RECORD_PATH_ESCAPE": {
        "title": "修正越界的任务/交接路径",
        "options": [{"id": "manual-review", "label": "将 records 路径改为项目根目录内的相对路径", "mode": "guided", "requires_approval": True}],
        "risk": "high",
        "reason": "路径越界可能访问项目外文件；不会自动改写配置。",
    },
    "RECORD_PATH_INVALID": {
        "title": "修正任务/交接路径配置类型",
        "options": [{"id": "manual-review", "label": "检查 records.tasks / records.handoff 并改为相对路径字符串", "mode": "guided", "requires_approval": True}],
        "risk": "medium",
        "reason": "配置结构存在歧义，必须由项目维护者确认。",
    },
    "ENV_KEY_DUPLICATE": {
        "title": "消除 .env.example 重复变量定义",
        "options": [{"id": "manual-review", "label": "比较重复定义的值，确认后人工合并为唯一赋值", "mode": "guided", "requires_approval": True}],
        "risk": "medium",
        "reason": "重复变量可能具有不同默认值；不能自动删除任意一行。",
    },
    "PROPOSAL_PENDING": {
        "title": "审核待处理的候选修复文件",
        "options": [{"id": "manual-review", "label": "比较候选文件与原文件，批准后再显式应用", "mode": "guided", "requires_approval": True}],
        "risk": "medium",
        "reason": "候选文件不是已批准的修复；不会自动应用或删除。",
    },
    "GIT_UNTRACKED_FILE": {
        "title": "决定未跟踪文件的版本管理策略",
        "options": [{"id": "manual-review", "label": "确认文件适合共享后手动纳管，或确认属于本地产物后加入忽略规则", "mode": "guided", "requires_approval": True}],
        "risk": "medium",
        "reason": "无法仅凭文件名判断是否包含秘密或生成物；不会执行 git add 或改写 .gitignore。",
    },
    "BROKEN_LINK": {
        "title": "修复失效的 Markdown 本地链接",
        "options": [{"id": "manual-review", "label": "核对目标是否移动或链接拼写是否错误，再修正链接", "mode": "guided", "requires_approval": True}],
        "risk": "low",
        "reason": "链接目标可能已移动或有意删除；不会猜测替代目标。",
    },
    "LINK_PATH_ESCAPE": {
        "title": "修正指向项目外部的 Markdown 链接",
        "options": [{"id": "manual-review", "label": "将链接改为项目内目标或明确的外部 URL", "mode": "guided", "requires_approval": True}],
        "risk": "high",
        "reason": "本地链接逃逸项目边界；需人工确认目标与文档意图。",
    },
    "CORE_REFERENCE_MISSING": {
        "title": "补全薄规则入口的治理核心引用",
        "options": [{"id": "manual-review", "label": "按薄入口规范补充核心文档引用，并保留项目专属规则", "mode": "guided", "requires_approval": True}],
        "risk": "medium",
        "reason": "入口文件可能包含用户自定义指令；不会自动覆盖或重写整份文件。",
    },
    "ENTRY_TOO_LONG": {
        "title": "精简过长的工具规则入口",
        "options": [{"id": "manual-review", "label": "审阅重复内容，将通用规则移入治理核心并保留项目特有约束", "mode": "guided", "requires_approval": True}],
        "risk": "medium",
        "reason": "自动删减可能丢失项目约束，必须比较差异并人工批准。",
    },
}


def build_repair_plan(root: Path) -> dict[str, Any]:
    """Combine AIMES configuration checks with read-only project/document diagnostics."""
    root = root.resolve()
    validation = validate_project(root)
    documentation = check_docs(root)
    sources = [("project-validation", validation.get("findings", [])), ("docs-check", documentation.get("findings", []))]
    actions: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    for source, source_findings in sources:
        for finding in source_findings:
            code = finding.get("code", "UNKNOWN")
            path = finding.get("path", "")
            message = finding.get("message", "")
            identity = (code, path, message)
            if identity in seen:
                continue
            seen.add(identity)
            remediation = _REMEDIATION.get(code, {"title": "人工分析未分类问题", "options": [{"id": "manual-review", "label": "查看证据后制定修复方案", "mode": "manual", "requires_approval": True}], "risk": "unknown", "reason": "该诊断类型没有经过验证的自动修复器。"})
            action = {
                "issue_id": f"ISSUE-{len(actions) + 1:03d}", "source": source, "code": code,
                "level": finding.get("level", "warning"), "message": message, "title": remediation["title"],
                "risk": remediation["risk"], "reason": remediation["reason"], "options": remediation["options"],
                "auto_repair_available": any(option["mode"] == "safe-auto" for option in remediation["options"]),
            }
            if path:
                action["path"] = path
            if finding.get("line") is not None:
                action["line"] = finding["line"]
            actions.append(action)
    return {
        "ok": validation.get("ok", False) and documentation.get("ok", False),
        "root": str(root), "diagnosis": validation, "documentation_diagnosis": documentation,
        "issue_count": len(actions), "repair_actions": actions,
        "recommended_mode": "preview-then-apply" if actions else "no-action-needed",
        "safety_policy": {"default_is_preview": True, "user_modified_files_are_never_force_overwritten": True,
            "destructive_or_remote_actions_are_not_performed": True, "unknown_findings_require_manual_review": True,
            "documentation_and_git_findings_are_advisory_unless_a_deterministic_repair_is_proven": True},
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
