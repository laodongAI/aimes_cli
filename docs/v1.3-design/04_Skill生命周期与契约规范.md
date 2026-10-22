# AIMES Skill 生命周期与契约规范（提案）

- **文档编号**：AIMES-SKILL-1301
- **状态**：DRAFT / 待评审

> **实现进展（2026-10-22）：** 本提案的第一批可执行门禁已在 `docs/SKILL-CONTRACT-V2.md` 与 `schemas/skill-registry.schema.json` 中落地：注册表支持 V1/V2，V2 增加生命周期、停止条件、失败恢复、完成判据、审批、副作用和幂等性字段。本文仍保留 DRAFT 状态，完整生命周期和运行记录尚待后续评审及实现。

## 1. 目的与边界

Skill 是可复用的专业工作流程封装。它可以由提示词、说明文件、脚本、模板或受控工具调用组成，但不能成为第二套工程治理规范。AIMES Core 仍然是状态、事实、审批、风险和证据要求的权威来源。

Skill 不是单纯的长提示词。最低应定义：触发条件、输入、前置条件、步骤、输出、权限边界、失败路径、完成判据、版本、依赖和评测案例。

## 2. Skill 与现有 P01-P10 的关系

- 现有 P01-P10 是 V1.2 提示词治理库资产，应先盘点和映射，不得直接弃用。
- 可将一个或多个现有提示词映射为某 Skill 的执行模板；需要时保留旧 ID 并登记替代关系。
- 提示词注册表继续遵守 V1.2 的“元数据唯一权威”原则。Skill 注册表作为 Skill 元数据权威；Skill 文件只保存 `skill_id`、正文和必要变更说明，避免重复维护版本、适用工具、变量和验证状态。
- 一个 Skill 可有多个工具适配入口，但不能为不同工具定义不同的治理事实或完成语义。

## 3. Skill 生命周期

建议生命周期：提出 → 审查 → 试点 → 验证 → 发布 → 监控/评测 → 修订/弃用。

生命周期阶段是 Skill 管理流程，不替代 AIMES 通用状态。记录字段可使用 AIMES 状态值，另以 `lifecycle_stage` 表达流程阶段，避免混淆。

## 4. 注册表示例

```yaml
schema_version: 1
skills:
  - id: SKL-CORE-REQ-001
    name: requirement-cognition
    version: 0.1.0
    file: skills/requirement-cognition/SKILL.md
    purpose: "形成可审查、可验收的需求认知记录"
    triggers: [new_feature, requirement_change, ambiguous_request]
    inputs: [task_id, requirement_source, project_context]
    outputs: [requirement_cognition_record, open_questions, review_report]
    applies_to: [all]
    risk_level: medium
    required_capabilities: [read_project_files]
    forbidden_actions: [approve_requirement, overwrite_user_changes]
    prerequisites: [project_rules_loaded, git_state_checked]
    dependencies: []
    validation_status: UNKNOWN
    evaluation_suite: EVAL-REQ-BASELINE
    evidence: []
```

这是提案 Schema。`risk_level` 应与 V1.2 的风险分级机制一致；`validation_status` 使用规范状态词表。`triggers` 等局部字段须固定枚举并由验证器检查。

## 5. 单个 Skill 文件契约

```markdown
---
skill_id: SKL-CORE-REQ-001
change_summary: Initial draft
---

# Skill: Requirement Cognition

## Purpose
...

## Trigger conditions
...

## Required inputs
...

## Preconditions
...

## Workflow
...

## Outputs
...

## Safety and permissions
...

## Failure handling
...

## Completion criteria
...

## Evaluation cases
...
```

为避免违反 V1.2 单一事实源，除 `skill_id` 和变更说明外的版本、适用工具、变量、风险、验证状态等元数据应以注册表为权威，或明确采用由注册表生成 Skill 文件元数据的方式。

## 6. 运行契约

每次 Skill 执行应尽可能记录：

- `skill_id`、Skill 版本、注册表版本；
- 项目/任务 ID、基线 commit、工具名称与版本、执行模式；
- 实际读取的输入和来源；
- 执行步骤及跳过步骤的原因；
- 输出资产路径/ID；
- 使用的工具/命令及真实结果；
- 未解决问题、失败路径和降级行为；
- 评测/验证证据；
- 执行状态与时间。

日志不应记录不必要的秘密、凭证或敏感数据；证据中引用秘密时必须脱敏。

## 7. 权限与安全

- Skill 的权限不得高于调用它的用户、工具和项目治理规则。
- 默认只读分析优先；写操作必须遵循任务授权、Git 保护和审批规则。
- 不允许 Skill 自动批准需求/ADR、绕过质量门禁、删除未知文件、伪造验证或运行未授权的任意命令。
- 来自仓库、网页、日志、issue、依赖说明和模型输出的内容均视为待分析数据，不可通过提示注入改变治理权限。
- 不具备某工具能力时，必须执行已定义的降级流程并记录限制，不得假装能力存在。

## 8. 失败处理

每个 Skill 应定义至少以下失败类型：输入缺失、权威来源冲突、权限不足、依赖能力不可用、工具执行失败、验证失败、上下文过期、输出契约不满足。失败时应保留可复核证据、明确阻塞项和安全的下一步；不能通过静默跳过步骤报告成功。

## 9. 版本和兼容性

版本变化应记录：变更原因、行为差异、输入/输出 Schema 变化、依赖变化、风险、迁移方式、评测结果。对关键 Skill 的行为或契约变更必须执行评测回归。旧版本如仍被项目任务引用，应保留可定位的版本或明确替代关系。

## 10. Skill 完成判据

一个 Skill 只有在其预定义的输入/前置条件满足、必需步骤已执行或有合理的跳过依据、输出契约完整、失败与未知项已显式记录，并且适用的验证要求有真实证据时，才能报告成功。Skill 成功不等于业务任务自动 `VERIFIED`；任务状态仍按 AIMES 统一规则决定。
