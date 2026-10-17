# AIMES 治理升级实施记录：P2 第一批

- 日期：2026-10-18
- 分支：`governance/p0-audit-2026-10-18`
- 关联 PR：[#1](https://github.com/laodongAI/aimes_cli/pull/1)
- 开发版本：`0.7.9`

## 1. 本批实现

1. 增加 `.aimes/project-control/active-writer.yaml` 声明契约和 JSON Schema，记录任务 ID、工具 ID、分支、基线 commit、租约、允许路径和状态。
2. 增加 `aimes task validate`：只读核验声明字段、租约、当前分支、基线 commit、已跟踪/未跟踪变更是否超出允许路径。
3. 增加 `aimes task claim`：需要显式 `--confirm CLAIM`，通过本地文件系统独占创建锁协调 AIMES 命令间的声明更新；创建声明前验证 Git 分支、基线和变更范围。
4. 增加 `aimes task release`：需要显式 `--confirm RELEASE`，必须有完整交接文件且任务/工具身份匹配，随后原子更新状态为 RELEASED。
5. 过期租约不自动接管；必须显式使用 `--takeover --confirm CLAIM`。已存在的活动租约不能被强行覆盖。
6. 增加每任务交接模板 `docs/templates/TASK-HANDOFF-TEMPLATE.md`，要求记录基线、Git 状态、变更文件、真实验证结果、未决风险和接手核验。
7. 补充测试，覆盖正常声明、越界变更、分支不匹配、过期租约、显式接管、任务释放、交接不完整和 CLI 行为。

## 2. 安全边界

- 本地独占创建锁只协调遵守 AIMES 协议的 CLI 操作；不能阻止 IDE/编辑器直接写入，也不是跨机器分布式锁。
- 如果进程异常退出留下锁文件，不自动删除；应先确认没有任务操作仍在运行，再按操作流程人工恢复。
- 允许路径是相对项目根目录的路径前缀，不支持任意 glob。
- `task release` 只接受项目根目录内的交接文件；要求必需章节、任务 ID、基线 commit 和关键元数据字段存在。
- 没有 Git 仓库时不能领取写入声明；不把无法检查解释为通过。

## 3. 验收状态

- 代码和文档已提交到独立开发分支。
- 最新一轮 GitHub Actions 单元测试正在/已按对应提交运行，最终状态以最新 run 为准。
- Windows EXE 打包资源修复已在此前一轮 Windows 工作流中通过构建和外部目录冒烟测试；P2 新增命令还需随当前提交再次验证。

## 4. 下一步

1. 复核 P2 最新提交的单元测试与 Windows EXE 工作流。
2. 复查任务声明和交接协议的错误恢复与跨 worktree 行为。
3. 完成 P1/P2 后再进入 P3 临时产物审计与指标采集。
