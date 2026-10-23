# AIMES CLI：AI 工程治理、验证与交付工具

**当前源码版本：0.8.7** · **治理核心：AIMES Core V1.2** · **Python：3.10+**

AIMES（AI Engineering Management & Intelligent Support）是一个**本地优先、跨 AI 编码工具的工程治理 CLI**。它把项目规则、Skills、工作流、质量门禁和验证证据组织成可部署、可检查、可追溯的工程机制，帮助 AI 工具更稳定地完成需求分析、产品设计、架构、编码、测试、文档、交接、版本管理和发布工作。

AIMES **不是大模型，也不替代 IDE、Agent 或 AI 编码工具**。它负责准备和验证治理环境、维护本地流程、检查证据和保护写入边界；具体的需求分析、代码生成和 UI 操作仍由用户选择的 AI 工具及其运行时完成。

> **重要边界：**规则/Skill 已部署、CLI 自动化测试通过、AI 工具运行时确实加载规则、真实项目试点达到预期，是四种不同状态。AIMES 不会仅凭文件存在就宣称模型已执行规则，也不会把示例数据或未运行的测试报告为 PASS。

## 目录

- [1. AIMES 解决什么问题](#1-aimes-解决什么问题)
- [2. 全部能力总览](#2-全部能力总览)
- [3. 支持的工具与部署范围](#3-支持的工具与部署范围)
- [4. 安装方式](#4-安装方式)
- [5. 第一次部署到项目](#5-第一次部署到项目)
- [6. 日常使用流程](#6-日常使用流程)
- [7. 命令能力索引](#7-命令能力索引)
- [8. Skills 与任务编排](#8-skills-与任务编排)
- [9. 安全模型与操作边界](#9-安全模型与操作边界)
- [10. 测试、评测与运行时验证](#10-测试评测与运行时验证)
- [11. 构建、打包与发布](#11-构建打包与发布)
- [12. 开发者指南与仓库结构](#12-开发者指南与仓库结构)
- [13. 常见问题](#13-常见问题)
- [14. 文档导航](#14-文档导航)
- [15. 当前限制与路线图](#15-当前限制与路线图)

---

## 1. AIMES 解决什么问题

多种 AI 编码工具可以提高开发速度，但项目知识、规则入口、验证方式和交接记录经常散落在不同文件和会话中，容易产生以下问题：

- AI 未先理解项目和业务目标，就直接给出 Spec 或修改代码。
- 项目规则已经写入，却不知道具体工具是否加载、是否按规则行动。
- 多个工具连续开发时，缺少统一基线、允许修改范围和交接记录。
- 测试、构建和评测结果缺少可核验的证据，容易把“计划执行”误报为“已经通过”。
- 升级治理文件时覆盖项目自定义内容。
- Token 优化只关注提示词变短，没有验证工程质量是否退化。
- 发布代码时遗漏文件，或误上传密钥、缓存、虚拟环境和大文件。
- 临时 AI 产物持续累积，却缺少登记、审计和清理决策。

AIMES 以本地项目为中心，为这些活动提供可复用的治理入口和证据协议。目标不是让每个项目都堆积大量说明，而是让 AI 工具在适当任务中找到正确的规则、Skill、知识、门禁和交接约定。

## 2. 全部能力总览

### 2.1 项目治理配置与工具适配

- 初始化项目级 AIMES 治理配置，支持预览、显式确认和多工具选择。
- 为不同 AI 工具生成相应的薄规则入口，并引用统一的 AIMES Core。
- 为已部署项目增加工具适配器，尽可能保留已有文件和用户自定义内容。
- 检查配置、规则入口、文件冲突、工具可用性和部署状态。
- 安全升级既有项目治理文件，对版本差异、缺失文件、定制文件和冲突给出报告。
- 审计项目 AIMES 版本与托管文件一致性。
- 检查 Markdown 本地链接、工具入口和治理核心引用。
- 输出文本或 JSON 报告，供人工检查或 CI 集成。

### 2.2 产品分析、需求、知识复用与 Skill 路由

AIMES Core 和 Skill 资产定义了面向任务的治理路线，包括：

- 项目接管、基线确认和项目知识分析。
- 产品经理分析：用户问题、业务目标、用户价值、现有能力、复用机会、缺口、范围和方案取舍。
- 需求认知与验收标准。
- 项目知识资产与复用决策记录。
- 变更影响分析、架构与契约审查。
- 受控实施、需求驱动测试和交接。
- UI 设计、设计系统治理、UI 质量审查与实现验证。
- 提示词和开发引导词生成：涉及产品判断时先分析项目知识；只要求改写已有提示词且不涉及产品判断时，才可直接优化表达。

Skill 注册表和工作流定义可进行结构校验。**注册、部署或静态路由不等于目标 AI 工具已在运行时调用 Skill**；运行时行为仍需要对应工具、版本和执行模式的实际证据。

### 2.3 诊断与安全修复闭环

- 治理问题诊断：生成问题、根因、风险、修复选项和修复后复诊结果。
- 业务代码修复提案：对 AI 编码工具生成的补丁进行检查、提案、应用、测试验证和受保护回滚。
- 补丁应用前检查修改范围和基线，保存备份；发现冲突时阻止盲目覆盖。
- 测试命令以参数数组运行，不通过 Shell 拼接执行。
- 修复计划不等于已经修改代码；业务代码补丁需要先由开发者或 AI 工具生成。

### 2.4 任务写入权、工作流和交接

- 声明当前任务的写入工具、分支、基线提交、允许修改路径和租约。
- 检查活动写入者声明、租约状态和变更范围。
- 为多工具交接建立独立 HANDOFF 记录。
- 校验声明式工作流状态、转换、终态、失败路径和重试策略。
- 记录本地工作流运行状态；状态转换需要显式确认，并记录审批、守卫和证据引用。
- 生成 Context Pack 与 HANDOFF，记录源文件清单和 SHA-256；验证源文件是否发生变化。
- 本地写入锁只能协调遵守 AIMES 协议的命令，不能阻止 IDE 或其他程序直接写文件，也不是跨机器分布式锁。

### 2.5 追溯、证据、审计和工程指标

- 校验需求、功能、实现、测试、缺陷和发布等实体之间的追溯关系。
- 校验证据注册表，包括记录的命令、测试、构建结果、产物路径和哈希。
- 校验 Skill 执行记录，包括输入基线、执行步骤、跳过原因、验收检查、输出和证据。
- 校验多工具规则加载验证证据，并生成覆盖率报告。
- 追加和校验本地 JSONL 审计事件。
- 审计临时产物登记、过期项和未登记候选；只报告，不自动删除。
- 生成工程指标报告：只有数据源可验证且分母有效时才计算；缺失数据保持 UNKNOWN，不把未知当作 0 或 100%。

### 2.6 AI 开发行为评测与 Token 效率

- 版本化评测集结构校验。
- 运行记录完整性、案例覆盖和硬门禁覆盖校验。
- 基线与候选运行对比，检查案例增删、状态退化和硬门禁退化。
- 固定 fixture 的确定性模拟检查，不调用真实模型。
- Token 效率基准设计：在同任务、同环境、同验收标准下比较优化前后，并要求能力不退化。
- 当平台未提供真实 Token usage 时，用量必须标记为 UNKNOWN；不得以字符数冒充 Token。

### 2.7 GitHub 镜像发布与发布前检查

- 交互式发布向导和可复用的发布配置档案。
- 发布前生成完整镜像计划和删除清单；默认预览，执行时要求显式确认。
- 支持向已有仓库发布，也支持首次发布到空仓库。
- 根据项目技术栈和 .gitignore 叠加过滤规则。
- 默认排除常见凭据、私钥、虚拟环境、依赖目录、AI 工具本地状态、缓存、日志、编译产物和大文件。
- 执行前扫描常见密钥模式，并使用普通非强制推送。
- 发布前校验包版本、运行时版本、README、治理核心模板和 EXE 资源收集配置。

**警告：**完整镜像发布可能删除远端存在、但本地不存在的文件。务必审阅预览和删除清单；不要在未理解差异的情况下执行发布。

### 2.8 Windows 独立 EXE

- 提供 Windows 原生构建脚本与部署指南。
- EXE 包含 Python 运行时，可在没有激活项目虚拟环境的情况下调用。
- 发布时需要整体复制 EXE 及其依赖文件所在目录，不能只复制单个 aimes.exe。
- Windows EXE 的真实构建和冒烟状态应以对应 GitHub Actions 运行记录为准；CI 成功不自动意味着 GitHub Release 已创建或下载资产已上传。

## 3. 支持的工具与部署范围

### 3.1 工具适配器

| 适配器 ID | 目标工具/执行上下文 |
|---|---|
| trae-code | Trae Code |
| vscode-codex | VS Code + Codex 扩展 |
| vscode-claude-code | VS Code + Claude Code 扩展 |
| vscode-copilot | VS Code + GitHub Copilot |
| zcode | ZCode |
| qcode | QCode |
| claude-code | Claude Code CLI |
| codex-cli | Codex CLI |
| chatgpt-work | ChatGPT Work |

不同 IDE 扩展与独立 CLI 属于不同执行上下文。即使共用 AGENTS.md 或 CLAUDE.md，也必须分别验证规则加载与行为。ZCode/QCode 等工具若缺乏可靠的原生规则路径信息，AIMES 会保留人工确认边界，不会猜测并宣称已集成。

### 3.2 部署范围

当前支持**项目级配置**。--scope 只接受 project。全局部署、自动卸载、通用三方合并和自动控制 IDE/Agent 尚不属于当前保证能力。

---

## 4. 安装方式

### 4.1 环境要求

- Python 3.10 或更新版本。
- Git。
- Windows 用户建议使用 PowerShell；macOS/Linux 可使用对应 Shell。
- 使用 AI 工具适配器时，需要自行安装并登录对应工具。
- 构建 Windows EXE 必须在 Windows 环境执行构建脚本。

### 4.2 方式 A：从源码安装（推荐用于开发和验证）

Windows PowerShell：

~~~powershell
git clone https://github.com/laodongAI/aimes_cli.git
cd aimes_cli

py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1

python -m pip install --upgrade pip
python -m pip install -e .

aimes --version
aimes --help
aimes release validate --root .
~~~

如果 PowerShell 的执行策略阻止激活脚本，可以仅为当前终端临时放宽策略，或直接使用虚拟环境中的 Python/命令路径；不要为此修改系统级策略。

macOS/Linux：

~~~bash
git clone https://github.com/laodongAI/aimes_cli.git
cd aimes_cli

python3 -m venv .venv
source .venv/bin/activate

python -m pip install --upgrade pip
python -m pip install -e .

aimes --version
aimes --help
aimes release validate --root .
~~~

可编辑安装适合开发；源码变化会反映到当前环境，但它不是独立可分发制品。

### 4.3 方式 B：安装构建好的 Python 包

先打开 [GitHub Releases](https://github.com/laodongAI/aimes_cli/releases)，确认确实存在对应版本的 Release 和资产，再按该 Release 提供的文件名安装。例如，只有在已下载对应 wheel 文件后才执行：

~~~powershell
python -m pip install .\aimes_governance_cli-<实际版本>-py3-none-any.whl
aimes --version
~~~

不要猜测 wheel 文件名或复用旧版本资产。若 Releases 页面没有对应资产，请使用源码安装或按第 11 节自行构建。

### 4.4 方式 C：Windows 独立 EXE

独立 EXE 不要求在业务项目中激活 .venv，但需要取得完整目录并配置 PATH。详细步骤见 [Windows EXE 构建与部署指南](docs/WINDOWS-EXE-DEPLOYMENT.md)。

- 只在 Windows 上构建 Windows EXE。
- 将整个 dist-exe\aimes\ 目录复制到稳定路径，例如 %LOCALAPPDATA%\Programs\AIMES\。
- 将该目录加入当前用户的 PATH。
- 重新打开 PowerShell，运行 Get-Command aimes.exe 与 aimes.exe --version。
- 若要直接输入 aimes，确认 Windows 命令解析能找到 aimes.exe。

---

## 5. 第一次部署到项目

以下假设目标项目是 E:\work\my-project。先进入**目标项目**目录，而不是 AIMES CLI 源码仓库目录：

~~~powershell
cd E:\work\my-project
~~~

### 第一步：检查现状

~~~powershell
aimes inspect --root .
aimes status --root .
aimes doctor --root .
aimes version-audit --root .
~~~

尚未部署 AIMES 的项目可能提示缺少配置；这是诊断结果，不代表 CLI 安装失败。

### 第二步：预览部署计划

~~~powershell
aimes init --tools trae-code,codex-cli,claude-code --scope project --dry-run --root .
~~~

将工具 ID 替换成你实际使用的适配器。一次初始化可以配置多个适配器。

### 第三步：执行初始化

~~~powershell
aimes init --tools trae-code,codex-cli,claude-code --scope project
~~~

交互式初始化会给出计划并要求确认。也可以直接运行 aimes，通过菜单选择工具。对已有项目，AIMES 会尽量保留现有文件；存在冲突时应审阅候选文件，不要直接覆盖用户内容。

### 第四步：检查结果

~~~powershell
aimes validate --root .
aimes status --root .
aimes docs check --root . --format json --output .aimes/reports/docs-check.json
aimes skill validate .aimes/skills/registry.yaml --root . --format json
~~~

### 第五步：在目标 AI 工具中做真实试点

开启一个新会话，执行一个范围明确、可验证的代表性任务，并记录：

1. 实际读取了哪些治理入口、项目知识文件和 Skill 文件。
2. 是否先完成项目理解、需求/产品分析和复用分析。
3. 是否遵循修改范围、审批、测试和文档要求。
4. 哪些检查实际执行，哪些未执行或被阻塞。
5. 原始输出、工具版本、执行模式和时间等证据。

不要仅因为 .aimes/skills/ 中存在文件、规则文件引用了 Core，或模型在回复中提到了某条规则，就判定运行时加载验证通过。

---

## 6. 日常使用流程

### 6.1 查看部署和诊断问题

~~~powershell
aimes
aimes inspect
aimes status
aimes doctor
aimes validate
aimes diff --tools trae-code,vscode-copilot,zcode,qcode
~~~

在交互式终端直接输入 aimes 会打开菜单；无参数的非交互环境会显示帮助信息。doctor 主要检查本机工具可执行程序是否可用，不会证明 AI 工具已经读取项目规则。

### 6.2 安全升级治理文件

~~~powershell
aimes version-audit --root .
aimes upgrade --dry-run --root .
~~~

检查每项动作、冲突和自定义文件之后，再执行交互式升级：

~~~powershell
aimes upgrade --root .
~~~

脚本/非交互模式需要明确授权：

~~~powershell
aimes upgrade --apply --confirm UPGRADE --root .
aimes validate --root .
aimes version-audit --root .
~~~

aimes upgrade 更新的是**目标项目中的 AIMES 管理文件**，不会更新你安装的 CLI 程序。更新 CLI 和升级项目治理配置是两件事。

### 6.3 诊断后安全修复

~~~powershell
# 只生成诊断和修复计划
aimes repair --root . --format json

# 复核计划后，才执行支持的安全修复
aimes repair --apply --confirm REPAIR --root . --format json
~~~

如果目标项目尚未配置 AIMES，需要显式指定工具，例如 --tools codex-cli。无法安全自动修复的问题会保留为待处理项，而不是强行覆盖文件。

### 6.4 受控业务代码修复

~~~powershell
# 运行指定测试/诊断命令并记录结果（示例为 unittest）
aimes repair-code diagnose --id diag-001 --test-argv-json '["python","-m","unittest","discover","-s","tests"]' --root . --format json

# 对候选补丁做只读检查并保存提案，不直接修改业务文件
aimes repair-code propose candidate.patch --id fix-001 --finding TEST-42 --root . --format json
aimes repair-code inspect fix-001 --root . --format json

# 人工审阅提案后，显式应用、验证；必要时回滚
aimes repair-code apply fix-001 --confirm APPLY-FIX --root . --format json
aimes repair-code verify fix-001 --test-argv-json '["python","-m","unittest","discover","-s","tests"]' --root . --format json
aimes repair-code rollback fix-001 --confirm ROLLBACK-FIX --root . --format json
~~~

请将示例测试命令替换成项目实际命令。补丁文件必须由开发者或 AI 工具先生成；AIMES 不会自动调用模型生成业务代码补丁。

### 6.5 GitHub 发布（完整镜像）

~~~powershell
# 先打开向导，默认预览
aimes publish

# 查看保存的配置
aimes publish --list-profiles

# 参数方式：先预览
aimes publish --source "E:\work\my-project" --repo "owner/repository" --branch main

# 确认检查删除清单和过滤结果后再应用
aimes publish --source "E:\work\my-project" --repo "owner/repository" --branch main --apply --confirm PUBLISH
~~~

完整镜像语义、排除规则、凭据扫描、空仓库和风险边界见 [GitHub 镜像发布指南](docs/PUBLISH-GITHUB-MIRROR.md)。

---

## 7. 命令能力索引

命令参数以当前安装版本的 aimes --help 和各子命令的 --help 为准。常见命令按用途分组如下。

| 命令 | 用途 | 是否会写入/执行 |
|---|---|---|
| init / configure | 初始化项目治理、添加工具适配器 | 可能写项目文件；支持预览 |
| inspect / status / diff | 检查项目、状态和部署差异 | 只读/预览 |
| validate / doctor | 配置校验、本机工具可用性检查 | 只读 |
| version-audit | 检查 CLI/项目版本及托管文件一致性 | 只读 |
| upgrade | 安全升级目标项目中的治理文件 | 预览后按确认写入 |
| repair | 诊断治理问题并应用已支持的安全修复 | 默认只规划；应用需确认 |
| repair-code | 业务补丁诊断、提案、应用、验证、回滚 | 按子命令和确认执行 |
| publish | 将本地目录镜像发布到 GitHub | 默认预览；应用需确认 |
| requirement validate | 校验结构化需求认知记录 | 只读 |
| knowledge validate | 校验项目知识资产记录 | 只读 |
| reuse validate | 校验知识/能力复用决策记录 | 只读 |
| skill validate | 校验 Skill 注册表与引用文件 | 只读，不执行 Skill |
| skill execution validate | 校验单次 Skill 执行记录 | 只读，不执行 Skill |
| workflow validate | 校验声明式工作流定义 | 只读，不执行工作流 |
| workflow run | 创建、校验和推进本地工作流运行记录 | 写记录时需确认 |
| task validate/claim/release | 写入者声明、范围检查和任务交接 | claim/release 需确认 |
| trace validate / evidence validate | 追溯与证据注册表校验 | 只读，不执行已记录命令 |
| context pack/validate | 生成/校验 Context Pack 与 HANDOFF | pack 会生成文件 |
| adapter validate/report/probe | 验证证据检查、覆盖报告、CLI 规则加载探针 | probe 创建文件；不会启动 IDE |
| evaluation validate/validate-run/report/compare/run-mock | 评测集、运行记录、对比与 fixture 检查 | 不调用真实模型 |
| audit append/validate | 本地 JSONL 审计事件 | append 会追加记录 |
| docs check | 检查 Markdown 链接和规则入口 | 只读 |
| cleanup audit | 临时产物审计 | 只读，不删除 |
| metrics report | 基于可验证数据生成工程指标 | 只读 |
| release validate | 发布前版本和资源兼容检查 | 只读 |

### 报告输出

许多命令支持 --format text（默认）、--format json 和 --output PATH。例如：

~~~powershell
aimes validate --root . --format json --output .aimes/reports/validation.json
aimes metrics report --root . --format json --output .aimes/reports/metrics.json
aimes release validate --root . --format json
~~~

不是每个子命令都拥有相同参数；请先查阅具体子命令帮助。

---

## 8. Skills 与任务编排

AIMES 不建议每个任务都加载所有 Skill。应根据任务类型选择必要流程，并记录跳过理由。

| 任务类型 | 建议的治理路线 |
|---|---|
| 新项目/新会话/跨工具交接 | 项目接管 → 基线和知识梳理 → 选择后续 Skill |
| 新功能、模糊需求、产品构想 | 项目接管 → 产品经理分析 → 需求认知 → 知识复用 → 影响分析 → 按需架构审查 → 获批准后实施 → 测试 |
| Bug 修复 | 需求/预期行为澄清（需要时）→ 知识复用 → 影响分析 → 受控修复 → 测试 |
| 重构/依赖升级 | 项目接管 → 知识复用 → 影响分析 → 按需架构审查 → 批准后实施和验证 |
| 生成开发引导词 | 项目知识分析 → 产品判断 → 缺口/范围/方案 → 完整可复制引导词 → 验收与验证建议 |
| 纯提示词改写 | 若不涉及产品判断，可直接进入提示词优化 |
| UI 设计/设计系统调整 | frontend-design、design-system-governance、ui-quality-review、ui-implementation-validation 按触发条件选择 |
| 测试设计或发布验证 | 需求/验收来源确认 → 测试设计 → 执行证据 → 状态和缺口报告 |

规范见 [Skill 编排协议](docs/SKILL-ORCHESTRATION-V1.0.md) 和 [UI 设计治理](docs/UI-DESIGN-GOVERNANCE.md)。

### 产品经理优先路由的关键要求

当用户要求“出引导词”“生成下一步 AI 任务指令”“基于当前项目知识提出下一步计划”时，不能因为请求提到代码或 Spec 就直接跳到技术勘察。应先：

1. 列出实际读取的项目知识来源与路径。
2. 区分已证实事实、推断、未知和冲突。
3. 分析用户问题、业务目标、用户价值、当前能力、复用机会、缺口和不做的范围。
4. 选择适当 Skill 并解释触发/跳过理由。
5. 生成完整可复制的任务引导词，包含输入、边界、交付物、验收标准和验证步骤。

若用户只要引导词，不应顺带修改项目代码。目标 AI 工具未提供真实读取证据时，不得声称某个 Skill 已在运行时成功加载。

---

## 9. 安全模型与操作边界

AIMES 的安全设计以“先观察、先预览、显式确认、保护用户内容、记录证据”为原则：

- **项目级优先：**当前只支持 project scope，不会自动部署全局规则。
- **保留用户修改：**已有文件与模板冲突时保留原文件，并在适当情况下生成候选文件；升级时通过托管清单和文件状态决定是否能更新。
- **预览优先：**初始化、升级、发布和修复均有预览/计划路径。
- **显式确认：**发布、升级、补丁应用、回滚、任务声明和工作流状态转换等写操作需要相应确认词或交互确认。
- **路径边界：**检查路径越界和相关符号链接逃逸风险。
- **不执行证据中的命令：**证据注册表只是校验记录，不会因为存在命令字符串就执行命令。
- **补丁边界：**受控代码修复会检查补丁目标和基线，应用前备份，并在允许条件下验证/回滚。
- **发布防护：**常见凭据路径过滤、密钥样式扫描、技术栈过滤和删除清单预览。
- **诚实状态：**NOT_RUN、UNKNOWN、BLOCKED 和 FAIL 不会被自动解释成 PASS。

AIMES 不能保证发现所有秘密、阻止不遵守协议的 IDE 直接写入、替代 Git 权限管理，或为本地 JSONL 日志提供不可篡改保证。重要操作仍需审阅 diff、Git 状态和实际证据。

---

## 10. 测试、评测与运行时验证

### 10.1 运行本项目自动化测试

在源码仓库根目录执行：

~~~powershell
python -m pip install -e .
python -m pip install pytest
python -m pytest
~~~

检查包元数据和当前治理资源：

~~~powershell
aimes release validate --root .
aimes docs check --root . --format json
~~~

### 10.2 评测套件与回归

~~~powershell
# 校验固定评测集结构
aimes evaluation validate examples/evaluation/rule-following-suite.yaml --root .
aimes evaluation validate examples/evaluation/token-efficiency-suite.yaml --root .

# 校验某次真实运行记录是否覆盖固定套件
aimes evaluation validate-run .aimes/evaluation/rule-following-run.json --suite examples/evaluation/rule-following-suite.yaml --root . --format json

# 对比基线与候选运行记录
aimes evaluation compare .aimes/evaluation/baseline.json .aimes/evaluation/candidate.json --root . --format json
~~~

结构校验通过只说明评测数据符合格式；run-mock 只使用固定 fixture，不代表真实 AI 工具的表现。

### 10.3 Codex CLI / Claude Code CLI 规则加载探针

AIMES 提供隔离探针来验证特定 CLI 版本的原生规则加载行为。创建探针不会启动 AI 工具；需要用户在全新会话中手动启动工具、提交提示词并保存原始回复，再运行验证命令。

~~~powershell
$probeRoot = Join-Path $env:TEMP "aimes-runtime-probe"
New-Item -ItemType Directory -Force -Path $probeRoot | Out-Null

aimes adapter probe create --tool codex-cli --product-version "$(codex --version)" --output-dir codex-cli --root $probeRoot
# 在全新 Codex 会话中，从探针目录启动工具；按探针提示提交 PROMPT.txt，并保存完整原始回复。
aimes adapter probe validate codex-cli --root $probeRoot
aimes adapter validate codex-cli/verification-evidence.yaml --root $probeRoot
~~~

Claude Code CLI 将工具参数改为 claude-code，版本填写实际 claude --version 输出。请按命令帮助确认输出目录参数的相对路径语义。探针只证明该工具版本和 CLI 执行模式下的隔离规则加载行为，不代表其他 IDE 插件或整个项目的全部治理能力。

### 10.4 验证状态定义

| 状态层级 | 能证明什么 | 不能证明什么 |
|---|---|---|
| 配置已生成 | 规则、Skill 或配置文件已写入目标项目 | 工具一定会读取 |
| 自动化测试通过 | 对应测试覆盖的 CLI 逻辑通过 | 所有工具运行时行为正确 |
| 运行时已验证 | 特定工具版本/执行模式有可复核的加载证据 | 其他版本、模式和项目都有效 |
| 真实项目试点验收 | 指定项目和任务的验收标准通过 | 所有未来任务都必然成功 |

详见 [能力与验证状态矩阵](docs/CAPABILITY-VERIFICATION-MATRIX.md)。评测套件是测试定义，不是自动产生的成功结论。

---

## 11. 构建、打包与发布

### 11.1 从源码运行与测试

~~~powershell
git clone https://github.com/laodongAI/aimes_cli.git
cd aimes_cli
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e .
python -m pip install pytest
python -m pytest
~~~

### 11.2 构建 Python wheel 和源码包

在源码环境中执行：

~~~powershell
python -m pip install --upgrade build
python -m build
~~~

构建结果位于 dist/，通常包含 wheel 和 source distribution。构建成功不代表已上传到 PyPI 或 GitHub Release。请检查文件名、版本和内容，再按项目发布流程分发。

### 11.3 构建 Windows EXE

必须在 Windows 主机或 Windows CI runner 上执行：

~~~powershell
Set-ExecutionPolicy -Scope Process Bypass
.\build_windows_exe.ps1
~~~

输出目录通常为 dist-exe\aimes\。请整体分发该目录，不要只复制 aimes.exe。完整 PATH、启动目录语义和故障排查见 [Windows EXE 部署指南](docs/WINDOWS-EXE-DEPLOYMENT.md)。

### 11.4 发布前校验

~~~powershell
aimes release validate --root .
python -m pytest
git status --short
git diff --check
~~~

发布前确认：

- src/aimes_cli/__init__.py 中的版本与项目元数据、模板和文档一致。
- README 中的安装命令、命令示例和文档链接仍有效。
- 测试在目标平台实际运行并有结果。
- 若本次发布包含 EXE，必须在 Windows 环境实际构建，并通过仓库外冒烟测试。
- Git 标签、GitHub Release 和下载资产只有在实际创建/上传后才可宣称已发布。

### 11.5 GitHub Actions

仓库包含自动化检查工作流。每次改动应查看对应提交的 Actions 运行结果；Linux 单元测试与 Windows EXE 构建/冒烟测试是不同工作项。CI 通过不能替代真实 IDE/CLI 的规则加载试点，也不意味着已创建 Release。

---

## 12. 开发者指南与仓库结构

### 12.1 主要目录

| 路径 | 内容 |
|---|---|
| src/aimes_cli/ | CLI 入口、治理逻辑、校验器、修复/发布/评测模块 |
| src/aimes_cli/templates/ | 初始化时部署到目标项目的治理 Core、规则入口和 Skill 模板 |
| src/aimes_cli/schemas/ | 结构化数据的 JSON Schema |
| skills/ | AIMES 源码仓库内的 Skill 资产 |
| docs/ | 部署、治理协议、运行时验证、安全边界与路线图 |
| examples/ | 评测套件、证据、追溯、工作流和配置示例 |
| tests/ | CLI、治理规则、文件安全、评测和回归测试 |
| build_windows_exe.ps1 | Windows 独立 EXE 构建脚本 |
| pyproject.toml | Python 包元数据、入口点、依赖与测试配置 |
| CHANGELOG.md | 版本变化记录 |

### 12.2 本地开发约定

- 以 main 为集成主干；具体分支和 PR 以仓库当前协作约定为准。
- 规则、Skill、Schema、模板和测试应同步更新，避免只改文档或只改运行代码。
- 新增命令时同步更新帮助信息、测试、README 和必要的专项文档。
- 涉及真实 AI 工具行为时，区分静态测试和运行时验证，保存可复核证据。
- 不在文档中将计划中的功能描述为已实现；不将未执行的检查写成 PASS。
- 对有破坏性的写入操作，默认预览并要求明确确认。

### 12.3 建议的开发验证顺序

~~~powershell
python -m pytest
aimes docs check --root . --format json
aimes release validate --root .
git diff --check
~~~

如涉及 Windows EXE，再执行 Windows 构建与仓库外冒烟测试；如涉及工具适配器或 Skill 路由，再执行目标工具的真实运行时试点。

---

## 13. 常见问题

### Q1：安装 AIMES 后，AI 工具就会自动遵守所有规则吗？

不会。安装 CLI、把配置部署到项目、目标工具加载规则、模型按规则行动，是不同环节。请先初始化和验证配置，再通过目标工具的真实会话进行试点，并记录工具版本、执行模式、读取路径和原始证据。

### Q2：升级项目时会覆盖我的 CLAUDE.md 或 AGENTS.md 吗？

AIMES 设计为保留用户内容；冲突时通常保留原文件并生成候选文件供审阅。仍应先运行 aimes upgrade --dry-run，检查每个文件的计划，再决定是否执行。

### Q3：aimes upgrade 会升级 CLI 程序吗？

不会。它升级的是当前目标项目里的 AIMES 管理文件。CLI 本身需要通过重新安装对应包或替换为经验证的独立 EXE 来更新。

### Q4：可以全局安装规则吗？

当前版本的初始化范围仅支持项目级 --scope project。不要将它当作已经支持全局部署或自动卸载的工具。

### Q5：为什么某些指标显示 UNKNOWN？

因为缺少可验证数据源、有效分母或真实运行记录。UNKNOWN 表示当前无法判断，不等于失败，也绝不等于通过。

### Q6：evaluation validate 会调用大模型吗？

不会。它校验评测集结构。evaluation report 和 compare 分析已有运行记录，run-mock 使用固定 fixture。真实模型评测必须由实际执行过程产生运行记录和证据。

### Q7：adapter probe 会自动启动 Codex 或 Claude Code 吗？

不会。它只创建或校验隔离探针文件；用户需要手动在新会话中运行目标 CLI 并保存原始回复。

### Q8：为什么 Windows EXE 在一台电脑能运行，另一台不行？

PATH、依赖目录是否完整、Windows 版本、执行策略、杀毒软件和企业应用控制都可能影响启动。先确认分发的是完整目录，使用 Get-Command aimes.exe 检查 PATH，再按 Windows EXE 部署指南排查。

### Q9：GitHub Actions 通过是否代表正式版本已经发布？

不代表。CI 通过只证明该工作流中的检查成功。Git 标签、GitHub Release 和下载资产需要分别确认。

### Q10：GitHub 镜像发布为什么会列出删除文件？

因为镜像目标是让远端根目录与本地纳入发布的文件保持一致。远端有而本地没有的文件可能被删除。必须审阅删除清单；如不接受该语义，不要执行发布。

---

## 14. 文档导航

| 文档 | 适用场景 |
|---|---|
| [变更记录](CHANGELOG.md) | 查看各版本新增、修改和已知限制 |
| [能力与验证状态矩阵](docs/CAPABILITY-VERIFICATION-MATRIX.md) | 区分配置、自动化测试、运行时验证和项目试点 |
| [工程能力增强路线图 V0.9](docs/ROADMAP-ENGINEERING-EXCELLENCE-V0.9.md) | 查看后续能力建设方向 |
| [Skill 编排协议](docs/SKILL-ORCHESTRATION-V1.0.md) | 任务路由、Skill 顺序、跳过条件和交接要求 |
| [UI 设计治理](docs/UI-DESIGN-GOVERNANCE.md) | UI 专项 Skill 和验证流程 |
| [诊断与安全修复指南](docs/REPAIR-LOOP.md) | 治理问题诊断、修复计划与安全边界 |
| [业务代码修复提案指南](docs/CODE-REPAIR-PROPOSALS.md) | 补丁提案、应用、验证和回滚 |
| [GitHub 镜像发布指南](docs/PUBLISH-GITHUB-MIRROR.md) | 发布预览、过滤规则、凭据扫描和删除风险 |
| [Windows EXE 构建与部署](docs/WINDOWS-EXE-DEPLOYMENT.md) | Windows 构建、PATH 配置和运行方式 |
| [运行时规则加载探针指南](docs/RUNTIME-RULE-LOADING-PROBE.md) | Codex CLI/Claude Code CLI 隔离规则加载验证 |
| [核心规则遵循回归测试指南](docs/RULE-FOLLOWING-REGRESSION.md) | 固定案例、硬门禁与运行记录验收 |
| [Token 效率与能力非退化基准](docs/governance-upgrade/TOKEN-EFFICIENCY-BENCHMARK-PLAN-2026-10-18.md) | Token 优化的对照测试和非退化原则 |
| [历史发布制品归档](docs/archive/release-artifacts/V0.5.3/README.md) | 历史版本材料，不代表当前发布状态 |

---

## 15. 当前限制与路线图

当前明确的限制包括：

- 不替代大模型、IDE、Agent，也不自动控制所有外部工具。
- 不保证所有 AI 工具、所有版本、所有模式都自动加载同一组规则。
- 全局部署、自动卸载和通用三方合并尚未实现。
- 本地写入者声明不能约束不遵守协议的外部编辑器，也不是跨机器分布式锁。
- 评测和指标只根据实际记录与可验证数据工作；缺失证据不会被推断为通过。
- 常见密钥扫描和过滤规则有帮助但不保证发现所有敏感信息；发布前仍需人工检查差异。
- Windows EXE 构建/冒烟测试、正式 Release 资产和真实工具运行时试点应分别确认。

路线图和当前验证状态请以 [能力与验证状态矩阵](docs/CAPABILITY-VERIFICATION-MATRIX.md)、[工程能力增强路线图](docs/ROADMAP-ENGINEERING-EXCELLENCE-V0.9.md) 和 GitHub Actions / Releases 页面为准。

## 许可证与使用说明

请查看仓库当前的许可证文件和项目政策。pyproject.toml 中声明了项目治理制品的专有许可文本；在再分发、商业集成或二次开发前，请确认仓库中的正式许可条款和授权范围。

**仓库：** https://github.com/laodongAI/aimes_cli  
**问题与建议：** https://github.com/laodongAI/aimes_cli/issues  
**版本与制品：** https://github.com/laodongAI/aimes_cli/releases
