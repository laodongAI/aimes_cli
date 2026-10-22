## 0.8.2 - 候选规则与 Git 纳管审计

- `aimes docs check` 会报告 `.aimes/proposed/*.proposed` 中等待审核的候选文件，不会自动应用。
- 增加只读 Git 未跟踪文件审计，逐文件提示纳管或忽略决策；不会自动执行 `git add`。
- 增加候选文件保留性和 Git 未跟踪文件审计回归测试。

## 0.8.1 - 项目配置一致性诊断增强

- 扩展 `aimes docs check`：检查配置中声明的任务/交接文件是否存在，并阻止绝对路径、路径越界和符号链接逃逸。
- 检查根目录 `.env.example` 的重复环境变量赋值，报告变量名、首次声明行和重复行；只读诊断，不自动改写。
- 增加任务/交接路径缺失、路径越界及重复环境变量的回归测试。

## 0.8.0 - 安全升级与工程治理增强

- 新增现有项目安全升级流程：支持只读预览、逐文件确认、备份、冲突候选文件和失败时的恢复尝试。
- 增强工程治理检查、任务声明与交接校验、临时产物审计及工程指标报告。
- 增加上下文预算、文件选择计划、提示词输出正反例和 Token 效率评测方案。
- 明确区分配置生成、自动化测试、工具运行时验证和真实项目试点验收；未验证能力不得标记为 PASS。
- 发布声明边界：CI 通过不等于 GitHub Release/tag 或下载资产已经创建。
- 适配验证证据增加 V2 契约：PASS 需记录工具版本、执行模式、平台、案例和治理版本等上下文；报告按执行模式统计覆盖率，同时兼容读取 V1 旧记录。
- Skill 注册表增加契约 V2：显式声明生命周期、停止条件、失败恢复、完成判据、审批要求、副作用和幂等性；V1 记录保持兼容，VERIFIED 必须关联评测集与证据。
- 增加 `aimes skill execution validate`，校验单次 Skill 运行的版本、基线、步骤、跳过原因、验收检查、输出和证据；真实 Token usage 不可获取时禁止估算。
- 增加 `aimes workflow validate`，检查声明式工作流状态图、终态、失败路径、不可达状态、隐式循环和重试策略；只校验定义，不自动执行工作流。
- 增加本地工作流运行记录：显式确认后创建/转换状态，记录审批和守卫证据引用，转换前备份并原子更新；定义哈希变化时阻止继续转换。
- 新增 Codex CLI / Claude Code CLI 隔离规则加载探针：使用不泄露答案的随机 token、原始响应精确比对、入口哈希校验和 V2 证据生成；不自动启动或控制外部 AI 工具。
- 新增 `examples/evaluation/rule-following-suite.yaml`，覆盖 8 类核心治理行为；新增 `aimes evaluation validate-run`，按固定套件检查案例完整度、套件版本、硬门禁覆盖与 PASS 证据引用。
- 新增 `aimes repair` 诊断修复闭环：输出带根因、风险和选项的修复计划；通过 `--apply --confirm REPAIR` 执行安全修复；修复后自动复诊，保护用户修改并明确未解决问题。
- 新增 `aimes repair-code` 业务代码修复提案流程：统一 diff 预检、显式应用、文件哈希冲突保护、应用前备份、无 shell 测试验证、验证记录与受保护回滚。
- 新增 `aimes repair-code diagnose`：执行用户指定的测试命令并记录证据，按常见错误特征提供修复建议和后续补丁提案指引；明确区分辅助分类与根因确认。
- 新增 `aimes repair-code inspect`：只读查看提案生命周期、补丁哈希、目标文件基线冲突、关联诊断摘要与下一步建议；新增补丁篡改和工作区冲突检测测试。

## 0.7.7 - 交互确认大小写不敏感并支持错误重输

- 发布确认词 `PUBLISH` 和初始化确认词 `YES` 均不区分大小写；命令行 `--confirm` 参数也兼容混合大小写。
- 确认词输入错误时提示并重新输入；只有明确输入 `N`、`NO`、`CANCEL` 等取消词才退出确认。
- `Y/n` 预览选择接受大小写不敏感的 `Y/YES/N/NO`，其他输入会提示重试。
- 增加发布确认、错误重输和大小写兼容的回归测试。

## 0.7.6 - 自动记住上次发布配置

- 交互式发布在输入有效仓库与目录后，自动保存为“上次使用”配置，无需额外手动命名。
- 下次打开发布向导时默认选中上次使用的配置，并预填本地目录、仓库地址、分支、提交说明及排除规则。
- 保留具名发布配置，支持在向导中切换配置或新建配置。
- 增加上次使用配置的回归测试。

