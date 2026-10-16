# AIMES Windows EXE 构建与全目录调用说明（V0.5.3）

## 目标

Windows EXE 应携带 Python 运行时及所需依赖，不依赖项目 `.venv` 是否激活。用户从任意工作目录调用 `aimes` 时，程序仍以**当前工作目录/向上查找的项目根目录**作为目标项目；EXE 所在目录仅用于加载程序，不应被误认为项目根目录。

## 构建

必须在 Windows 上构建 Windows EXE。Linux 下的 PyInstaller 不能可靠地直接产出原生 Windows 可执行文件。

在 Windows PowerShell 中解压源码后执行：

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\build_windows_exe.ps1
```

输出：`dist-exe\aimes\aimes.exe` 以及同目录依赖文件。请整体分发 `dist-exe\aimes\` 目录，不要只复制 `aimes.exe`。

## 配置 PATH

建议将整个文件夹复制到稳定路径，例如：

`%LOCALAPPDATA%\Programs\AIMES\`

然后在 Windows「环境变量」中，把该目录加入**当前用户**的 `Path`。关闭并重新打开 PowerShell 后验证：

```powershell
Get-Command aimes.exe
 aimes.exe --version
 aimes.exe
```

如希望直接输入 `aimes`，可将可执行文件命名为 `aimes.exe`；PowerShell 通常可通过命令名找到它。若系统策略或命令解析存在差异，先使用 `aimes.exe` 验证 PATH 配置。

## 不同目录的语义

- `cd E:\project-a; aimes.exe`：操作 E:\project-a 项目。
- 在一个没有项目配置的目录运行：使用当前目录作为初始化目标，除非向上找到已有 AIMES 项目根目录。
- 不要求激活任何项目 `.venv`。
- 这不意味着无需安装：首次部署仍需把发布目录放到稳定位置并配置 PATH。

## 安全和限制

- V0.5.3 的 `--scope` 仍只支持 `project`，不会自动安装全局项目规则。
- EXE 需要在目标 Windows 版本上实测；签名、杀毒软件信誉、企业应用控制策略可能影响启动。
- 此源码包中的构建脚本只是构建配方。若没有在 Windows runner 上实际执行构建和烟雾测试，不应宣称已交付经过 Windows 验证的 EXE。
