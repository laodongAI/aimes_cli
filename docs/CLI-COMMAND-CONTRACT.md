# AIMES CLI 命令契约 V0.7.1

| 命令 | 用途 | 写入行为 | 失败退出码 |
|---|---|---|---|
| `aimes init` | 首次初始化并交互选择工具 | 创建不存在的文件；冲突写提案 | 2 |
| `aimes configure --tools ...` | 增加工具适配 | 仅更新 manifest 证明未被修改的受管文件 | 2 |
| `aimes inspect` | 读取项目目录与 Git 状态 | 只读 | 0 |
| `aimes diff --tools ...` | 预览初始化动作 | 只读 | 2 |
| `aimes validate` | 检查配置、核心规范、入口和 manifest | 只读 | 2（存在错误） |
| `aimes doctor` | 检查常见可执行文件 | 只读 | 0 |
| `aimes status` | 汇总部署状态 | 只读 | 0 |

## 通用选项

- `--root PATH`：指定项目根目录；默认当前目录并向上探测 Git 根目录或 AIMES 配置。
- `--format text|json`：报告格式（V0.1.0 结构化输出均为 JSON 风格，简洁文本渲染待实现）。
- `--output PATH`：将报告写入文件。
- `--tools a,b`：非交互式选择工具。
- `--dry-run`：只预览、不写入。

## 工具 ID

`trae-code`, `vscode-codex`, `vscode-claude-code`, `vscode-copilot`, `zcode`, `qcode`, `claude-code`, `codex-cli`。

## 退出语义

- `0`：命令成功；注意这不代表 AI 工具运行时规则已加载。
- `2`：参数、配置或写入冲突错误，需要用户检查。

## 后续兼容承诺

- 命令 ID 与工具 ID 纳入版本控制。
- 配置 Schema 有版本号；不兼容更改提升 schema 版本。
- JSON 输出字段尽量向后兼容。
- 全局部署、升级和卸载在具备备份、差异和恢复机制后才进入稳定版。


## V0.2 新增结构化校验命令

| 命令 | 输入 | 检查范围 | 写入行为 |
|---|---|---|---|
| `aimes requirement validate <path>` | 需求认知 YAML/JSON | 必填字段、状态、场景/需求 ID、验收条件、批准证据 | 只读 |
| `aimes knowledge validate <path>` | 知识资产 YAML/JSON | 来源、适用条件、成熟度和证据、项目内来源路径 | 只读 |
| `aimes reuse validate <path>` | 复用决策 YAML/JSON | 决策枚举、候选资产引用、比较记录、验证计划 | 只读 |
| `aimes skill validate [<registry>] [--id ID]` | Skill 注册表与引用文件 | 必填契约、唯一 ID、状态/风险枚举、文件存在、根目录路径约束、推荐章节 | 只读 |

V0.2 JSON 报告固定包含 `schema_version`、`validator`、`source`、`ok`、`summary` 和 `findings`。校验通过为退出码 0；发现治理错误为 1。未知字段暂为 WARNING；本版本不自动批准需求、升级知识成熟度或运行 Skill。


## V0.3 追溯与证据命令

| 命令 | 用途 | 写入行为 | 退出码 |
|---|---|---|---|
| `aimes trace validate <path>` | 检查实体链接、缺失目标、重复 ID，以及 VERIFIED 状态是否引用 PASS 证据 | 只读 | 0 通过；1 校验失败 |
| `aimes evidence validate <path>` | 检查证据结构、命令与退出码一致性、产物路径和可选哈希 | 只读 | 0 通过；1 校验失败 |
| `aimes context pack <manifest> --output-dir <dir>` | 生成 `context-pack.json` 和 `HANDOFF.md` | 在项目根目录内生成文件 | 0 成功；2 输入/路径错误 |

证据是“被记录的执行结果”，CLI 不会执行证据中的 command。`PASS` 只是证据记录的结果字段；在需要强保证的场景，应由可信 CI 或受控执行器生成并签名证据。当前版本不验证签名、不证明证据记录一定真实。

`VERIFIED` 的最低门禁：manifest 必须指定 `evidence_file`；实体必须有 `evidence_refs`；每个引用必须存在且结果为 `PASS`。本规则校验引用一致性和记录结构，不等同于独立复现执行。


## V0.4 评测与回归命令

| 命令 | 用途 | 写入行为 | 退出码 |
|---|---|---|---|
| `aimes evaluation validate <suite>` | 校验评测集元数据、案例唯一性、必需字段与评分契约 | 只读 | 0 通过；1 校验失败 |
| `aimes evaluation report <run-record>` | 校验运行记录并输出案例状态、硬门禁统计与诊断分数 | 只读；可通过 `--output` 保存报告 | 0 通过；1 校验失败 |
| `aimes evaluation compare <baseline> <candidate>` | 比较两次运行的案例状态、硬门禁和诊断分数 | 只读；可通过 `--output` 保存报告 | 0 无硬门禁退化；1 检测到硬门禁退化 |

V0.4 的 `evaluation` 命令不执行 AI 任务或命令。运行记录由实际评测执行方填写/生成；CLI 负责结构校验、统计和对比。`PASS` 结果应关联可复核证据，元数据缺失会产生 WARNING。当前对比以同一 `case_id` 为共同样本，新增/删除案例会单独列出，不把不一致样本直接算作模型退化。


