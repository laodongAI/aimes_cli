$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot

# 在 Windows PowerShell 中运行；不要在 Linux 上尝试交叉生成 Windows EXE。
if (-not (Get-Command py -ErrorAction SilentlyContinue)) {
    throw '未找到 Python Launcher（py）。请先安装 Python 3.10+ 并启用 Add Python to PATH。'
}

py -3 -m venv .build-venv
$python = Join-Path $PSScriptRoot '.build-venv\Scripts\python.exe'
& $python -m pip install --upgrade pip
& $python -m pip install -e .
& $python -m pip install -r requirements-build.txt

# 使用 onedir，启动更快、故障排查更容易；输出目录包含独立运行时，不依赖项目 venv。
& $python -m PyInstaller --noconfirm --clean --onedir --console `
    --name aimes `
    --collect-all yaml `
    --paths src `
    --distpath dist-exe `
    --workpath build\pyinstaller-work `
    aimes_entry.py

if ($LASTEXITCODE -ne 0) { throw 'PyInstaller 构建失败。' }
Write-Host ''
Write-Host '构建完成：' (Join-Path $PSScriptRoot 'dist-exe\aimes\aimes.exe')
Write-Host '请将整个 dist-exe\aimes 文件夹部署到固定目录，并将该目录加入用户 PATH。'
Write-Host '验证：在新的 PowerShell 窗口中运行 aimes.exe --version 和 aimes。'
