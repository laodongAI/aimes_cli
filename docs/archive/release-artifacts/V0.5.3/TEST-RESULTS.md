# AIMES CLI V0.5.3 Test Results

Environment: Linux container, Python 3.13. This is not a Windows validation report.

- `PYTHONPATH=src python -m unittest discover -s tests -v`: 47 passed, 0 failed.
- Interactive wizard unit tests: menu exit and invalid menu input paths passed.
- CLI version smoke: pending final package build check.
- Windows PyInstaller EXE: not built or tested in this Linux environment. Run `build_windows_exe.ps1` on Windows and verify from a fresh PowerShell session and a directory outside the source tree.

Limitations:
- EXE distribution is a build recipe and Windows deployment guide, not a prebuilt, Windows-verified binary.
- `--scope` remains project-only.
