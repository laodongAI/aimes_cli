# AIMES 自动化工程质量检查与门禁

状态：确定性静态检查持续扩展；不代表 AI 语义审查已自动化。

## 1. 使用方式

```bash
aimes quality inspect
aimes quality inspect --format json

# 已安装 AIMES pre-commit hook 时，也会执行质量检查
```

检查不会修改源代码。默认 `enforce: false`，发现问题只报告，不改变现有项目构建/提交行为。审查基线后，可在 `.aimes/quality-gates.yaml` 设置 `enforce: true`；达到 `fail_on` 阈值的发现将返回非零退出码。

## 2. 当前确定性规则

| 规则 | 检查内容 | 默认 WARNING | 默认 ERROR |
|---|---|---:|---:|
| SFC_LINES | Vue 单文件组件总行数 | 400 | 600 |
| SCRIPT_LINES | Vue script block 行数 | 250 | 400 |
| TEMPLATE_LINES | Vue template block 行数 | 250 | 400 |
| VUE_DIRECT_HTTP_CALL | Vue script 中直接调用 fetch/axios HTTP 方法 | WARNING | — |

SFC 行数阈值可按项目调整；`vue.disallow_direct_http_calls` 可关闭直接 HTTP 调用规则；排除目录可配置。扫描跳过常见依赖、构建、虚拟环境目录，并忽略符号链接文件。

## 3. 质量结果语义

- PASS：无发现。
- PASS_WITH_FINDINGS：有发现，但未启用阻断门禁。
- FAIL：启用门禁且发现达到阻断级别。
- 配置错误作为 ERROR 报告；门禁开启时失败关闭。

每条发现包含规则 ID、级别、路径、指标、阈值和改进建议。报告只说明静态规则实际检查到的事实。

## 4. 当前边界

当前确定性检查覆盖 Vue SFC 体量，以及 `<script>` 中直接调用 `fetch()` / `axios.get/post/put/patch/delete/request()` 的情况。后者报告 WARNING，建议将网络请求与端点处理迁移到可复用 API Service；它不证明所有直接请求都一定错误，也不识别自定义 request wrapper。

它**不会**仅凭文本判断组件是否应复用、是否重复实现相同业务、Page 是否违反架构分层、Props/Emits 是否设计合理。这些需要后续引入 AI 语义审查，并要求提供可复核的文件/行号、证据和置信度。

安装的 AIMES pre-commit hook 会依次运行 `aimes validate` 与 `aimes quality inspect`；只有项目显式启用 `enforce: true` 且命中阻断级别时才会阻止提交。本工具不会自动拆分组件或重写业务代码。自动修复必须另行设计预览、补丁审查、备份、显式确认和验证流程。
