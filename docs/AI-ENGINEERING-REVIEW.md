# AIMES AI 工程审查报告契约（V1）

## 目标与边界

确定性静态检查无法可靠判断组件复用、业务逻辑重复、职责边界、前后端分层或需求—设计—代码—测试追踪关系。AI 工具可以执行这些语义审查，但结论必须携带可核验的源码证据。

AIMES V1 采用“外部 AI 生成报告、AIMES 本地验证报告”：不在 CLI 内绑定模型供应商，不暗示 AIMES 已自动调用模型。`aimes quality review` 只验证报告结构和证据，不验证模型推理过程是否正确。

## 命令

```powershell
aimes quality inspect --root . --format json
aimes quality review-context --root . --format json --output .aimes/reviews/review-context.json
aimes quality review --report .aimes/reviews/engineering-review.json --root . --format json

# 汇总静态检查与 AI 审查结果（AI 报告可选）
aimes quality report --ai-report .aimes/reviews/engineering-review.json --root . --format json
```

报告文件和证据源码必须位于项目根目录内。路径解析会处理 `..` 与符号链接；越界路径、缺失文件、超出文件长度的行号、与源码不匹配的 excerpt 均会被拒绝。

## 审查上下文包

`aimes quality review-context` 只读生成供外部 AI 工具使用的上下文包。默认仅从根目录治理入口/项目说明文件及 `src`、`app`、`backend`、`frontend`、`web`、`tests`、`docs/design`、`docs/architecture`、`.aimes/skills` 等受控位置收集文本文件。

默认上限为 80 个文件、单文件 8 KiB、总量 180 KiB。排除常见凭据文件名/目录、密钥/证书扩展名、若干常见密钥内容模式、依赖/构建目录、符号链接和超限文件；输出包含文件清单、SHA-256、审查提示词和跳过统计。命令不会调用模型、上传文件或执行项目代码。

```powershell
aimes quality review-context --root . --format json --output .aimes/reviews/review-context.json
```

上下文包可能因扫描目录白名单和大小限制而遗漏相关材料。敏感文件过滤是启发式保护，**分享给外部 AI 服务前必须人工检查上下文包**。

## JSON 契约

```json
{
  "schema_version": 1,
  "findings": [
    {
      "id": "AI-REUSE-001",
      "category": "component-reuse",
      "severity": "WARNING",
      "message": "两个页面可能重复实现相同的筛选交互。",
      "recommendation": "对比状态、事件和业务约束，确认是否抽取共享组件。",
      "confidence": 0.87,
      "evidence": {
        "path": "src/views/Users.vue",
        "line_start": 1,
        "line_end": 3,
        "excerpt": "<template>"
      }
    }
  ]
}
```

每条 finding 必须包含唯一 ID、类别、级别、问题、建议、0 到 1 的置信度，以及源码路径、起止行和原文摘录。摘录必须出现在对应行范围中。

## 建议审查维度

- 组件复用：相似 UI/交互是否有稳定的共享抽象；避免为了复用而过度抽象。
- 职责边界：Page/View、业务组件、Composable、Store、API Service 是否职责清晰。
- 重复逻辑：相同业务规则是否在多个页面或模块重复实现。
- 前后端分层：Vue 是否承载了应属于服务端的业务规则；FastAPI Router、Service、Repository 是否越层。
- 契约影响：API、DTO、类型定义变化是否同步影响调用方、错误处理和兼容性。
- 需求追踪：需求、设计决策、实现位置、测试用例是否有可定位关联。

## 安全与门禁策略

- AI finding 只允许 `INFO` 或 `WARNING`；报告声明 `ERROR` 将被拒绝。
- AI finding 永远标记 `origin=ai`、`blocking=false`，不能单独令确定性质量门禁失败。
- 只有静态规则或其他明确、可重复执行且经过项目授权的验证，才可作为阻断依据。
- 报告中的文本视为不可信数据；不会执行报告内容、命令或建议。
- 不扫描或上传源码；该命令只读取报告引用的项目内文件以核验行号和摘录。
- 报告验证通过只代表结构与证据定位通过，不代表语义判断正确，也不等同于 VERIFIED 交付结论。

## 当前限制

当前版本支持受控上下文包生成和外部 AI JSON 报告验证；仍不自动调用模型、不上传源码、不执行修复，也不将 AI 发现合并为静态门禁的阻断项。上下文包是否完整、敏感信息是否被排除，仍需人工复核。


## 统一质量报告

`aimes quality report` 将静态检查和经过证据验证的 AI findings 统一到一个 Finding 结构中，保留 `origin`、`category`、`severity`、`message`、`recommendation`、`evidence`、`confidence` 和 `blocking`。静态检查仍是门禁结果的唯一权威来源；AI finding 永远 advisory，不能让原本通过的静态门禁变成失败。

不提供 `--ai-report` 时只输出静态质量报告。提供 AI 报告但验证失败时，命令返回 `INVALID_AI_REPORT`，不会静默合并不可信数据。统一报告是展示和后续治理集成的基础，不代表已经具备自动修复或变更影响分析能力。
