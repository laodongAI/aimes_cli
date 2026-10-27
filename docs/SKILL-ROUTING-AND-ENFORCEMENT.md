# Skill 实际调用与规则强制链设计

本文说明 AIMES 如何把"规则文件存在"推进到"Skill 被真实调用、规则被强制检查"。所有能力都遵循既有边界：先预览、显式确认、不覆盖用户文件、不操纵 AI 工具、不伪造运行时证据。

## 1. 四条强制链

| 层次 | 机制 | 强制强度 | 当前状态 |
|---|---|---|---|
| 原生发现 | Skill frontmatter 增加 `name`/`description`；Claude 系工具初始化时同步部署 `.claude/skills/<name>/SKILL.md` 镜像 | 工具的 Skill 机制可原生发现 | 模板与部署已实现；运行时发现按工具版本独立验证 |
| 确定性路由 | `aimes skill route "<任务描述>"` 与 MCP `aimes_skill_route` 按注册表 trigger（含中文别名）评分返回必读 Skill | 把"模型自愿读注册表"变为一条命令的可复核输出 | 已实现（本地匹配） |
| 交付门禁 | `aimes delivery validate <报告.md>` 校验 Core 8.3 固定标题、`VERIFIED`↔PASS 证据绑定、报告等级≥风险等级 | 违规报告返回退出码 1 | 已实现（只读） |
| 提交闸门 | `aimes hook install --type pre-commit` 生成 `hooks/pre-commit`，在提交前执行 `aimes validate` 与 `aimes docs check` | 独立于模型是否自觉 | 已实现；需 `git config core.hooksPath hooks` 激活 |

## 2. Skill 路由命令

```powershell
aimes skill route "实现新功能前先做需求分析并确定验收标准" --root .
aimes skill route "帮我出引导词" --format json --top 5
```

- ASCII trigger 按词边界匹配（`new_feature` 命中 "new feature"）；中文别名按子串匹配。
- 输出含每个命中 Skill 的 `file`（必读路径）、`matched_triggers`、`inputs`、`outputs` 与 `prerequisites`。
- 无命中时返回空列表并要求报告缺口，而不是猜测一个 Skill。
- 静态匹配不证明任何工具已经读取 Skill 文件；运行时状态仍需探针与试点证据。

## 3. MCP 服务接入

```powershell
aimes mcp serve --root .
```

stdio JSON-RPC 服务暴露三个工具：`aimes_skill_route`、`aimes_read_skill`（读取权威 SKILL.md 正文）、`aimes_validate_delivery`（校验交付报告文本）。支持 MCP 的宿主（Claude Code、Codex、Copilot、Trae、Qoder 等）把该服务注册为本地 MCP server 后，模型可在任务开始前一次性获得确定性路由结果。工具描述与返回均声明：调用成功不等于规则已被宿主强制。

各宿主的 MCP 注册方式随产品版本变化，请按实际文档配置并用 `aimes adapter` 证据记录验证结果；AIMES 不自动修改任何宿主配置。

## 4. pre-commit 闸门

```powershell
aimes hook install --root .            # 预览
aimes hook install --root . --apply --confirm HOOK
git config core.hooksPath hooks        # 由用户执行以激活
```

- 生成的钩子带 `# managed-by: aimes` 标记；只更新 AIMES 生成的钩子，用户自有钩子永远保留（生成版本写入 `.aimes/proposed/hooks/` 供人工合并）。
- 钩子仅运行只读检查（`aimes validate`、`aimes docs check`），不执行项目构建命令，不自动修复。

## 5. 已知边界

- `.claude/skills/` 镜像与 `.aimes/skills/` 权威文件的同步靠 manifest 哈希与 `aimes upgrade`/`version-audit` 检查，不代表宿主已加载。
- 中文 trigger 别名覆盖常见任务词，但自然语言表达多样；未命中时应按 Core 路由表人工匹配并反馈补强别名。
- 交付报告校验是结构检查：字段缺失、状态词表和证据绑定可以机检，证据内容是否真实仍需人审或 `aimes evidence validate`。
