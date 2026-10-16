# AIMES 首批 Skills 目录与任务模板

- **文档编号**：AIMES-SKILLS-1301
- **状态**：DRAFT / 待评审

## 1. 建设顺序

第一批不建设大量分散 Skill，优先形成能覆盖需求理解、知识复用、变更安全和验证的闭环。P0 是试点必需能力，P1 在核心流程稳定后补充。

| ID（提案） | Skill | 优先级 | 核心职责 | 现有提示词映射候选 |
|---|---|---|---|---|
| SKL-CORE-ONB-001 | `project-onboarding` | P0 | 恢复项目目标、当前基线、规则、模块、测试和未知项 | P01 |
| SKL-CORE-REQ-001 | `requirement-cognition` | P0 | 需求目标、场景、事实/推断/未知、歧义和验收 | P09，结合 P01/P06 |
| SKL-CORE-REUSE-001 | `project-knowledge-reuse` | P0 | 搜索、比较、复用决策、迁移和验证 | P06，扩展知识资产流程 |
| SKL-CORE-IMPACT-001 | `change-impact-analysis` | P0 | 分析需求、模块、API、数据、测试和运维影响 | P06 |
| SKL-CORE-CONTRACT-001 | `architecture-contract-review` | P0 | 核验模块边界、接口契约、ADR 和兼容性 | P07/P10 |
| SKL-CORE-IMPL-001 | `controlled-implementation` | P0 | 最小变更、保护用户改动、受控执行 | P02 |
| SKL-CORE-TEST-001 | `requirement-driven-testing` | P0 | 独立生成验收、边界、异常和回归测试 | P02/P07（需新建主体） |
| SKL-CORE-REVIEW-001 | `independent-quality-review` | P1 | 独立审查正确性、安全、兼容性与测试质量 | P07 |
| SKL-CORE-KNOW-001 | `knowledge-curation` | P1 | 去重、来源核验、候选知识升级/弃用 | P03/P05（部分） |
| SKL-CORE-DELIVERY-001 | `evidence-based-delivery` | P1 | 验证证据、追溯同步、交接和交付报告 | P03/P05 |
| SKL-CORE-EVAL-001 | `skill-evaluation` | P1 | 固定案例评测、回归、失败分类 | 新建 |

以上 ID 与名称尚待正式注册。应先复用/映射 P01-P10，避免重复维护；映射完成后再决定旧提示词保留、合并或弃用。

## 2. Skill 最小模板

```markdown
---
skill_id: SKL-CORE-REQ-001
change_summary: Initial draft
---

# Skill: Requirement Cognition

## Purpose
要解决的问题和不负责的事项。

## Trigger conditions
什么任务类型触发，什么情况不触发。

## Required inputs
任务 ID、需求来源、项目上下文、基线 commit 等。

## Preconditions
规则已加载/读取，Git 状态已检查，权威资料可访问。

## Workflow
每一步的动作、依据、预期输出和分支条件。

## Output contract
输出文件/字段/ID/引用及其权威性。

## Safety and permissions
只读/写入权限、审批边界、用户修改保护。

## Failure handling
缺输入、冲突、工具不可用、验证失败时的处理。

## Completion criteria
可观察、可检查的完成条件。

## Evaluation cases
对应评测集 ID 和必过硬门禁。
```

## 3. 功能开发统一任务模板

```markdown
# AIMES 功能开发任务

- task_id: TASK-<PROJECT>-NNN
- risk_level: <按 V1.2 评估>
- base_commit: <实际 commit>
- requirement_refs: []
- acceptance_criteria: []

## 1. 业务目标
描述要解决的问题和期望结果。

## 2. 已确认事实
每项事实附权威来源；不要混入推断。

## 3. 待确认事项 / 冲突 / 假设
说明影响、责任人、是否阻塞写操作。

## 4. 项目资产检索
列出相关模块、代码、接口、ADR、测试、历史缺陷和检索范围。

## 5. 复用决策
REUSE / ADAPT / TRANSFER_PATTERN / DO_NOT_REUSE / NEED_MORE_EVIDENCE；说明差异、约束和证据。

## 6. 影响分析
需求、模块、API、数据、权限、安全、兼容、测试、部署和回滚。

## 7. 实施计划
最小变更、预期文件、依赖、风险和分步验收。

## 8. 验证计划
需求验收、边界/异常、契约、回归、静态检查、构建；标明不能运行的检查。

## 9. 交付证据
真实命令/结果、证据路径、diff、追溯更新、未解决项和下一步。
```

## 4. 首批 Skill 验收要求

- 每个 P0 Skill 有注册表条目和版本化文件；
- 明确输入/输出和完成判据；
- 至少有一个成功案例和一个失败/歧义案例；
- 不存在无授权的高风险动作；
- 规则入口/工具能力没有实测时标记 `UNKNOWN`；
- 所有声称的验证结果有可定位证据；
- 与现有 P01-P10 的映射关系已登记。
