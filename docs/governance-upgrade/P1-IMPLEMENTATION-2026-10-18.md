# AIMES 治理升级实施记录：P1

- 日期：2026-10-18
- 分支：`governance/p0-audit-2026-10-18`
- PR：[#1](https://github.com/laodongAI/aimes_cli/pull/1)
- 开发版本：`0.7.9`

## 1. 文档与薄入口检查

- 新增 `aimes docs check`：只读检查 Markdown 本地链接、配置登记的工具入口是否存在、原生薄入口是否引用治理核心、是否超过默认 40 行。
- 测试覆盖正常文档、断链、缺失核心引用、入口超长、配置入口缺失、外部链接、普通未初始化仓库和模板内项目相对链接。
- 文档扫描先以 advisory baseline 运行，不直接阻断 PR；待存量问题和误报边界确认后再升级门禁。

## 2. 追溯校验补强

- 扩展追溯实体类型，支持 module、feature、design、code。
- 对不同实体类型应用对应状态词表；knowledge 使用知识成熟度词表，其它任务类实体使用全局状态词表。
- 校验 `evidence_refs`、`evidence_file` 和 `context_files` 的字段类型，避免错误数据触发未捕获异常。
- 增加测试覆盖非法状态、知识状态词表及错误路径字段类型。
- 复用现有 `trace validate`，没有另造第二套追溯注册表。

## 3. 发布兼容性

- 统一 `pyproject.toml`、运行时 `__version__` 和 README 标题版本为 `0.7.9`。
- 新增 `aimes release validate`，校验包/运行时/README 版本、治理核心模板版本、包数据声明和 Windows EXE 数据收集配置。
- 将 release validate 加入 GitHub Actions 阻断步骤。
- 修复 Windows EXE 构建缺少治理核心模板的问题：增加 PyInstaller `--collect-data aimes_cli`。

## 4. 运行证据

- GitHub Actions 单元测试曾在任务交接新增时暴露一个非法 newline 参数；已修复并增加回归测试。
- 最近一次完整单元测试运行：105 项测试通过，release compatibility 检查通过，advisory 文档检查通过。
- Windows EXE 构建及外部目录初始化冒烟测试在修复资源收集后已通过一轮；更晚的 P2/P3 提交正在进行再次验证。
- 文档基线：47 个 Markdown 文件、3 个本地链接，0 个 ERROR、0 个 WARNING。

## 5. 边界

- 静态检查不能证明 IDE/插件实际加载了规则。
- 真实工具规则加载仍需在目标 Windows 工作区中按工具/版本执行验收，并保存证据。
- 文档检查、追溯检查和 release validate 的报告不能替代人工架构批准或功能验收。
