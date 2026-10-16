# AIMES 本地治理 CLI（V0.5.3）

AIMES CLI 是本地优先的跨 AI 开发工具工程治理配置与验证工具。它负责把 AIMES V1.2 治理核心部署到项目仓库，生成工具专属规则入口，检查配置与冲突，并输出部署状态。它不替代 Codex、Claude Code、Trae、ZCode 或 Copilot 执行开发任务。

> 当前版本是可运行的 MVP 原型，不是生产级安装器。V0.5.3 在 V0.5.2 基础上增加无参数启动的交互式主菜单，并提供 Windows 独立 EXE 构建脚本；EXE 需要在 Windows 环境中构建和验证。自动化测试以本次构建记录为准；尚未在用户 Windows 环境和实际 IDE/Agent 运行时完成验证。

## 0. 交互式启动与 Windows 独立 EXE

在交互式终端中只输入 `aimes` 即可进入菜单，逐步选择初始化、配置、检查或验证任务。初始化向导支持多选工具，默认先预览；确认实际写入时需要输入 `YES`。原有参数命令仍然保留，适合脚本和 CI。

Windows 独立 EXE 构建和 PATH 配置请见 [`docs/WINDOWS-EXE-DEPLOYMENT.md`](docs/WINDOWS-EXE-DEPLOYMENT.md)。独立 EXE 携带 Python 运行时，不需要激活项目 `.venv`；但必须将整个发布目录放入固定位置并配置用户 PATH。当前开发环境未在 Windows 上实际构建或验证 EXE。

## 1. 锁定的工具入口

1. Trae Code
2. VS Code + Codex
3. VS Code + Claude Code
4. VS Code + GitHub Copilot
5. ZCode
6. QCode
7. Claude Code CLI
8. Codex CLI

VS Code 插件和独立 CLI 是不同执行上下文，必须分别验证。若它们共享 `AGENTS.md` 或 `CLAUDE.md`，治理入口可以共用，但不能假设加载行为相同。

## 2. 安装（Windows PowerShell）

需要 Python 3.10+。安装时需能获取 PyYAML 依赖，或提前将该依赖安装到当前 Python 环境。

```powershell
# 解压发布包后，进入 aimes-cli-v0.5.3 目录
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install .\dist\aimes_governance_cli-0.5.3-py3-none-any.whl

aimes --version
```

如果希望从源码安装：

```powershell
python -m pip install .
aimes --version
```

## 3. 第一次初始化

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

## 4. 常用命令

```powershell
aimes inspect
aimes diff --tools trae-code,vscode-copilot,zcode,qcode
aimes configure --tools vscode-copilot
 aimes validate
aimes doctor
aimes status
aimes validate --format json --output .aimes/reports/validation.json
```

`--scope` 当前仅支持 `project`。全局配置、自动升级、卸载和回滚尚未实现，不应使用本版本执行全局部署。

### V0.3：追溯、证据与交接

```powershell
aimes trace validate examples/traceability/trace-manifest.example.yaml
aimes evidence validate examples/evidence/evidence-registry.example.yaml
aimes context pack examples/traceability/trace-manifest.example.yaml --output-dir .aimes/context-pack
```

- `trace validate` 检查实体 ID 唯一性、追溯链接、证据文件以及 VERIFIED 状态对应的证据引用。
- `evidence validate` 校验已记录的命令/测试/构建证据，不会执行其中的命令；可校验产物存在性和 SHA-256。
- `context pack` 生成 `context-pack.json` 与 `HANDOFF.md`，记录上下文文件清单和哈希；不复制源文件、不执行项目命令。
- 示例数据中的证据是格式演示，不代表真实项目已经执行过相关命令。


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

- `adapter validate` 校验各工具规则入口的验证记录，包括工具 ID、版本、入口路径、验证方法、观察时间、证据文件与哈希。静态检查文件不等于运行时已加载。
- `adapter report` 汇总各工具的 PASS/FAIL/BLOCKED/NOT_RUN/UNKNOWN 覆盖情况。缺少记录不等于通过或失败。
- `context validate` 对照 Context Pack 中记录的 SHA-256 检查源文件是否变化，并可检查 HANDOFF 文件是否存在。变化会提示重新审阅，不自动判断修改是否正确。
- PASS 记录必须采用运行时观察、自动化检查或用户确认的方法，并附证据文件或说明。CLI 不会自动操纵 IDE，也不会伪造运行时证据。

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
```

命令检查必填字段、AIMES 状态、重复 ID、验收条件、知识来源/成熟度证据、复用验证计划、Skill 文件存在性与项目根目录路径逃逸。未知字段目前报告为 WARNING，结构性和契约错误报告为 ERROR。JSON 报告使用 `schema_version: 1`。

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
