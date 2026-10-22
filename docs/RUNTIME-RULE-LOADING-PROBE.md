# AI 工具规则加载探针（Codex CLI / Claude Code CLI）

## 目标与边界

探针在项目内生成一个独立、临时的最小项目，只包含目标 CLI 原生规则入口和验证说明：

- Codex CLI：AGENTS.md
- Claude Code CLI：CLAUDE.md

规则文件包含随机唯一 token，PROMPT.txt 不包含 token。必须在全新 CLI 会话中，从探针目录启动工具，并把提示原样提交。然后把助手的完整原始回复保存为 response.txt，由 AIMES 精确比较 token，并生成适配证据 V2。

这能提供指定工具版本、CLI 执行模式、操作系统下“隔离项目原生规则入口加载并遵循探针指令”的证据。它不能证明真实业务项目里的每一条规则都被加载、所有 Skill 都有效或工程质量已经提升。不要把该结果等同于完整治理能力验收。

## 1. 创建探针

在已安装最新 AIMES CLI 的终端中执行。版本字段必须填写实际工具版本，不要使用示例值：

    aimes adapter probe create --tool codex-cli --product-version "<实际 codex --version 输出>" --output-dir .aimes/probes/codex-cli --root . --format json

    aimes adapter probe create --tool claude-code --product-version "<实际 claude --version 输出>" --output-dir .aimes/probes/claude-code --root . --format json

探针输出目录若已存在，AIMES 会拒绝覆盖。请保留每次探针的目录和原始结果，不要重复使用旧探针目录。

## 2. 在真实 CLI 中执行

以 Codex CLI 为例：

1. 打开一个新的 PowerShell 终端。
2. 进入 .aimes/probes/codex-cli 目录。
3. 启动正常的 Codex CLI 命令。
4. 创建新会话，不要复用已有对话。
5. 将 PROMPT.txt 的完整内容作为用户消息发送。
6. 将助手的完整原始回复保存为该目录下的 response.txt，不要改写、删减或自行补入 token。

Claude Code 同理，在 CLAUDE.md 所在目录启动 claude，并在新会话中执行提示。

如果工具没有读取规则、返回解释文字、输出 Markdown 包装、响应 token 不一致，或无法确认是新会话，应保留原始响应并记录失败/阻塞，不要手动修成 PASS。

## 3. 验证并生成证据

从项目根目录执行：

    aimes adapter probe validate .aimes/probes/codex-cli --root . --format json
    aimes adapter validate .aimes/probes/codex-cli/verification-evidence.yaml --root . --format json

Claude Code 对应使用 .aimes/probes/claude-code 路径。

验证命令会：

- 检查探针规则入口的 SHA-256 是否仍与创建时一致；
- 检查原始回复是否严格匹配随机 token（仅允许首尾空白）；
- 生成 verification-evidence.yaml，记录工具版本、执行模式、平台、规则入口、观察时间、案例 ID、AIMES 版本、治理版本、原始响应路径和 SHA-256；
- 返回 PASS、FAIL 或 NOT_RUN。没有 response.txt 时不会创建 PASS 记录；
- 拒绝覆盖已有证据文件。若需重测，请创建新的探针目录。

## 4. 安全与可信边界

- AIMES 不会启动、控制或注入提示到 Codex/Claude CLI；操作者手动启动并保存原始回复。
- 预期 token 不会写入 PROMPT.txt 或 probe-manifest.json，只保存在原生规则文件中，降低直接从提示复制答案导致的假阳性。
- 探针目录应视为临时测试资产，不应作为生产项目的治理规则使用。
- 结果依赖操作者遵循新会话流程；若在旧会话中执行、修改响应文件或伪造输出，结构校验不能证明过程真实。
- 证据文件与本地响应文件可被修改；当前版本不提供签名、远程可信时间戳或防篡改保证。
- PASS 只适用于该次指定版本/执行模式/平台，不自动外推到 VS Code 插件、其他版本或其他 AI 工具。

## 5. 下一步

探针通过后，应继续在真实项目中验证更具体的规则遵循行为，例如变更前先检查需求、先运行测试、禁止未授权写入、要求文档与代码同步。每个行为都需要独立案例和外部可复核证据；不能只凭模型复述规则就宣称工程效果提升。
