# 业务代码修复提案：审阅、应用、验证与回滚

## 目标与边界

`aimes repair` 处理 AIMES 配置和治理文件。对于业务代码，AIMES 不应直接相信模型给出的“已修好”结论，而应将修复作为独立提案：先保存并审阅 diff，再经明确确认应用，记录备份，执行用户指定的测试命令，并在需要时安全回滚。

当前实现接收统一 diff（unified diff）文件；它不自行调用模型，也不自动推断根因。用户或 AI 编码工具先生成补丁，AIMES 负责路径/基线校验、提案留档、应用确认、测试记录和回滚保护。

## 0. 先运行诊断命令并生成修复建议

如果你已经知道需要复现问题的测试命令，可以先让 AIMES 运行该命令、记录退出码和输出，并给出基于常见错误特征的修复建议：

```powershell
aimes repair-code diagnose --id diag-2026-001 --test-argv-json '["python","-m","unittest","discover","-s","tests"]' --timeout-seconds 300 --root . --format json
```

诊断记录保存在 `.aimes/repairs/diagnostics/diag-2026-001.json`。它会区分依赖/导入错误、语法错误、断言失败、类型/接口错误、测试发现失败、超时及未分类失败，并给出检查建议和下一步补丁提案流程。此分类是辅助提示，不保证根因已确认；命令返回 0 也只表示这条命令成功。
## 1.1 随时检查提案状态与下一步

可在任意阶段运行只读检查，查看当前状态、补丁哈希完整性、目标文件是否被后续修改、关联诊断摘要和推荐的下一步操作：

```powershell
aimes repair-code inspect fix-2026-001 --root . --format json
```

该命令不写入文件、不运行测试，也不自动应用/回滚。若发现 `PATCH_HASH_MISMATCH`、`PREIMAGE_CHANGED` 或 `POST_APPLY_CHANGED`，应先人工调查；不要绕过冲突保护。`VERIFIED` 只代表记录的那条测试命令通过，仍需复跑原始失败用例并执行必要的回归验收。

## 1. 准备补丁

让编码工具先给出最小 unified diff，并保存为项目内或可访问的 UTF-8 文本文件，例如 `candidate.patch`。v1 接受普通文本文件修改和新增，不接受删除、重命名、二进制文件或修改 AIMES 元数据/虚拟环境/依赖目录。

## 2. 创建提案（只读业务文件）

```powershell
aimes repair-code propose candidate.patch --id fix-2026-001 --finding "TEST-42: test_login rejects valid credentials" --rationale "修复登录校验中的错误分支" --root . --format json
```

提案存放在 `.aimes/repairs/fix-2026-001/`，包括 `change.patch`（原始补丁）和 `proposal.json`（诊断关联、补丁哈希、涉及文件、创建时文件哈希和状态）。创建提案不会修改业务代码。提案目录已存在时拒绝覆盖。请先人工审阅补丁与清单。

## 3. 显式应用

```powershell
aimes repair-code apply fix-2026-001 --confirm APPLY-FIX --root . --format json
```

命令检查补丁哈希、目标文件是否在提案后变化、路径边界和 Git 补丁预检，然后保存应用前备份并应用补丁。确认词 `APPLY-FIX` 不区分大小写。

## 4. 执行测试并记录证据

Python 示例：

```powershell
aimes repair-code verify fix-2026-001 --test-argv-json '["python","-m","unittest","discover","-s","tests"]' --timeout-seconds 300 --root . --format json
```

Node.js 示例：

```powershell
aimes repair-code verify fix-2026-001 --test-argv-json '["npm","test","--","--runInBand"]' --timeout-seconds 300 --root . --format json
```

测试命令按参数数组调用，使用 `shell=False`，不经过 shell 解析。测试通过只证明指定命令返回 0，并不自动证明原始问题已解决或完整回归测试已覆盖。验证失败会记录退出码、输出尾部和超时信息，状态为 `VERIFICATION_FAILED`，不会虚报成功。

## 5. 安全回滚

```powershell
aimes repair-code rollback fix-2026-001 --confirm ROLLBACK-FIX --root . --format json
```

只有在被修改文件的当前哈希仍与补丁应用后记录的哈希一致时才允许回滚，避免覆盖应用补丁后用户继续做出的修改。确认词 `ROLLBACK-FIX` 不区分大小写。提案、补丁、备份和验证记录仍保留。

## 状态流转

```text
PROPOSED -> APPLIED -> VERIFIED
                    -> VERIFICATION_FAILED
APPLIED / VERIFIED / VERIFICATION_FAILED -> ROLLED_BACK
```

只有 `VERIFIED` 表示指定验证命令通过；它不等于整个任务的验收通过。还应复跑最初失败的诊断、相关回归测试，并由任务验收标准决定是否关闭问题。

## 安全边界

- 提案默认只读；应用、回滚均要求显式确认。
- 拒绝绝对路径、目录穿越、符号链接、删除、重命名和二进制补丁。
- 不修改 `.git`、`.aimes`、虚拟环境、依赖和缓存目录。
- 提案创建时记录目标文件哈希，应用前再次检查，防止覆盖期间产生的新改动。
- 应用前保存备份；回滚前检查应用后哈希，防止覆盖后续修改。
- 验证命令必须是 JSON 字符串数组，不通过 shell 执行；仅运行用户明确提供的命令。
- 当前不自动生成补丁、不自动调用 LLM、不执行远程发布，也不自动决定修复正确性。
