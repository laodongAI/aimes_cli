# AIMES Skill 编排协议 V1.0

## 1. 目标

按任务需要选择并排序 Skills，避免一次性加载所有完整 Skill，也避免只调用编码 Skill 而遗漏需求、影响、安全和验证环节。编排器是轻量调度规则，不取代用户授权或 AIMES Core。

## 2. 默认路由表

| 任务信号 | 默认调用顺序 | 可跳过条件 |
|---|---|---|
| 新项目/新会话/跨工具交接 | project-onboarding → 按任务选后续 Skill | 不可跳过接管中的基线与用户修改保护检查；若只问概念性问题且无仓库任务，可不接管仓库 |
| 新功能/模糊需求/需求变更 | project-onboarding（上下文未知时）→ product-manager（目标/价值/范围分析）→ requirement-cognition → project-knowledge-reuse → change-impact-analysis → architecture-contract-review（涉及架构/契约时）→ controlled-implementation（获批准后）→ requirement-driven-testing | 只读咨询可以不进入实施；架构审查仅在触及架构/公共契约/数据模型时必需 |
| Bug 修复 | project-onboarding（上下文未知时）→ requirement-cognition（预期行为不清时）→ project-knowledge-reuse → change-impact-analysis → controlled-implementation → requirement-driven-testing | 若需求明确且无架构/契约变化，可简化对应分析，但必须记录理由 |
| 重构/依赖升级 | project-onboarding → project-knowledge-reuse → change-impact-analysis → architecture-contract-review（跨边界/公共契约时）→ controlled-implementation（批准后）→ requirement-driven-testing | 纯只读影响评估不进入实施 |
| 生成引导词/产品构想/需求探索 | project-onboarding → project-knowledge-reuse（按需）→ product-manager → requirement-cognition（需要形成可验收需求时）→ prompt-optimization（需要提示词表达优化时） | 明确只要引导词时输出完整可复制引导词，不自动编码；不得跳过项目知识分析 |
| 纯提示词改写（不涉及产品判断） | prompt-optimization | 仅改写已有提示词且目标/范围明确时可直接调用；需要决定做什么、为何做或如何复用项目知识时，先调用 product-manager |
| 纯测试设计/发布验证 | project-onboarding（上下文未知时）→ requirement-cognition（验收有歧义时）→ requirement-driven-testing | 不允许跳过批准需求来源与未执行状态披露 |
| 架构方案评审 | project-onboarding（上下文未知时）→ requirement-cognition（目标不清时）→ project-knowledge-reuse → change-impact-analysis → architecture-contract-review | 不进入编码，除非用户另行批准实施 |

## 3. 编排步骤

1. 识别任务意图、是否涉及仓库、是否要求写操作、风险等级和完成定义。用户要求“出引导词/深入分析产品构想/基于当前项目知识规划下一步”时，必须先路由 product-manager；不得仅因提到代码或 Spec 就直接进入技术勘察。
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

## 7. 产品经理优先路由与深度引导词

- 对“出引导词 / 生成开发提示词 / 基于当前项目知识提出下一步任务”等请求，先由 `skills/product-manager/SKILL.md` 建立项目知识证据地图，再分析用户问题、现有能力、复用机会、缺口、范围和方案取舍。
- 输出必须包含需求理解、项目知识分析、产品判断、Skill 路由理由、完整可复制引导词、验收与运行时验证建议。
- 只有用户明确要求直接实施，且必要需求/审批门禁满足后，才进入编码；用户只要引导词时不得修改代码。
- 若目标工具未报告实际读取的 Skill/项目资料，不能把文件存在或路径展示当作已加载证据。路由是否在真实 Trae Code 会话生效，仍需运行时试点验证。
