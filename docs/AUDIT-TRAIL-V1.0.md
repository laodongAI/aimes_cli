# AIMES 结构化审计追踪 V1.0

## 事件模型

每条 JSONL 事件至少包含：`schema_version`、`run_id`、`event_id`、`timestamp`、`event_type`、`status`、`actor`、`details`。相关事件共享 `run_id`；必要时可用 `parent_event_id` 串联阶段。

## 建议事件类型

`run.started`、`skill.selected`、`context.plan.created`、`evidence.collected`、`reuse.decision`、`tool.started`、`tool.completed`、`tool.failed`、`output.validated`、`run.completed`。

## 安全规则

- 仅记录完成追溯所需的摘要和引用，不默认写入完整 prompt、对话、源码或命令输出。
- 对 key/token/password/secret/cookie/authorization 等疑似敏感字段做递归脱敏。
- 事件日志不等于防篡改日志；如需高保证，应追加签名、远程只追加存储、权限隔离和保留策略。
- 审计写入失败应在结果中显式报告；高风险写操作若审计是强制控制，应失败关闭。

## 当前实现边界

V0.5.2 提供本地 JSONL 事件记录基础设施，调用方需显式记录事件。它不会自动观察任意 IDE 内部或所有模型交互，也不声称日志天然不可篡改。
