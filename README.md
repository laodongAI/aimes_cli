# AIMES 本地治理 CLI（V0.8.0）

AIMES CLI 是本地优先的跨 AI 开发工具工程治理配置与验证工具。它负责把 AIMES V1.2 治理核心部署到项目仓库，生成工具专属规则入口，检查配置与冲突，并输出部署状态。它不替代 Codex、Claude Code、Trae、ZCode 或 Copilot 执行开发任务。

> 当前版本是本地优先的工程治理 CLI。包版本与运行时版本由同一版本源驱动；真实 AI 工具运行时是否加载规则、行为是否改善，必须以独立验证记录为准。CI 中的 Windows EXE 构建/冒烟测试不等于 GitHub Release 或下载资产已经发布。

## 0.1 诊断后生成修复选项，并安全自动修复

`aimes repair` 默认只生成诊断和修复计划；检查选项后，显式确认才会应用可安全自动修复的配置问题：

```powershell
# 诊断并查看每项问题的根因、风险、修复选项
aimes repair --root . --format json

# 已配置项目：预览后确认执行安全修复
aimes repair --apply --confirm REPAIR --root . --format json

# 尚未配置 AIMES 的项目：必须明确指定适配器
aimes repair --apply --confirm REPAIR --tools codex-cli --root . --format json
```

该流程会在修复后复诊，并列出已解决与剩余问题。用户修改过的规则文件不会被强制覆盖；配置无法解析、清单损坏或适配器未验证时，会提供人工/引导式选项，而不是假装已修复。完整安全边界见 [诊断与安全修复指南](docs/REPAIR-LOOP.md)。

## 0. 交互式启动与 Windows 独立 EXE

在交互式终端中只输入 `aimes` 即可进入菜单，逐步选择初始化、配置、检查或验证任务。初始化向导支持多选工具，默认先预览；确认实际写入时需要输入 `YES`。原有参数命令仍然保留，适合脚本和 CI。

Windows 独立 EXE 构建和 PATH 配置请见 [`docs/WINDOWS-EXE-DEPLOYMENT.md`](docs/WINDOWS-EXE-DEPLOYMENT.md)。独立 EXE 携带 Python 运行时，不需要激活项目 `.venv`；但必须将整个发布目录放入固定位置并配置用户 PATH。当前开发环境未在 Windows 上实际构建或验证 EXE。

## 1. GitHub 根目录镜像发布（V0.7.4）

`aimes publish` 默认只预览；执行必须同时提供 `--apply --confirm PUBLISH`。完整镜像会删除远端根目录中本地不存在的文件，必须先检查删除清单。目标仓库可以是已有仓库，也可以是尚无提交的空仓库；空仓库首次发布将创建初始提交。命令排除常见凭据/私钥、虚拟环境、依赖和缓存路径，执行前扫描常见密钥样式，并使用普通非强制推送。详细边界见 [`docs/PUBLISH-GITHUB-MIRROR.md`](docs/PUBLISH-GITHUB-MIRROR.md)。

```powershell
# 推荐：交互式选择配置，先预览，再输入 PUBLISH 执行
aimes publish

# 列出或复用已保存配置
aimes publish --list-profiles
aimes publish --profile my-project

# 参数模式：可以追加排除规则并保存配置
aimes publish --source "E:\work\my-project" --repo "owner/repository" --branch main --exclude "test-data/**" --save-profile my-project
aimes publish --profile my-project --apply --confirm PUBLISH
```

默认过滤 `.venv`、`.claude`、`.codex`、`.cursor` 等环境和 AI 工具辅助目录、日志与运行时文件、构建缓存、编译产物及凭据。发布时会自动识别项目根目录中的技术栈标志文件（如 `pyproject.toml`、`package.json`、`pom.xml`、`go.mod`、`Cargo.toml`、`.csproj`），叠加相应过滤规则，并读取 `.gitignore` 中的正向排除规则。交互式向导不再询问追加排除规则；确有需要时可使用 `--exclude` 或已保存的发布配置。配置保存和完整规则见 [发布向导文档](docs/PUBLISH-GITHUB-MIRROR.md)。

## 2. 锁定的工具入口

1. Trae Code
2. VS Code + Codex
3. VS Code + Claude Code
4. VS Code + GitHub Copilot
5. ZCode
6. QCode
7. Claude Code CLI
8. Codex CLI