## V0.5.0 命令契约

- `aimes adapter validate <path>`：只读校验工具验证证据记录。PASS 必须采用 `runtime_observation`、`automated_check` 或 `user_confirmed`，并包含 `artifact_path` 或 `evidence_note`。
- `aimes adapter report <path>`：输出工具覆盖统计；不推断未记录工具的状态。
- `aimes context validate <path> [--handoff <path>]`：校验 Context Pack 类型、路径边界、源文件存在性与 SHA-256，并可检查 HANDOFF 文件。
- 所有新命令支持 `--root`、`--format text|json`、`--output`。校验失败退出码为 1，参数或文件读取错误为 2。
- 以上命令不读取 IDE 私有状态、不执行任意 shell、不自动修改规则入口，也不证明证据来源不可伪造。


## V0.5.2 新增命令

| 命令 | 用途 | 写入行为 | 退出码/边界 |
|---|---|---|---|
| `aimes evaluation run-mock <suite> --responses <fixtures>` | 对明确提供的 mock 文本夹具执行大小写不敏感的精确子串检查 | 仅写入显式指定的 `--output` | 0 表示所选夹具词面检查通过；1 表示有失败/未执行；不调用模型、不代表语义评测 |
| `aimes audit append <path> --run-id ID --event-type TYPE --status STATUS [--details-json JSON]` | 追加脱敏 JSONL 审计事件 | 追加指定日志 | 事件字段经基础脱敏；本地日志不具备自动防篡改保证 |
| `aimes audit validate <path>` | 检查审计 JSONL 的结构、必填字段和重复 event_id | 只读 | 0 通过；1 结构错误 |

新增提示词资产：`docs/PROMPT-OUTPUT-EXAMPLES-V1.0.md`、`docs/CONTEXT-BUDGET-AND-FILE-PLAN-V1.0.md`、`docs/TOOL-FAILURE-DEGRADATION-PROTOCOL-V1.0.md`、`docs/AUDIT-TRAIL-V1.0.md`。Mock Runner 使用字面匹配，不判断语义等价性；真实模型评测仍需真实模型适配器与独立评审。


## V0.6.0：GitHub 根目录镜像发布

| 命令 | 用途 | 写入行为 | 安全边界 |
|---|---|---|---|
| `aimes publish --source PATH --repo OWNER/REPO` | 预览本地项目与已有 GitHub 仓库根目录的完整镜像差异 | 默认只读预览 | 显示新增、更新、删除、未变化文件 |
| `aimes publish ... --apply --confirm PUBLISH` | 执行镜像并推送提交 | 在临时克隆中准备提交并普通推送 | 必须显式确认；不强制推送；检测到疑似密钥时阻止执行 |

发布默认使用仓库默认分支；可用 `--branch` 指定分支。完整镜像会删除目标根目录中本地不存在的文件，执行前必须检查删除清单。`.git` 元数据、符号链接、常见缓存/依赖目录和凭据文件会排除。密钥扫描是启发式检查，不是完整的秘密检测保证。


## V0.7.1：配置式 GitHub 发布

| 命令 | 用途 | 写入行为 | 安全边界 |
|---|---|---|---|
| `aimes publish` | 进入交互式配置、预览和发布向导 | 默认只预览；输入 `PUBLISH` 后推送 | 先展示完整镜像差异和删除清单 |
| `aimes publish --list-profiles` | 列出本地发布配置 | 只读 | 不输出认证信息 |
| `aimes publish --profile NAME` | 使用已保存配置 | 默认只预览 | 配置不保存 Token/密码 |
| `aimes publish ... --save-profile NAME` | 保存/更新用户级配置 | 写入 JSON 配置文件 | 仅保存路径、仓库、分支、说明和排除规则 |
| `aimes publish ... --exclude GLOB` | 追加自定义排除规则，可重复 | 影响本次文件清单 | 只能增加过滤，不能取消默认安全过滤 |
| `aimes publish ... --apply --confirm PUBLISH` | 非交互执行发布 | 创建提交并普通推送 | 显式确认，不强制推送 |

默认过滤 Python/Node 环境、AI 工具本地状态目录、运行日志/PID/临时文件、构建缓存和常见编译产物。预览与执行共用同一套过滤规则。

  
交互式初始化（无参数运行 `aimes` 后选择“初始化项目”）会将当前工作目录明确显示为目标目录。选择预览后，先输出 dry-run 变更报告，再提示输入 `YES`；只有确认后才执行正式写入。取消不会写入文件。

## V0.7.8 治理检查命令

| 命令 | 用途 | 写入行为 | 退出码 |
|---|---|---|---|
| `aimes docs check [--root PATH]` | 检查 Markdown 本地链接、已配置工具入口是否存在，以及原生薄入口的核心引用/行数限制 | 只读；仅通过 `--output` 保存报告 | 0 通过；1 校验发现错误；2 参数或读取错误 |

该命令当前实现于治理升级开发分支，尚未合并到主分支。手动适配说明文件只检查存在性，不按原生薄规则入口执行行数限制。文档检查不证明 IDE 已在运行时加载规则；运行时加载仍须通过 `adapter validate/report` 的独立证据流程验收。
