# AIMES 全量 Skill 资产治理与验收

## 1. 目标

避免“主仓库存在 Skill，但初始化后的项目没有该文件”“注册表存在路由但目标文件缺失”“Skill 有文件但没有明确调用规则”“验证仅检查静态存在”等问题再次出现。

## 2. 资产层级

- `skills/registry.yaml` 与 `skills/**/SKILL.md`：仓库中的专业 Skill 源资产和规范登记。
- `src/aimes_cli/templates/skills/**/SKILL.md`：CLI 可随项目初始化分发的 Skill 包。
- `src/aimes_cli/templates/skills/registry.yaml`：项目级可执行路由登记，文件路径必须与初始化后的实际位置一致。
- `src/aimes_cli/templates/core/AIMES-CORE-V1.2.md`：任务分类、Skill 调用顺序、批准门禁和降级边界。
- `aimes validate`：对已初始化项目执行注册表与部署文件一致性检查。

根目录源注册表和项目级部署注册表的路径格式不同是允许的，但所有源注册 Skill 必须有同名可部署资产与项目级路由。项目级可以额外提供编排入口 Skill，例如 `product-analysis`。

## 3. 当前纳入项目初始化的 Skill

- 项目接管：`project-onboarding`
- 需求认知：`requirement-cognition`
- 知识复用：`project-knowledge-reuse`
- 变更影响分析：`change-impact-analysis`
- 架构与接口契约审查：`architecture-contract-review`
- 受控实施：`controlled-implementation`
- 需求驱动测试：`requirement-driven-testing`
- 产品分析编排入口：`product-analysis`
- 产品专项：`market-analysis`、`financial-evaluation`、`strategic-positioning`、`opportunity-solution-tree`、`customer-journey-mapping`
- UI 专项：`frontend-design`、`design-system-governance`、`ui-quality-review`、`ui-implementation-validation`

以上是资产部署覆盖范围，不意味着每个任务都要调用全部 Skill。Core 按触发条件选择适用技能，保持按需加载。

## 4. 自动化防回归

CI 测试应覆盖：
1. 根目录规范注册表中每个 Skill 都存在源文件。
2. 每个规范 Skill 都有项目模板副本和部署注册表路由。
3. 初始化后所有路由文件均存在，且注册表的 ID/名称不重复。
4. 路由缺失文件、路径越出项目根目录时，`aimes validate` 必须失败。
5. Skill 依赖引用必须能解析；缺少触发条件需给出警告。
6. 重复初始化不能静默覆盖用户修改过的注册表或 Skill 文件。
7. Core 对核心工程链路和专业 Skill 有明确调用规则，并说明失败/降级状态。

## 5. 状态边界

- 自动化测试只证明静态资产、路由和校验逻辑在测试环境中满足契约。
- `aimes validate` 检查项目文件与注册表结构，不证明 AI 工具运行时加载。
- ZCode、Trae Code、Claude Code、Codex 等工具需按工具 ID、版本、运行模式和平台分别做运行时探针与行为评测。
- 没有原始可复核证据时，运行时状态保持 `NOT_RUN` / `UNKNOWN`；宿主级 Skill 降级执行不得冒充 AIMES 项目级 Skill 成功调用。
