# AIMES Skill 编排协议 V1.0

## 1. 目标

按任务需要选择并排序 Skills，避免一次性加载所有完整 Skill，也避免只调用编码 Skill 而遗漏需求、影响、安全和验证环节。编排器是轻量调度规则，不取代用户授权或 AIMES Core。

## 2. 默认路由表

| 任务信号 | 默认调用顺序 | 可跳过条件 |
|---|---|---|
| 新项目/新会话/跨工具交接 | project-onboarding → 按任务选后续 Skill | 不可跳过接管中的基线与用户修改保护检查；若只问概念性问题且无仓库任务，可不接管仓库 |
| 新功能/模糊需求/需求变更 | project-onboarding（上下文未知时）→ requirement-cognition → project-knowledge-reuse → change-impact-analysis → architecture-contract-review（涉及架构/契约时）→ controlled-implementation（获批准后）→ requirement-driven-testing | 只读咨询可以不进入实施；架构审查仅在触及架构/公共契约/数据模型时必需 |
| Bug 修复 | project-onboarding（上下文未知时）→ requirement-cognition（预期行为不清时）→ project-knowledge-reuse → change-impact-analysis → controlled-implementation → requirement-driven-testing | 若需求明确且无架构/契约变化，可简化对应分析，但必须记录理由 |
| 重构/依赖升级 | project-onboarding → project-knowledge-reuse → change-impact-analysis → architecture-contract-review（跨边界/公共契约时）→ controlled-implementation（批准后）→ requirement-driven-testing | 纯只读影响评估不进入实施 |
| 纯测试设计/发布验证 | project-onboarding（上下文未知时）→ requirement-cognition（验收有歧义时）→ requirement-driven-testing | 不允许跳过批准需求来源与未执行状态披露 |
| 架构方案评审 | project-onboarding（上下文未知时）→ requirement-cognition（目标不清时）→ project-knowledge-reuse → change-impact-analysis → architecture-contract-review | 不进入编码，除非用户另行批准实施 |

## 3. 编排步骤

1. 识别任务意图、是否涉及仓库、是否要求写操作、风险等级和完成定义。
2. 确定项目根目录与当前工作区状态；上下文未知时先调用接管流程。
3. 先执行必要的需求/契约分析，识别阻断级未知和审批门禁。
4. 对需要实施的任务，完成知识复用和影响分析；按触发条件调用架构审查。
5. 只有批准和前置条件满足后，进入受控实施。
6. 实施后调用需求驱动测试，并同步追溯与交付报告。
7. 对每个被跳过的 Skill 记录原因；不能因为节省上下文而跳过硬门禁。

## 4. 并行规则

- 默认单写入者。需求分析、知识检索和架构审查可以并行只读，但需共享同一基线和引用来源。
- 多个工具同时写入必须使用隔离 worktree/分支，并明确集成责任人；不得在同一工作区并行写。
- 合并前重新检查基线、diff、契约和测试；旧的影响分析在基线变化后需要复核。

## 5. 终止/降级规则

- 关键需求、安全/权限、公共契约或不可逆操作审批缺失：停止受影响写操作。
- 可以继续不受影响的只读分析，并说明阻塞边界。
- 工具能力不足：采用人工提供证据/人工执行验证/标记 BLOCKED，不假装自动完成。
- 不以所有 Skill 都执行过作为质量标准；以触发规则、门禁和证据是否充分为标准。

## 6. 最小交接记录

任务/项目 ID、基线 commit、已调用 Skill 与版本、跳过原因、权威来源、事实/未知/冲突、受保护修改、审批状态、已执行检查及证据、未执行项、下一步。
