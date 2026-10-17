# AIMES 治理升级实施记录：P3 第一批

- 日期：2026-10-18
- 分支：`governance/p0-audit-2026-10-18`
- 关联 PR：[#1](https://github.com/laodongAI/aimes_cli/pull/1)
- 开发版本：`0.7.9`

## 1. 临时产物审计

新增 `aimes cleanup audit`，支持：

- 读取 `.aimes/temp-registry.yaml`，校验 Schema 版本、条目 ID 唯一性、路径边界、分类、状态、创建时间与到期时间。
- 检查登记项是否存在、是否过期、是否已标记删除但仍然存在。
- 扫描常见的 pip 临时目录、Python bytecode、pytest/mypy/ruff 缓存和 `.tmp/.temp` 文件。
- 报告未登记候选、风险类别、大小和临时项合规率。
- 设置最大扫描条目数，超限时明确报告扫描不完整。

**安全边界：** 命令只读，不删除、不改名、不移动文件。A/B/C 只是风险分类，不是删除授权。默认跳过 Git 元数据、虚拟环境、依赖目录和 AIMES 自身控制/报告目录。

## 2. 工程指标报告

新增 `aimes metrics report`，对应 AIMES-CORE-V1.2 中定义的九项指标：

1. 需求追溯率；
2. 功能实现映射率；
3. 功能测试映射率；
4. 验证证据完整率；
5. 追溯引用有效率；
6. 文档链接有效率；
7. 交接可恢复率；
8. 临时文件合规率；
9. 门禁绕过次数。

计算规则：
- 只有在提供有效数据源且分母大于零时才计算比率。
- 缺少数据源、零分母或数据无法验证时返回 `UNKNOWN`，不以 0 或 100% 代替。
- 功能映射率只统计明确标记为 `critical: true` 或 `criticality: high|critical` 的功能。
- 门禁绕过只统计明确记录为 `event_type: gate.bypassed` 的审计事件。
- 报告记录生成时间、Git 分支/commit（可采集时）、来源和未知项。

## 3. 规则与发布兼容性

新增 `aimes release validate`，校验：
- `pyproject.toml` 与运行时 `__version__` 一致；
- README 标题版本与包版本一致；
- `GOVERNANCE_VERSION` 与包内核心模板文件名一致；
- 包数据配置包含模板和 Schema；
- Windows EXE 构建脚本包含 `--collect-data aimes_cli`；
- 若项目存在 `.aimes/config.yaml`，检查项目治理版本与核心路径。

该命令已加入 GitHub Actions 阻断流程，防止本轮发现的版本/资源漂移再次静默发生。

## 4. 当前验收状态

- 单元测试工作流正在对最新提交运行。
- Windows EXE 工作流正在对最新提交运行。
- 先前提交已验证文档检查基线、任务声明/交接功能以及 Windows EXE 资源打包修复；本报告中的最终结论以最新提交的两条 CI 工作流完成为准。
- 本报告不宣称真实 IDE 规则加载已通过；该项仍需在用户的实际工具会话中执行验收并保存证据。
