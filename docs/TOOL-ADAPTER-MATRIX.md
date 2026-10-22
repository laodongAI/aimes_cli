# AIMES 工具适配矩阵（基线）

| 工具上下文 | 预期入口 | CLI 动作 | 当前状态 | 关键验证 |
|---|---|---|---|---|
| Trae Code | `.trae/rules/00-aimes-governance.md` | 生成模板 | 模板候选，需按版本确认 | 新会话能否读取项目规则 |
| VS Code + Codex | `AGENTS.md` | 生成共享入口 | 静态模板 | 扩展实际模式是否读取 AGENTS.md |
| VS Code + Claude Code | `CLAUDE.md` | 生成共享入口 | 静态模板 | 扩展是否按 Claude Code 规则加载 |
| VS Code + Copilot | `.github/copilot-instructions.md` | 生成模板 | 静态模板 | Copilot Agent 实际模式加载情况 |
| ZCode | 未确认 | 生成审查说明，不猜测路径 | 手动/未验证 | 插件 manifest、规则加载、路由冲突、运行时验收 |
| QCode | 未确认 | 生成审查说明，不猜测路径 | 手动/未验证 | 产品身份、版本、文档和实际加载行为 |
| Claude Code CLI | `CLAUDE.md` | 生成共享入口 | 静态模板 | CLI 新会话实际加载与引用深度 |
| Codex CLI | `AGENTS.md` | 生成共享入口 | 静态模板 | CLI 新会话实际加载与指令优先级 |

## 验证上下文

每条新验证记录必须区分工具执行模式（IDE 插件、CLI 或桌面应用），并记录操作系统、产品版本、规则入口、案例 ID、观察时间、观察者、AIMES CLI 版本与治理核心版本。新证据文件使用 `schema_version: 2`；V2 中的 PASS 缺少上述上下文会被拒绝。V1 记录仍可读取，但缺少字段仅提示警告，不代表已达到新的可复现要求。

## 状态定义

- `UNKNOWN`：产品身份、入口或加载行为未知。
- `TEMPLATE`：已生成配置模板，但未证明运行时加载。
- `STATIC-PASS`：文件结构、路径和 Schema 检查通过。
- `RUNTIME-PASS`：在指定产品版本和模式下执行了验收用例并留存证据。
- `LIMITED`：存在已知限制，不能按完整能力宣传。

不允许将 `TEMPLATE` 自动提升为 `RUNTIME-PASS`。


## V0.5 证据记录约定

每个工具上下文应单独登记验证记录，即使它们共用 `AGENTS.md` 或 `CLAUDE.md`。建议字段包括产品版本、规则入口、验证方法、观察时间、观察者、证据文件及 SHA-256。`file_inspection` 只证明文件被检查，不证明运行时读取；`runtime_observation`、`automated_check` 或 `user_confirmed` 需要附可复核证据。未知状态应保留为 `UNKNOWN` 或 `NOT_RUN`。