## 0.7.5 - 自动规避 GitHub 超大文件推送失败

- 发布扫描阶段识别接近/超过 GitHub 2 GiB 单对象限制的文件，并在提交前自动排除，避免推送阶段才出现 HTTP 422。
- 预览的排除清单会标注被跳过文件及原因，方便用户决定是否改用 Git LFS 或外部制品存储。
- 增加超大对象自动排除的回归测试。

## 0.7.4 - 支持发布到空 GitHub 仓库

- 修复目标 GitHub 仓库尚无提交时读取 `HEAD` 失败的问题。
- 预先探测远端分支与默认分支；空仓库预览时使用用户指定分支、远端声明的默认分支，或回退到 `main`。
- 空仓库的首次发布可以创建初始提交；预览报告会明确标记远端仓库尚无提交。
- 增加空远端仓库预览回归测试。

## 0.7.3 - 自动识别项目并选择镜像过滤规则

- 发布向导不再要求用户每次手工输入追加排除规则；已有配置和 `--exclude` 参数仍然可用。
- 根据项目标志文件识别 Python、Node.js、Vue、React、Java、Go、Rust、.NET、Ruby、PHP 和原生构建项目，自动选择对应的缓存/构建产物过滤规则。
- 自动读取项目根目录 `.gitignore` 中的正向排除规则，并保留内置敏感路径过滤与密钥扫描。
- 镜像预览报告显示识别出的技术栈和自动规则数量；新增检测与过滤回归测试。

# Changelog

## 0.7.2 - Case-insensitive init confirmation

- Accept `YES`, `yes`, and mixed-case variants after the initialization preview or direct-write prompt.
- Add a regression test proving lowercase `yes` proceeds to the apply phase.

## 0.7.1 - 修复初始化预览后的执行流程

- 修复交互式初始化选择预览后只输出 dry-run 报告并返回菜单、没有继续执行的问题。
- 预览完成后增加明确的 `YES` 确认；确认后重新执行正式初始化，其他输入取消且不写文件。
- 交互式向导使用当前工作目录作为操作范围，避免自动向上定位到父级 Git 仓库而误初始化父目录。
- 增加预览后确认执行及取消执行的交互测试。

## 0.7.0 - 配置式 GitHub 发布向导与扩展忽略规则

- `aimes publish` 增加交互式配置选择、预览和确认推送流程。
- 新增用户级发布配置档案，支持 `--profile`、`--save-profile`、`--list-profiles` 和重复使用的 `--exclude` 参数。
- 默认过滤 Python/Node 环境、AI 工具本地状态目录、运行时日志/PID/临时文件、构建目录和编译产物。
- 配置仅保存项目路径、仓库、分支、提交说明和排除规则，不保存 GitHub 凭据。
- 增加过滤规则、配置档案和命令参数测试。

## 0.6.0 - GitHub root mirror publishing

- Added `aimes publish` to preview and publish a local project as a complete mirror of an existing GitHub repository root.
- Added explicit `--apply --confirm PUBLISH` execution gate; preview is the default and deletion lists are included in reports.
- Added conservative exclusion of credentials, private-key files, symlinks, virtual environments, dependency folders and common caches.
- Added heuristic secret scanning, branch/repository validation, temporary-clone staging, normal non-force push, and focused unit tests.
- Added Chinese usage and safety documentation. Root mirror semantics can delete remote-only files; this is prominently documented.


## 0.5.2 - Prompt/runtime engineering hardening

- Added shared positive/negative prompt output examples and file-selection/context budget protocol.
- Added external-tool failure classification and safe degradation protocol.
- Added local JSONL audit trail primitives with sensitive-field redaction.
- Added deterministic evaluation fixture runner; it reports heuristic/fixture results and does not claim real-model evaluation.
- Added CLI command-contract regression tests and friendlier parse/schema diagnostics.
- Preserved V0.5.1 prompt assets and seven P0 Skills; added V0.5.2 protocol sections.


## 0.5.1 - Prompt and Skill optimization

- 全量修订 7 个 P0 Skills，明确输入/输出契约、证据和状态语义、任务专属失败分支、停止条件与评测案例。
- 新增提示词系统统一契约、Skill 编排协议、全量复审报告和 14 个提示词基准案例。
- Skill 注册表版本升级到 0.2.0；真实工具验证状态继续保持 UNKNOWN。
- 增加提示词评测套件结构校验与契约示例。
- 未实现自动模型/IDE 驱动，不宣称真实工具行为已验证。

