# AIMES 自动化工程质量检查与门禁

状态：初始实现（确定性静态检查）；不代表 AI 语义审查已自动化。

## 1. 使用方式

```bash
aimes quality inspect
aimes quality inspect --format json
```

检查不会修改源代码。默认 `enforce: false`，发现问题只报告，不改变现有项目构建/提交行为。审查基线后，可在 `.aimes/quality-gates.yaml` 设置 `enforce: true`；达到 `fail_on` 阈值的发现将返回非零退出码。

## 2. 当前确定性规则

| 规则 | 检查内容 | 默认 WARNING | 默认 ERROR |
|---|---|---:|---:|
| SFC_LINES | Vue 单文件组件总行数 | 400 | 600 |
| SCRIPT_LINES | Vue script block 行数 | 250 | 400 |
| TEMPLATE_LINES | Vue template block 行数 | 250 | 400 |

阈值可按项目调整；排除目录可配置。扫描跳过常见依赖、构建、虚拟环境目录，并忽略符号链接文件。

## 3. 质量结果语义

- PASS：无发现。
- PASS_WITH_FINDINGS：有发现，但未启用阻断门禁。
- FAIL：启用门禁且发现达到阻断级别。
- 配置错误作为 ERROR 报告；门禁开启时失败关闭。

每条发现包含规则 ID、级别、路径、指标、阈值和改进建议。报告只说明静态规则实际检查到的事实。

## 4. 当前边界

本版只对 Vue SFC 体量进行确定性检查。它**不会**仅凭文本判断组件是否应复用、是否重复实现相同业务、Page 是否违反架构分层、Props/Emits 是否设计合理。这些需要后续引入 AI 语义审查，并要求提供可复核的文件/行号、证据和置信度。

本工具不会自动拆分组件或重写业务代码。自动修复必须另行设计预览、补丁审查、备份、显式确认和验证流程。
