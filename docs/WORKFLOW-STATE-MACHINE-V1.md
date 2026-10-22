# AIMES 声明式工作流状态机 V1

## 1. 目标和边界

工作流定义描述允许的状态、转换、审批要求、失败恢复和重试策略。V1 提供只读定义校验，以及需要显式确认的本地运行记录创建/状态转换。它不会执行 AI 工具或自动批准操作；状态转换必须由操作者提交事件与审批/守卫证据。

定义文件示例：`examples/workflows/engineering-workflow.example.yaml`。

## 2. 状态契约

每个状态需要定义：

- `state_id`、`name`：稳定标识与可读名称；
- `entry_conditions`：进入该状态前必须满足的条件；
- `required_artifacts`：状态运行所需产物；
- `completion_criteria`：判断状态完成的可检查条件；
- `failure_recovery`：失败时的安全处理与恢复建议；
- `side_effects`：可能发生的写入或命令副作用；
- `approval_required`：是否需要外部审批；该字段本身不构成审批凭据；
- `retry_mode`、`max_attempts`：重试策略；
- `terminal_outcome`：终态使用 `SUCCESS`、`FAILURE`、`BLOCKED` 或 `CANCELLED`，非终态使用 `null`。

`retry_mode` 的含义：

- `idempotent`：重复执行不会造成额外副作用，仍需遵守 `max_attempts`。
- `guarded`：只有 `retry_guard` 中的条件经过检查后才允许重试。
- `never`：不允许重试，`max_attempts` 必须为 1。

终态不得有出边。重试必须显式使用 `on: retry` 并返回同一状态。V1 禁止除显式重试自环以外的图环，以避免隐式无限循环。

## 3. 转换和图校验

转换事件支持 `success`、`failure`、`blocked`、`cancelled`、`retry`、`approval_granted` 和 `approval_denied`。

验证器检查：

1. 入口状态存在，状态 ID 和转换唯一；
2. 所有转换的源/目标状态存在；
3. 每个非终态有成功路径和失败/阻塞/取消路径；
4. 至少有一个 SUCCESS 终态；
5. 所有状态从入口可达；
6. 不存在非重试循环；
7. 重试策略与最大尝试次数一致，受控重试必须有 guard。

## 4. 使用方式

```powershell
aimes workflow validate examples/workflows/engineering-workflow.example.yaml --root . --format json
```

JSON Schema：`schemas/workflow-definition.schema.json`；打包副本位于 `src/aimes_cli/schemas/workflow-definition.schema.json`。CI 校验示例定义。

## 5. 本地运行记录与状态转换

命令支持：

```powershell
aimes workflow run start examples/workflows/engineering-workflow.example.yaml --record .aimes/workflows/runs/task-001.json --run-id TASK-001-RUN-1 --task-id TASK-001 --baseline-commit <commit-sha> --confirm START --root . --format json
aimes workflow run validate examples/workflows/engineering-workflow.example.yaml .aimes/workflows/runs/task-001.json --root . --format json
aimes workflow run transition examples/workflows/engineering-workflow.example.yaml .aimes/workflows/runs/task-001.json --event success --approval-ref APPROVAL-001 --evidence-ref EVIDENCE-001 --confirm TRANSITION --root . --format json
```

- 启动需要 `START` 确认；转换需要 `TRANSITION` 确认，均大小写不敏感。
- 已存在的运行记录不会被覆盖；每次成功转换前会将旧记录备份到 `.aimes/backups/workflow-runs/<run-id>/`，然后原子更新运行记录。
- 运行记录保存工作流定义 SHA-256；定义发生变化时，验证器会阻止继续转换，需先审查并明确处理旧运行记录。
- 进入要求审批的状态时必须提供 `--approval-ref`；守卫转换和 guarded 重试必须提供 `--guard-evidence`。
- 转换只记录状态，不运行外部命令。`evidence-ref` 必须指向实际存在且可复核的外部证据；CLI 不会替用户生成该证据。

## 6. 当前限制和后续

当前能力只检查定义结构和图的一致性。它还不会：

- 持久化每次运行的当前状态、尝试次数或检查点；
- 在重启后恢复运行；
- 真的执行审批工作流或锁定写权限；
- 在失败后自动重试、回滚或重放工具命令；
- 证明状态转换背后的外部证据真实。

后续实施应先增加可持久化的运行记录、状态转换审计、并发/幂等保护和中断恢复测试，再考虑执行引擎。