## V0.5.0 — 多工具运行时验证证据与交接完整性

- 新增 `aimes adapter validate`：校验跨工具规则加载验证记录，支持 PASS/FAIL/BLOCKED/NOT_RUN/UNKNOWN。
- 新增 `aimes adapter report`：按工具汇总验证覆盖情况，不把未执行检查视为通过。
- 新增 `aimes context validate`：核对 Context Pack 源文件 SHA-256，检测打包后上下文变化，并可检查 HANDOFF 文件。
- 增加证据方法门禁：仅查看规则文件不能记录为运行时 PASS；PASS 需有运行时观察、自动化检查或用户确认，并附证据说明或文件。
- 新增 V0.5 示例和专项测试；CLI 仍不控制 IDE、不自动执行探针、不声称真实工具已经完成验证。

## V0.4.0 — AI 开发准确度评测与回归

- 新增版本化评测集校验：`aimes evaluation validate`。
- 新增已记录运行结果校验和报告：`aimes evaluation report`。
- 新增基线/候选对比：`aimes evaluation compare`，可识别状态退化、硬门禁退化、案例增删与诊断分数变化。
- 新增评测集与运行记录 JSON Schema、示例数据及自动化测试。
- 明确评测 CLI 不调用模型、不执行项目命令；分数是诊断指标，硬门禁单独报告。
- 本版本仍需在真实工具、隔离项目 fixture 和人工/独立验收流程中完成端到端试点。


## V0.3.0
- 新增 `trace validate`：校验跨实体引用、重复 ID、证据文件及 VERIFIED 证据门禁。
- 新增 `evidence validate`：校验记录的命令/测试/构建结果、退出码、产物路径与可选 SHA-256。
- 新增 `context pack`：生成 `context-pack.json` 与 `HANDOFF.md`，记录上下文文件哈希、任务状态、未决问题和风险。
- 新增 trace/evidence JSON Schema、示例数据与 5 项专项测试。
- 保留 V0.1/V0.2 命令与只读治理原则；不会执行证据中记录的命令或自动升级 VERIFIED。


## 0.1.0 — MVP prototype

- Added interactive and non-interactive project initialization.
- Added eight tool execution contexts: Trae Code, VS Code + Codex, VS Code + Claude Code, VS Code + GitHub Copilot, ZCode, QCode, Claude Code CLI, Codex CLI.
- Added shared AIMES V1.2 governance core deployment.
- Added tool-specific instruction entry templates for known paths.
- Added manual review notes for ZCode and QCode instead of guessing native rule paths.
- Added safe conflict handling: preserve existing files and stage proposals.
- Added manifest-based updates for unchanged managed files.
- Added inspect, diff, configure, validate, doctor, status.
- Added JSON output and Windows installation documentation.
- Added eight unit tests.

## Known limitations

No global deployment, automatic uninstall, rollback, three-way merge, automatic runtime rule loading detection, or actual ZCode/QCode integration. Runtime verification across the eight tool contexts remains a release gate for the next version.


## 0.2.0 - 2026-10-14

- 新增只读命令：`requirement validate`、`knowledge validate`、`reuse validate`、`skill validate`。
- 新增需求认知、知识资产、复用决策和 Skill 注册表 JSON Schema。
- 增加字段、状态、重复 ID、验收标准、成熟度证据、复用验证计划和 Skill 文件引用检查。
- 增加项目根目录路径逃逸检查；验证器不执行 Shell、不改写源文件。
- 增加示例 YAML、首个 requirement-cognition Skill 示例及 V1.3 设计文档副本。
- 保留 V0.1 既有命令与项目初始化行为；V0.2 新校验命令以退出码 1 表示治理校验失败。

- 加入首批 7 个 P0 Skill 草案及统一注册表：项目接管、需求认知、项目知识复用、变更影响分析、架构契约审查、受控实施、需求驱动测试。
- 所有 Skill 初始 `validation_status: UNKNOWN`，不声称已在真实工具中验证。

## V0.5.3 - 2026-10-16

- Added an interactive main menu when `aimes` is launched without arguments in a TTY.
- Added guided multi-tool selection for init/configure/diff; project writes require explicit `YES` confirmation when the user opts out of preview mode.
- Kept existing argument-based CLI commands for scripts and CI.
- Added Windows PyInstaller build script and deployment guidance for a standalone EXE that does not require activating a project virtual environment.
- Windows EXE build/runtime verification is not claimed until the build script is run on Windows.
