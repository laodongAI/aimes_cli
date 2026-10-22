# AIMES CLI 实现状态与验证历史


> **当前状态入口（2026-10-22）**：本文后续表格保留各历史阶段的实现记录，不应单独作为当前版本快照。当前能力与验证状态以 [能力与验证状态矩阵](CAPABILITY-VERIFICATION-MATRIX.md) 为准，后续路线以 [工程能力增强路线图 V0.9](ROADMAP-ENGINEERING-EXCELLENCE-V0.9.md) 为准。
>
> 当前包版本声明为 `0.8.0`，治理核心版本为 `1.2`。代码/模板已进入主干、CI 自动化测试通过、特定 AI 工具运行时已验证、真实项目试点已验收是四种不同状态。不得将其中任何一种自动推断为其他状态。

## 当前验证边界

- `aimes release validate` 检查包版本、运行版本、README 版本、治理核心模板和打包配置；它不创建 GitHub Release，也不证明下载资产已发布。
- `aimes evaluation validate/report/compare` 负责验证和比较已记录的评测数据，不自动调用真实模型或 IDE 执行开发任务。
- `aimes adapter validate/report` 校验适配验证记录，不自动探测 IDE 内部状态；无证据时保持 `UNKNOWN` 或 `NOT_RUN`。
- Windows EXE 构建/冒烟测试、用户本机安装验证和真实工具行为验收应分别记录，不相互替代。

| 能力 | 状态 | 证据/说明 |
|---|---|---|
| 项目初始化、配置、inspect、diff、validate、doctor、status | `IMPLEMENTED_UNVERIFIED`（容器内测试通过） | V0.1 回归测试；目标 Windows 环境待验证 |
| 需求认知记录结构校验 | `IMPLEMENTED_UNVERIFIED` | `aimes requirement validate`；必填字段、状态、重复 ID、验收条件、批准证据 |
| 知识资产结构校验 | `IMPLEMENTED_UNVERIFIED` | `aimes knowledge validate`；来源、适用条件、成熟度和证据、项目路径逃逸 |
| 复用决策结构校验 | `IMPLEMENTED_UNVERIFIED` | `aimes reuse validate`；决策枚举、候选资产、比较记录、验证计划 |
| Skill 注册表和引用文件校验 | `IMPLEMENTED_UNVERIFIED` | `aimes skill validate`；必填契约、ID、风险/状态、文件引用、路径逃逸、推荐章节 |
| JSON 报告 | `IMPLEMENTED_UNVERIFIED` | 报告包含 schema_version、validator、source、ok、summary、findings |
| AI 自动需求评审/自动批准 | `NOT_APPLICABLE` | CLI 不负责语义裁决或批准 |
| 知识自动升级为 validated | `NOT_APPLICABLE` | 必须由真实证据和治理流程决定；本版本只检查记录字段 |
| 需求—设计—实现—测试追溯检查 | `IMPLEMENTED_UNVERIFIED` | V0.3 `trace validate`；引用完整性、重复 ID、缺失链接 |
| 评测集和回归报告 | `PLANNED` | V0.4 |
| 多工具规则加载/交接试点证据 | `PLANNED` | V0.5 |
| Windows 真实环境安装 | `UNKNOWN` | 尚未在用户机器执行 |
| IDE/Agent 实际规则加载 | `UNKNOWN` | 必须逐工具做行为验收，不以文件存在代替证据 |

注意：容器内测试通过只证明所覆盖的代码路径在当前测试环境下可运行，不等于用户目标环境已验证。

## 首批 P0 Skills

| Skill | 状态 |
|---|---|
| project-onboarding | `DRAFT`，待真实项目试点 |
| requirement-cognition | `DRAFT`，待真实需求案例评测 |
| project-knowledge-reuse | `DRAFT`，待复用正确率评测 |
| change-impact-analysis | `DRAFT`，待变更任务试点 |
| architecture-contract-review | `DRAFT`，待高风险设计评审试点 |
| controlled-implementation | `DRAFT`，待真实编码任务试点 |
| requirement-driven-testing | `DRAFT`，待需求覆盖与测试结果评测 |

Skill 文件是标准化工作流草案，不等于已在所有 AI 工具中生效。注册表中的 `validation_status` 初始保持 `UNKNOWN`，直到具体工具、版本、运行模式和项目案例完成可复核评测。


## V0.3.0 实现状态（2026-10-14）

- 已实现：`trace validate`、`evidence validate`、`context pack`。
- 已实现：追溯 ID/链接检查、VERIFIED → PASS 证据引用门禁、证据产物路径根目录限制、可选 SHA-256 校验、Context Pack 文件哈希清单。
- 已实现：trace/evidence JSON Schema、示例 manifest、HANDOFF 模板输出和专项自动化测试。
- 自动化测试：23 passed / 0 failed（Linux 容器，Python 3.13）。
- 未验证：Windows 11 安装、真实项目接入、CI 证据来源可信性、IDE/Agent 跨会话加载。示例证据仅为演示记录。
- 尚未实现：证据签名/来源证明、跨文件全域 ID 自动发现、图形化追溯视图、跨工具上下文自动注入。


## V0.4.0 — AI 开发准确度评测与回归

**已实现：** 评测集结构校验；运行记录结构校验；案例状态、硬门禁与诊断分数汇总；基线/候选比较；硬门禁回退识别；评测集与运行记录 Schema；示例评测集；自动化测试。

**未实现：** 自动驱动具体模型/IDE/Agent 执行评测任务；自动化隔离仓库快照；独立盲审平台；可信证据签名/验证；基于评测阈值自动发布 Skill。以上不应被当前 CLI 能力暗示为已具备。


## V0.5.0 增量

- 已实现工具验证证据记录校验和覆盖报告。
- 已实现 Context Pack 的源文件哈希复核及 HANDOFF 存在性检查。
- 已实现证据方法门禁：文件静态检查不能单独作为运行时 PASS。
- 未实现 IDE 内部状态探测、自动提示注入、自动跨工具执行、证据签名/可信时间戳及用户机器端到端验证。


## V0.5.1 提示词优化增量

- 已完成：7 个 P0 Skills 0.2.0 文本修订；统一提示词契约；Skill 编排协议；提示词审计报告；14 个基准案例；评测结构校验。
- 未实现：自动模型调用/自动 IDE 操作/自动 Skill 编排执行器；统一证据格式尚未全部映射到 CLI Schema。
- 未验证：Windows 11 安装、真实 IDE/Agent 规则加载、跨工具效果、模型输出质量改善。
- 所有 Skill `validation_status` 保持 `UNKNOWN`，直至实际工具试点留下可复核证据。


## V0.5.2 增量状态

- 已实现：共享输出正反例、文件选择计划协议、工具失败分类与降级协议。
- 已实现：本地 JSONL 审计事件 append/validate，包含常见敏感字段脱敏。
- 已实现：Mock Runner，对提供的 fixture 文本执行精确子串检查；该模式明确 `model_evaluation: false`。
- 已实现：关键 YAML/JSON 解析错误的行列定位与修复提示，以及新增命令的回归测试。
- 部分实现：审计记录由调用方显式触发，不会自动捕获全部命令、模型对话或 IDE 运行时活动。
- 未实现：真实模型 API/本地模型适配器、语义级判定、自动纠错重试、完整 Skill 自动编排引擎、交互式配置向导。
- 未验证：Windows 11 和真实 Claude Code/Trae/Cursor/ZCode 等 IDE 运行时行为。
