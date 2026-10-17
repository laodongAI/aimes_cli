# AIMES 治理升级实施记录：P1 第一批

- 日期：2026-10-18
- 分支：`governance/p0-audit-2026-10-18`
- PR：[#1](https://github.com/laodongAI/aimes_cli/pull/1)
- 版本：`0.7.8`（开发分支）

## 1. 本批已实现

1. 新增 `aimes docs check`，只读检查 Markdown 本地链接、配置中登记的工具入口是否存在，以及原生薄入口是否引用治理核心、是否超过默认 40 行。
2. 为文档检查器增加正反例测试：正常项目、断链、缺失核心引用、入口超长、配置入口缺失、外部链接、未初始化的普通文档仓库、模板内项目相对链接。
3. 新增 CLI 集成测试，验证 JSON 输出及校验失败退出码。
4. 新增 GitHub Actions 单元测试工作流；在现有单元测试之外，以非阻断方式执行仓库文档检查基线。
5. 将 `pyproject.toml`、`src/aimes_cli/__init__.py` 和 README 版本统一到 `0.7.8`。
6. 修复 Windows EXE 构建脚本遗漏包数据资源的问题：增加 PyInstaller `--collect-data aimes_cli`，确保治理核心模板能被收集。

## 2. 已取得的运行证据

- GitHub Actions 的 AIMES CLI 单元测试工作流已报告成功。
- 仓库文档基线检查报告：47 个 Markdown 文件、3 个本地链接，0 个 ERROR、0 个 WARNING。
- 第一次 Windows EXE 工作流：构建成功，但在外部目录运行 `aimes init --tools codex-cli` 时失败，日志明确显示缺少打包后的 `aimes_cli/templates/core/AIMES-CORE-V1.2.md`。
- 针对该失败已修改打包参数；修复后的 Windows EXE 工作流正在重新执行，最终结论需以该次工作流结果为准。

## 3. 设计边界

- `docs check` 是静态检查，不证明任何 IDE/插件在运行时加载了规则。
- 未初始化 AIMES 的普通 Markdown 仓库不强制要求存在 AIMES 核心文件；一旦存在 AIMES 配置或登记入口，则必须验证核心文件。
- 包内治理核心模板中的相对链接以消费项目根目录为基准，因此文档检查不会错误地将模板源文件当作项目根目录下的普通文档。
- 手动适配说明只检查文件存在性，不应用原生薄规则入口的长度和引用约束。
- 仓库文档扫描目前先作为 advisory baseline，不阻断 PR；待基线稳定、误报边界明确后再决定是否升级为门禁。

## 4. 后续

- P1：复核 Windows EXE 修复后的运行结果；在确认后完善版本发布与包资源完整性检查。
- P1：梳理现有 `trace validate` 的实体状态、关系类型、路径和证据边界；先补缺失的自动化测试，再决定是否需要独立注册表。
- P2：实现任务声明、活动写入者和每任务交接协议。
- P3：实现临时产物只读审计与指标采集。