VS Code 插件和独立 CLI 是不同执行上下文，必须分别验证。若它们共享 `AGENTS.md` 或 `CLAUDE.md`，治理入口可以共用，但不能假设加载行为相同。

### 工程能力与验证状态

AIMES 的能力状态分为配置已生成、自动化测试通过、工具运行时已验证和真实项目试点已验收。请查看 [能力与验证状态矩阵](docs/CAPABILITY-VERIFICATION-MATRIX.md)；后续实施顺序见 [工程能力增强路线图 V0.9](docs/ROADMAP-ENGINEERING-EXCELLENCE-V0.9.md)。旧版 V0.5.3 发布报告和哈希清单已归档至 [历史发布制品](docs/archive/release-artifacts/V0.5.3/README.md)，不代表当前发布状态。

## 3. 安装（Windows PowerShell）

需要 Python 3.10+。推荐从仓库源码安装，避免复制历史版本的 wheel 文件名：

```powershell
git clone https://github.com/laodongAI/aimes_cli.git
cd aimes_cli
py -3 -m venv .venv
.\\.venv\\Scripts\\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e .
aimes --version
aimes release validate --root .
```

如果使用 GitHub Release 提供的 wheel，请安装该 Release 附带的确切版本文件，不要复用旧文档中的 `0.5.3` 文件名。正式发布状态和下载资产以 [GitHub Releases](https://github.com/laodongAI/aimes_cli/releases) 页面为准。

Windows 独立 EXE 的构建和部署说明见 [Windows EXE 部署指南](docs/WINDOWS-EXE-DEPLOYMENT.md)。EXE 需要按发布流程验证版本、资源打包和冒烟行为；不要仅凭源码测试通过就宣称用户环境已验证。

## 4. 第一次初始化

先预览，不写入：

```powershell
aimes init --tools codex-cli,claude-code --scope project --dry-run
```

确认动作后再执行：

```powershell
aimes init --tools codex-cli,claude-code --scope project
```

交互式选择工具：

```powershell
aimes init
```

## 5. 常用命令

```powershell
aimes inspect
aimes diff --tools trae-code,vscode-copilot,zcode,qcode
aimes configure --tools vscode-copilot
 aimes validate
aimes doctor
aimes status
aimes validate --format json --output .aimes/reports/validation.json
aimes docs check --root . --format json --output .aimes/reports/docs-check.json
```

`--scope` 当前仅支持 `project`。全局配置和卸载尚未实现，不应使用本版本执行全局部署。现有项目的安全升级请使用 `aimes upgrade`；它先列出文件差异，逐项确认后才写入，并保留冲突文件。

### V0.3：追溯、证据与交接

```powershell
aimes trace validate examples/traceability/trace-manifest.example.yaml
aimes evidence validate examples/evidence/evidence-registry.example.yaml
aimes context pack examples/traceability/trace-manifest.example.yaml --output-dir .aimes/context-pack
```

- `trace validate` 检查实体 ID 唯一性、追溯链接、按实体类型区分的状态词表、证据文件/引用，以及 VERIFIED 状态对应的 PASS 证据；路径字段类型错误会以结构化错误报告，不应导致 CLI 崩溃。
- `evidence validate` 校验已记录的命令/测试/构建证据，不会执行其中的命令；可校验产物存在性和 SHA-256。
- `context pack` 生成 `context-pack.json` 与 `HANDOFF.md`，记录上下文文件清单和哈希；不复制源文件、不执行项目命令。
- 示例数据中的证据是格式演示，不代表真实项目已经执行过相关命令。


### 核心规则遵循固定回归集

新增 [核心规则遵循回归集](examples/evaluation/rule-following-suite.yaml)，覆盖需求歧义、证据真实性、用户改动保护、不可信内容、修改范围、边界测试、审批门禁和代码/文档追溯。

```powershell
# 校验固定案例集结构，不调用模型
aimes evaluation validate examples/evaluation/rule-following-suite.yaml --root .

# 校验实际运行记录是否覆盖全部案例和硬门禁
aimes evaluation validate-run .aimes/evaluation/rule-following-run.json --suite examples/evaluation/rule-following-suite.yaml --root . --format json
```

`validate-run` 会拒绝缺失案例、额外案例、套件版本不匹配、缺少硬门禁或无证据的 PASS。执行步骤和验收协议见 [核心规则遵循回归测试指南](docs/RULE-FOLLOWING-REGRESSION.md)。案例集目前是测试定义，不代表已在真实 AI 工具中执行或通过。

### Token 效率与能力非退化基准

Token 优化必须先证明工程能力不退化，不能把大幅压缩提示词作为默认手段。基准方案见 [Token 效率与能力非退化基准测试方案](docs/governance-upgrade/TOKEN-EFFICIENCY-BENCHMARK-PLAN-2026-10-18.md)，固定案例集见 [token-efficiency-suite.yaml](examples/evaluation/token-efficiency-suite.yaml)。

```powershell
# 仅校验固定案例集的结构；不会调用模型或 IDE
aimes evaluation validate examples/evaluation/token-efficiency-suite.yaml
```

案例集定义了 8 类代表性任务和硬门禁，当前真实工具运行状态为 NOT_RUN。开始对照时，先记录现有规则下的 A 组基线，再一次只改变一个优化因素执行 B 组；同任务、同环境、同验收标准比较。没有平台真实 usage 时，Token 记为 UNKNOWN，不得用字符数冒充实际 Token。任何硬门禁失败或关键能力退化，都判定优化失败。

### V0.4：AI 开发准确度评测与回归

```powershell
aimes evaluation validate examples/evaluation/suite.example.yaml
aimes evaluation report examples/evaluation/run-record.example.json --format json --output .aimes/reports/evaluation-run.json
aimes evaluation compare .aimes/evaluation/baseline.json .aimes/evaluation/candidate.json --format json --output .aimes/reports/regression.json
```

- `evaluation validate` 校验版本化评测集的案例 ID、必需字段、预期结果和评分契约。
- `evaluation report` 校验已记录的运行结果，并汇总案例状态、硬门禁和诊断维度；不会运行模型、Skill 或测试命令。
- `evaluation compare` 对比基线与候选运行，标出案例增删、状态退化、硬门禁退化和诊断分数变化。硬门禁失败不能被平均分抵消。
- 每次评测应记录模型、工具、Skill 版本、案例集版本、环境和证据引用。示例运行记录仅用于演示格式，不是真实评测结论。

### V0.5：多工具验证证据与交接完整性

```powershell
aimes adapter validate examples/adapters/verification-evidence.example.yaml --format json
aimes adapter report examples/adapters/verification-evidence.example.yaml --format json
aimes context pack examples/traceability/trace-manifest.example.yaml --output-dir .aimes/context-pack
aimes context validate .aimes/context-pack/context-pack.json --handoff .aimes/context-pack/HANDOFF.md --format json
```

- `adapter validate` 校验工具规则入口验证记录。新记录使用 `schema_version: 2`；PASS 必须记录产品版本、执行模式、操作系统、规则入口、观察时间、观察者、案例 ID、AIMES CLI 版本与治理核心版本。V1 旧记录仍可读取，但缺失上下文会产生警告。
- `adapter report` 按工具和执行模式分别汇总 PASS/FAIL/BLOCKED/NOT_RUN/UNKNOWN 覆盖情况。缺少记录不等于通过或失败；静态检查文件不等于运行时已加载。
- `context validate` 对照 Context Pack 中记录的 SHA-256 检查源文件是否变化，并可检查 HANDOFF 文件是否存在。变化会提示重新审阅，不自动判断修改是否正确。
- PASS 记录必须采用运行时观察、自动化检查或用户确认的方法，并附证据文件或说明。CLI 不会自动操纵 IDE，也不会伪造运行时证据。


#### Codex CLI / Claude Code CLI 真实规则加载探针

    $probeRoot = Join-Path $env:TEMP "aimes-runtime-probe"
    New-Item -ItemType Directory -Force -Path $probeRoot | Out-Null
    aimes adapter probe create --tool codex-cli --product-version "$(codex --version)" --output-dir codex-cli --root $probeRoot
    # 在新会话中从 $probeRoot\codex-cli 启动 Codex，并把原始回复保存为 response.txt
    aimes adapter probe validate codex-cli --root $probeRoot
    aimes adapter validate codex-cli/verification-evidence.yaml --root $probeRoot

Claude Code CLI 将工具参数改为 --tool claude-code，版本填写实际 claude --version 输出，并使用 $probeRoot 下独立的 claude-code 目录。建议将探针放在业务项目之外，避免父目录规则污染结果。创建后必须在全新 CLI 会话中从探针目录启动对应工具，将 PROMPT.txt 作为用户消息，并把未修改的完整回复保存为 response.txt。AIMES 不会启动 AI 工具。探针结果只证明该工具版本/CLI 模式下的隔离规则加载行为，不代表真实项目全部治理规则有效。完整流程、安全边界和证据解释见 [运行时规则加载探针指南](docs/RUNTIME-RULE-LOADING-PROBE.md)。

### 文档完整性与薄入口检查

```powershell
# 只读检查 Markdown 本地链接、配置中的工具入口和治理核心引用
aimes docs check --root . --format json --output .aimes/reports/docs-check.json
```

- 检查本地 Markdown 链接目标是否存在，并跳过代码围栏中的示例链接与外部 URL。
- 对配置中登记的工具入口检查文件是否存在；对原生薄规则入口检查权威核心引用和行数上限（默认 40 行）。
- 手动适配说明文件只检查存在性，不会被误判为原生薄规则入口。
- 命令只读，不自动修复或删除文件；发现错误返回退出码 1。首次接入时建议先审阅报告，再决定是否作为 CI 阻断门禁。

### 活动写入者与任务交接校验

```powershell
# 检查当前项目的活动写入者声明、分支、租约和文件范围
aimes task validate --root . --format json
# 要求当前必须存在有效的活动写入者声明
aimes task validate --root . --require-active --format json

# 取得当前分支与基线提交，再声明本任务的写入范围
$branch = git branch --show-current
$base = git rev-parse HEAD
aimes task claim --task-id TASK-123 --tool-id trae-code --branch $branch --base-commit $base --allowed-path src/ --allowed-path tests/ --lease-hours 8 --confirm CLAIM

# 完成交接文件后释放写入声明
aimes task release --task-id TASK-123 --tool-id trae-code --handoff-file project-control/handoffs/2026-10-18-TASK-123-trae-code.md --confirm RELEASE
```

活动写入者声明位于 `.aimes/project-control/active-writer.yaml`，格式示例见 `examples/project-control/active-writer.example.yaml`。检查器可核对任务 ID、工具 ID、分支、基线提交、租约时间、允许修改的路径，以及基线之后的已跟踪/未跟踪变更是否越界。默认没有声明时仅提示 WARNING；使用 `--require-active` 可将缺失/过期声明作为错误。

任务交接使用独立文件，建议命名为 `project-control/handoffs/YYYY-MM-DD-TASK-<ID>-<tool>.md`，模板见 `docs/templates/TASK-HANDOFF-TEMPLATE.md`。全局 `HANDOFF.md` 仅作为索引，不应替代每个任务的实际交接记录。

**边界：** 当前 `task claim/release` 使用本地文件系统的独占创建锁来协调 AIMES 命令之间的声明更新；`task validate` 本身只读。该锁不能阻止不遵守 AIMES 协议的 IDE/编辑器直接写文件，也不应被视为跨机器分布式锁。多人/多工具并行仍应使用独立分支或 worktree，并在交接前后核验 Git 状态。

### 临时产物审计与工程指标

```powershell
# 只读审计临时产物，不删除文件
aimes cleanup audit --root . --format json --output .aimes/reports/cleanup-audit.json

# 仅使用当前可验证数据计算工程指标；缺少数据源时显示 UNKNOWN
aimes metrics report --root . --format json --output .aimes/reports/metrics.json
# 发布前检查包版本、运行时版本、README、治理核心模板和 EXE 资源收集配置
aimes release validate --root . --format json

# 提供追溯、临时产物、交接试点和审计日志数据源
aimes metrics report --root . --trace-manifest .aimes/traceability/trace-manifest.yaml --temp-registry .aimes/temp-registry.yaml --handoff-trials .aimes/evaluations/handoff-trials.yaml --audit-log .aimes/audit/events.jsonl --format json
```

- 临时登记表示例：`examples/project-control/temp-registry.example.yaml`；Schema：`schemas/temp-registry.schema.json`。
- `cleanup audit` 检查登记项是否存在、是否过期，并扫描常见未登记临时目录/文件；只输出候选和风险分类，不会删除。
- `metrics report` 对应 AIMES 核心规范的 9 项工程指标。只有在数据源可验证且分母有效时才计算比率；缺少追溯、交接试点、临时登记或审计日志时，指标显示 `UNKNOWN`，不会把缺失数据当作 0 或 100%。
- 关键功能实现/测试映射率只统计明确标记为 `critical: true` 或 `criticality: high|critical` 的功能，避免模型自行猜测关键程度。

## 5. 安全机制

- 不覆盖已有文件。
- 如果目标文件已存在且与模板冲突，保留原文件，并把建议版本写入 `.aimes/proposed/`。
- 仅在 manifest 证明文件未被用户修改时，才允许更新已有 AIMES 管理文件。
- 不执行任意 Shell 命令，不删除文件。
- ZCode、QCode 暂不猜测原生规则路径，只生成待人工确认的适配说明。
- `doctor` 对可执行文件的检测只是提示，不代表 IDE 插件存在或规则已加载。
- `validate` 通过仅代表静态配置检查通过，不代表工具运行时已遵循规则。

## 6. 初始化后目录

按选择的工具生成最小集合，例如：

```text
project/
├── AGENTS.md
├── CLAUDE.md
├── .github/copilot-instructions.md
├── .trae/rules/00-aimes-governance.md
├── .aimes/
│   ├── config.yaml
│   ├── tool-capabilities.yaml
│   ├── manifest.json
│   ├── adapters/
│   └── proposed/
└── docs/_governance/AIMES-CORE-V1.2.md
```

不是每个项目都必须生成所有文件。CLI 根据所选工具生成对应入口。ZCode/QCode 仅生成适配审查说明，直到产品版本与规则加载机制得到确认。

## 7. V0.2 新增：需求、知识、复用与 Skill 契约校验

这些命令均为只读校验，不会改写被检查的输入文件：

```powershell
aimes requirement validate examples/requirements/requirement-cognition.example.yaml --format json
aimes knowledge validate examples/knowledge/knowledge-asset.example.yaml --format json
aimes reuse validate examples/reuse/reuse-decision.example.yaml --format json
aimes skill validate examples/skills/registry.example.yaml --id SKL-CORE-REQ-001 --format json
aimes skill execution validate examples/skills/execution-record.example.yaml --root . --format json
aimes workflow validate examples/workflows/engineering-workflow.example.yaml --root . --format json
```

命令检查必填字段、AIMES 状态、重复 ID、验收条件、知识来源/成熟度证据、复用验证计划、Skill 文件存在性与项目根目录路径逃逸。Skill 注册表支持 V1/V2：V2 增加生命周期阶段、停止条件、失败恢复、完成判据、审批要求、副作用和幂等性契约；V1 继续兼容。V2 的 `VERIFIED` Skill 必须提供评测集与证据。未知字段报告为 WARNING，结构性和契约错误报告为 ERROR。

Skill V2 规范见 [`docs/SKILL-CONTRACT-V2.md`](docs/SKILL-CONTRACT-V2.md)。CI 会校验 `examples/skills/registry.example.yaml`，防止示例与验证器发生漂移。
执行记录命令 `aimes skill execution validate <path>` 校验单次 Skill 运行的工具/Skill 版本、基线、步骤、跳过原因、验收检查、输出与证据引用；Token usage 不可获取时必须记录 unavailable/null，不允许估算。记录校验不等于真实执行或结果正确。规范见 [`docs/SKILL-EXECUTION-RECORD-V1.md`](docs/SKILL-EXECUTION-RECORD-V1.md)。
声明式工作流命令 `aimes workflow validate <path>` 检查状态入口、转换引用、成功/失败路径、可达性、非重试循环与重试策略。它只验证定义，不会执行或恢复工作流。规范见 [`docs/WORKFLOW-STATE-MACHINE-V1.md`](docs/WORKFLOW-STATE-MACHINE-V1.md)。
工作流运行命令 `aimes workflow run start|validate|transition` 记录本地状态、显式审批/守卫引用、转换历史和备份；开始与转换必须确认，不覆盖既有运行记录，工作流定义哈希变化会阻止继续转换。它不会运行 AI 工具或生成外部证据。
**已实现：** V0.5 的 `adapter validate`、`adapter report`、`context validate`；V0.1 的 `init`、`configure`、`inspect`、`diff`、`validate`、`doctor`、`status`；V0.2 的 `requirement validate`、`knowledge validate`、`reuse validate`、`skill validate`；示例数据、JSON Schema、只读校验报告和自动化测试。

**尚未实现：** 自动调用模型/Agent 执行评测案例、直接读取 IDE 内部规则加载状态、自动生成可信执行证据、签名验证、全局安装、三方合并、自动卸载、回滚、自动升级策略、任务/追溯全量治理、清理命令、执行项目构建命令、AI 路由、ZCode/QCode 原生插件集成、工具运行时自动验证。

## 8. 退出码

- `0`：校验通过（允许存在 WARNING）。
- `1`：结构/治理校验发现 ERROR（V0.2 新校验命令）。
- `2`：CLI 参数、配置、文件读取或初始化操作错误；V0.1 既有命令的退出码保持兼容。

## 9. 测试

```powershell
python -m unittest discover -s tests -v
```

目前测试覆盖工具别名、dry-run、初始化与校验、原文件保护、增量配置、ZCode 手动适配和非法工具名称。发布前仍需在 Windows 本机和目标工具版本中进行真实验证。

## 10. 文档

- `docs/CLI-PRODUCT-REQUIREMENTS.md`：产品需求基线
- `docs/CLI-COMMAND-CONTRACT.md`：命令契约
- `docs/TOOL-ADAPTER-MATRIX.md`：工具适配与验证状态
- `docs/ACCEPTANCE-TEST-PLAN.md`：运行时验收计划
- `docs/INSTALL-WINDOWS.md`：Windows 部署说明
- `docs/TECHNICAL-DESIGN-BASELINE.md`：既有 CLI 技术设计基线
- `schemas/config.schema.json`：V0.1 配置 Schema
- `schemas/*-*.schema.json`：V0.2 需求认知、知识资产、复用决策与 Skill 注册表 Schema
- `examples/`：可复制的示例记录
- `skills/registry.yaml` 与 `skills/*/SKILL.md`：首批 7 个 P0 Skills 工作流模板；初始验证状态均为 `UNKNOWN`，需在真实工具/项目中评测后更新
- `docs/v1.3-design/`：AIMES V1.3 设计基线文档
- `docs/governance-upgrade/TOKEN-EFFICIENCY-DESIGN-2026-10-18.md`：Token 效率原则、上下文分层加载、指标与分阶段实施建议


## V0.5.1：提示词与 Skill 全量优化

- 七个 P0 Skills 升级为 0.2.0，增加任务专属决策分支、输入输出契约、证据状态、失败恢复和专属评测案例。
- 新增 `docs/PROMPT-SYSTEM-CONTRACT-V1.0.md` 与 `docs/SKILL-ORCHESTRATION-V1.0.md`。
- 新增 `docs/PROMPT-AUDIT-AND-OPTIMIZATION-REPORT.md` 与 14 个提示词基准案例。
- 新增案例可通过 `aimes evaluation validate examples/evaluation/prompt-optimization-suite.yaml` 进行结构校验。该命令不运行模型或真实 IDE；七个 Skill 的真实工具验证状态仍为 `UNKNOWN`。


### V0.5.2：提示词与工程运行时增强

```powershell
# 评测集结构检查
aimes evaluation validate examples/evaluation/prompt-optimization-suite.yaml --format json

# 使用预置文本夹具运行 6 个确定性词面检查（不调用模型）
aimes evaluation run-mock examples/evaluation/prompt-optimization-suite.yaml --responses examples/evaluation/mock-responses.yaml --case-id EVAL-PROMPT-ONB-001 --case-id EVAL-PROMPT-REQ-001 --case-id EVAL-PROMPT-TEST-001 --case-id EVAL-PROMPT-SEC-001 --case-id EVAL-PROMPT-REQ-002 --case-id EVAL-PROMPT-ARCH-002 --format json --output .aimes/reports/mock-evaluation.json

# 追加并检查本地审计事件
aimes audit append .aimes/audit/events.jsonl --run-id demo-001 --event-type skill.selected --status RECORDED --details-json '{"skill":"project-onboarding","api_key":"example-secret"}'
aimes audit validate .aimes/audit/events.jsonl --format json
```

Mock Runner 只验证预置响应文本的精确子串，不评估真实模型的语义质量。不要把 Mock PASS 写成真实模型评测通过。当前结构化审计需由调用方显式记录事件，尚不自动捕获所有 IDE/模型活动。


## 现有项目安全升级（V0.8.0）

AIMES 0.8.0 增加了面向已接入项目的安全升级向导。先在项目目录执行 `aimes upgrade --dry-run` 查看已安装 CLI 版本、项目清单版本和逐文件操作计划；执行 `aimes upgrade` 进入逐项确认向导。已证明未被修改的 AIMES 托管文件会在备份后更新；新文件需确认后添加；用户修改过或无法证明由 AIMES 管理的文件绝不覆盖，只可生成候选文件供人工合并。升级完成后执行 `aimes validate`。

完整策略和边界见 [`docs/SAFE-PROJECT-UPGRADE.md`](docs/SAFE-PROJECT-UPGRADE.md)。
