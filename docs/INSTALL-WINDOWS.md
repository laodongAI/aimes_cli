# AIMES CLI V0.5.1 — Windows 部署说明

## 前置条件

- Windows 10/11
- Python 3.10 或更高版本
- PowerShell
- PyYAML 6.x（wheel 安装时如未预装，pip 需要能够获取依赖）

## 安装发布 wheel

解压完整源码包后，在源码目录执行：

```powershell
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install .\release-artifacts\aimes_governance_cli-0.5.1-py3-none-any.whl
aimes --version
```

如果 PowerShell 禁止激活脚本，可直接调用虚拟环境中的 Python：

```powershell
.\.venv\Scripts\python.exe -m pip install .\release-artifacts\aimes_governance_cli-0.5.1-py3-none-any.whl
.\.venv\Scripts\python.exe -m aimes_cli.cli --version
```

## 在项目中初始化

```powershell
Set-Location E:\path\to\your-project
git status --short --branch
aimes inspect
aimes init --tools codex-cli,claude-code --scope project --dry-run
aimes init --tools codex-cli,claude-code --scope project
aimes validate
aimes status
```

请先提交或备份重要工作。AIMES CLI 不替代项目自身的版本控制与备份流程。

## V0.5 交接完整性与工具验证

```powershell
aimes adapter validate examples/adapters/verification-evidence.example.yaml --format json
aimes adapter report examples/adapters/verification-evidence.example.yaml --format json
aimes context pack examples/traceability/trace-manifest.example.yaml --output-dir .aimes/context-pack
aimes context validate .aimes/context-pack/context-pack.json --handoff .aimes/context-pack/HANDOFF.md --format json
```

`UNKNOWN` 与 `NOT_RUN` 表示尚无充分验证结论。仅检查规则文件不能证明 IDE/Agent 已加载规则；运行时 PASS 需要附可复核的观察记录或产物。V0.5 尚未在所有目标工具的真实 Windows 环境完成验证。

## 冲突与回滚

如果目标文件存在冲突，原文件会被保留；查看 `.aimes/proposed/`，人工审查后再合并。MVP 暂不提供自动回滚。推荐在初始化前建立 Git commit。不要直接删除整个 `.aimes/` 目录，因为其中可能包含用户配置、报告或人工维护的适配证据。
