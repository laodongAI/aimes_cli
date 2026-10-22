# AIMES Skill 执行记录 V1

## 1. 目标

Skill 注册表描述“这个 Skill 应该是什么”；执行记录描述“某一次任务中实际发生了什么”。两者必须分离，不能把 Skill 定义、模型自述或静态文件存在当作执行证据。

执行记录由实际运行的工具/操作者填写。当前 `aimes skill execution validate` 只校验结构与状态一致性，不会调用模型、运行 Skill、读取 IDE 内部状态或证明证据真实性。

## 2. 必需上下文

每次执行记录应包含：

- 唯一 `run_id`、`task_id`、`skill_id`、Skill 版本与注册表版本；
- 执行基线 commit、工具 ID/版本、执行模式、AIMES CLI 版本与治理核心版本；
- 带时区的开始时间；终态运行必须有带时区的结束时间；
- 按顺序记录的步骤、跳过原因、验收检查、输出引用和证据引用；
- 未解决问题、审批引用，以及可获取时的 Token usage。

不要把完整提示词、秘密、凭证或敏感项目数据复制进记录；只引用必要的产物 ID、路径或脱敏日志。

## 3. 状态语义

运行状态：`PASS`、`FAIL`、`BLOCKED`、`CANCELLED`、`UNKNOWN`、`IN_PROGRESS`。

步骤状态：`COMPLETED`、`SKIPPED`、`FAILED`、`BLOCKED`、`NOT_RUN`。

- 每个 SKIPPED 步骤必须提供 `skip_reason`。
- PASS 必须有结束时间、至少一个步骤、至少一个输出引用、至少一个证据引用，以及至少一个全部通过的验收检查。
- PASS 不能包含 FAILED、BLOCKED 或 NOT_RUN 步骤；跳过的步骤必须记录理由。
- 验收检查的 PASS 仍应关联外部证据；验证器不能确认外部证据内容是否真实。
- 无法获取真实 Token usage 时，`usage.source` 使用 `unavailable`，所有 token 数值为 `null`。不允许估算后填入数字。

## 4. 示例与命令

示例文件 `examples/skills/execution-record.example.yaml` 明确标记为 DEMO、状态为 UNKNOWN，不是真实运行证明。

在项目根目录运行：

```powershell
aimes skill execution validate examples/skills/execution-record.example.yaml --root . --format json
```

JSON Schema：`schemas/skill-execution-record.schema.json`。打包后的 Schema 位于 `src/aimes_cli/schemas/skill-execution-record.schema.json`；测试会检查两份定义一致。

## 5. 当前边界与后续

当前能力：验证记录结构、版本/执行模式、重复步骤与验收 ID、跳过原因、终态约束、PASS 的输出/证据/验收门禁，以及 Token usage 不可用时禁止估算。

尚未实现：自动从 Codex/Claude Code 会话采集运行记录、签名/防篡改、自动审批服务、自动恢复执行和自动判定真实结果。下一阶段将围绕工作流状态机增加可恢复状态、幂等重试和审批交接。
