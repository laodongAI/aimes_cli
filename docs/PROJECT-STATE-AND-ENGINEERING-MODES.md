# 项目状态与工程模式感知

## 1. 目标

AIMES 将项目整体生命周期、当前任务的工程模式和任务执行阶段分开管理。三者不可合并成单一的 `project_status`：

| 维度 | 解决的问题 | 示例 |
|---|---|---|
| 项目生命周期 | 整个项目目前处于什么成熟阶段 | development |
| 工程模式 | 当前对话/任务正在做哪类工程工作 | frontend-optimization |
| 任务阶段 | 当前任务走到哪一步 | analysis |

项目可能长期处于开发阶段，而当前任务先做前端优化分析、再进入实现和验收；切换任务模式不应错误改变项目生命周期。

## 2. 已交付能力

- `.aimes/project-state.yaml`：兼容性项目级状态快照，保存生命周期及当前默认模式/阶段；多会话任务进度由独立任务与会话记录管理。
- `.aimes/project-state/engineering-modes.yaml`：工程模式目录，定义触发词、复用的 Skills、工作流标识和质量配置标识。
- `aimes state show`：查看状态及当前模式对应的 Skills/工作流/质量配置路由，并根据生命周期、模式和任务阶段给出下一步建议；交互式 CLI 启动时自动显示同一状态卡片。
- `aimes state modes`：查看所有已注册工程模式。
- `aimes state set`：显式设置项目生命周期、工程模式、任务阶段和当前任务摘要。
- `aimes state detect --task-text "..."`：对显式传入的任务文本做确定性关键词候选识别，不写入状态。
- `aimes state assess-lifecycle`：只读收集项目结构、测试、发布目录和 Git 历史证据，输出候选生命周期与限制，不自动写入。
- `aimes task start/list/show/update`：独立创建、查询和更新任务记录，任务阶段/状态不再依赖单一项目快照。
- `aimes session show/bind`：每个 AI 工具会话独立保存当前任务指针，支持切换/恢复任务。

## 3. 工程模式目录

首批注册模式：

- project-bootstrap：新项目初始化
- product-discovery：产品探索与需求分析
- architecture-design：架构设计
- feature-design：功能设计
- feature-development：新功能开发
- backend-development：后端开发
- frontend-development：前端开发
- frontend-optimization：前端体验优化
- refactoring：代码重构
- bugfix：缺陷修复
- performance-optimization：性能优化
- security-hardening：安全加固
- integration-development：集成开发
- testing-validation：测试与验收
- release-delivery：发布与交付
- documentation：文档建设
- technical-debt：技术债治理
- database-migration：数据库与数据迁移
- devops-ci：DevOps 与 CI/CD
- observability：可观测性建设
- ai-model-evaluation：AI 模型与 Agent 评测
- incident-response：线上故障与应急响应
- platform-migration：技术与平台迁移
- engineering-audit：工程审计

模式映射优先复用已有 Skills。例如前端优化组合 Vue 工程规范、UI 质量审查、前端设计和实现验证；重构组合软件工程规范与变更影响分析。并非每个模式都必须创建一份同名 Skill，只有存在稳定、独立、可评测的方法论时才新增专业 Skill。

当前工作流和质量配置字段是路由元数据。尚未配置/部署对应工作流执行器或质量策略时，不代表自动执行，也不代表已存在可执行的 workflow definition。

## 4. 命令用法

查看：

```bash
aimes state show
aimes state modes
```

显式设置：

```bash
aimes state set --lifecycle development --mode frontend-optimization --phase analysis --task "优化学习页面体验"
aimes state set --mode refactoring --phase implementation --task "拆分用户模块" --source ai --confidence medium
```

候选识别：

```bash
aimes state detect --task-text "请优化 Vue 页面交互和响应式体验"
```

JSON 输出可用于 AI 工具适配层：

```bash
aimes state show --format json
aimes state detect --task-text "修复接口调用错误" --format json
```

`detect` 不会保存候选；当命中多个模式时返回低置信度和候选列表，不擅自选择。用户显式指定模式始终优先。用户选择通过 `--source user` 记录；AI 根据对话判断后写入时必须使用 `--source ai --confidence high|medium`，低置信度不得持久化猜测。

## 5. 生命周期证据评估与任务/会话隔离

`aimes state assess-lifecycle` 是只读评估，不是自动分类器。它收集 README/语言构建清单、设计文档目录、测试目录、CI、发布记录、部署目录以及可用 Git 历史/标签等有限信号，返回：

