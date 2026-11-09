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

- `.aimes/project-state.yaml`：项目级状态快照，保存生命周期、当前工程模式、任务阶段、任务摘要、模式来源、置信度和更新时间。
- `.aimes/project-state/engineering-modes.yaml`：工程模式目录，定义触发词、复用的 Skills、工作流标识和质量配置标识。
- `aimes state show`：查看状态及当前模式对应的 Skills/工作流/质量配置路由；交互式 CLI 启动时自动显示同一状态卡片。
- `aimes state modes`：查看所有已注册工程模式。
- `aimes state set`：显式设置项目生命周期、工程模式、任务阶段和当前任务摘要。
- `aimes state detect --task-text "..."`：对显式传入的任务文本做确定性关键词候选识别，不写入状态。

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
- technical-debt：技术债治理\n- database-migration：数据库与数据迁移\n- devops-ci：DevOps 与 CI/CD\n- observability：可观测性建设\n- ai-model-evaluation：AI 模型与 Agent 评测\n- incident-response：线上故障与应急响应\n- platform-migration：技术与平台迁移\n- engineering-audit：工程审计

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
aimes state set --mode refactoring --phase implementation --task "拆分用户模块"
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

`detect` 不会保存候选；当命中多个模式时返回低置信度和候选列表，不擅自选择。用户显式指定模式始终优先。

## 5. AI 对话与 CLI 的职责边界

本地 CLI 无法自行读取 Codex、Claude Code、Trae、ZCode、QCode 或 ChatGPT 的当前对话内容。因此：

1. AI 工具开始任务时，先读取项目指令、`aimes state show`、任务记录和 Git 状态。
2. AI 根据当前用户意图识别工程模式，而不是仅凭项目生命周期推断。
3. AI 可以把简洁任务描述传给 `aimes state detect` 作为候选辅助；关键词识别不是语义理解。
4. 高置信度且与用户明确要求一致时，按工具权限和项目规则更新状态；中/低置信度时先向用户确认。
5. 模式确认后，读取模式映射的 Skills，并继续调用既有 `aimes skill route`。映射是组合入口，不替代 Skill 正文和调用证据。
6. 任务阶段变化时只更新 task_phase；工程模式变化时只更新 engineering_mode；除非有明确项目决策，不自动修改 project_lifecycle。

## 6. 生命周期与任务状态约束

生命周期取值：`unknown`、`new`、`planning`、`design`、`development`、`testing`、`release`、`operation`、`paused`、`archived`。

任务阶段取值：`analysis`、`clarification`、`design`、`review`、`implementation`、`testing`、`acceptance`、`delivery`。

初始化时生命周期默认 `unknown`，因为对一个已有仓库执行 AIMES init 并不代表它是新项目。只有显式确认后才设置为 `new` 或其他生命周期。

## 7. 当前限制与后续迭代

- 状态是项目级单一快照；多用户、多分支、多会话并发时还需要 session/task 级状态模型与冲突策略。
- 当前关键词识别是确定性辅助，不调用模型、不读取会话、不上传数据。
- 当前模式映射声明 Skills、workflow ID 和质量配置 ID；尚未将所有 workflow/quality profile 变成自动执行的模式专属策略。
- 状态变更记录更新时间，但当前还没有完整的状态事件审计、历史回滚和任务完成自动迁移。
- 后续阶段应增加任务/会话状态分离、模式工作流执行、质量配置绑定、状态转换守卫、运行时反馈卡片和跨工具实测评估。

静态部署与单元测试通过不能证明任一 AI 宿主已自动加载状态或遵循路由。运行时能力必须按具体工具、版本和执行模式单独验证。