- 当前已保存的项目生命周期；
- 可能的生命周期候选和置信度；
- 每个文件/目录/Git 信号的证据；
- 判断限制与需要人工确认的事项。

它不读取源码正文、不执行项目代码、不联网，也不自动修改生命周期。目录存在不能证明功能完成、测试通过或服务正在运行。应结合项目任务、CI 结果、发布记录和负责人确认，再通过 `aimes state set --lifecycle ...` 显式更新。

任务和会话记录分开保存：

- `.aimes/tasks/<task-id>.yaml`：任务标题、工程模式、状态、阶段、所属会话及时间戳。
- `.aimes/sessions/<session-id>.yaml`：该会话当前关联的任务 ID。
- 一个项目可有多个任务；不同 AI 工具使用不同 session ID，任务阶段更新不会改写项目生命周期或其他会话指针。
- 同一任务可以被另一个会话显式绑定；任务记录仍是单份权威数据。并发写同一任务时仍需外部协调，当前不提供分布式锁。

示例：

```bash
aimes state assess-lifecycle
aimes task start --title "优化前端体验" --session-id codex --mode frontend-optimization
aimes task list --session-id codex
aimes task update --id <task-id> --phase testing --status blocked
aimes session show --id codex
aimes session bind --id codex --task-id <task-id>
```

## 6. MCP 工具

AIMES MCP Server 同步暴露三个项目状态工具，供已连接的 AI 宿主调用：

- `aimes_project_state`：只读读取当前状态、可用/缺失 Skills 和下一步建议。
- `aimes_detect_engineering_mode`：对宿主传入的任务摘要做确定性候选识别，不持久化。
- `aimes_set_project_state`：持久化生命周期、模式、任务阶段或任务摘要。设置工程模式时必须提供 `source`；AI 来源的低置信度模式会被拒绝，需先向用户确认。

工具声明不代表宿主已连接或自动调用；必须在目标工具中验证 MCP 连接、工具发现和真实调用证据。

## 7. AI 对话与 CLI 的职责边界

本地 CLI 无法自行读取 Codex、Claude Code、Trae、ZCode、QCode 或 ChatGPT 的当前对话内容。因此：

1. AI 工具开始任务时，先读取项目指令、`aimes state show`、任务记录和 Git 状态。
2. AI 根据当前用户意图识别工程模式，而不是仅凭项目生命周期推断。
3. AI 可以把简洁任务描述传给 `aimes state detect` 作为候选辅助；关键词识别不是语义理解。
4. 高置信度且与用户明确要求一致时可更新状态；中置信度结合任务语义、触发证据和项目规则判断，必要时确认；低置信度或多模式冲突必须先向用户确认。
5. 模式确认后，读取模式映射的 Skills，并继续调用既有 `aimes skill route`。映射是组合入口，不替代 Skill 正文和调用证据。
6. 任务阶段变化时只更新 task_phase；工程模式变化时只更新 engineering_mode；除非有明确项目决策，不自动修改 project_lifecycle。

## 8. 生命周期与任务状态约束

生命周期取值：`unknown`、`new`、`planning`、`design`、`development`、`testing`、`release`、`operation`、`paused`、`archived`。

任务阶段取值：`analysis`、`clarification`、`design`、`review`、`implementation`、`testing`、`acceptance`、`delivery`。

初始化时生命周期默认 `unknown`，因为对一个已有仓库执行 AIMES init 并不代表它是新项目。只有显式确认后才设置为 `new` 或其他生命周期。

## 9. 当前限制与后续迭代

- 项目生命周期仍是项目级共享状态；任务记录与会话指针已分离，但多个进程并发更新同一任务时尚无文件锁/乐观版本冲突检测。
- 当前关键词识别是确定性辅助，不调用模型、不读取会话、不上传数据。
- 当前模式映射声明 Skills、workflow ID 和质量配置 ID；尚未将所有 workflow/quality profile 变成自动执行的模式专属策略。
- 状态变更记录更新时间，但当前还没有完整的状态事件审计、历史回滚和任务完成自动迁移。
- 后续阶段应增加模式工作流执行、质量配置绑定、状态转换守卫、状态历史审计/回滚、增强运行时反馈卡片和跨工具实测评估。

静态部署与单元测试通过不能证明任一 AI 宿主已自动加载状态或遵循路由。运行时能力必须按具体工具、版本和执行模式单独验证。

当工程模式或当前任务摘要发生变化且未显式传入 `--phase` 时，AIMES 会将任务阶段重置为 `analysis`，避免把上一任务的 testing/acceptance 阶段错误带入新任务。