from __future__ import annotations
import hashlib, os, re, shutil, subprocess, tempfile
from pathlib import Path
from typing import Any

EXCLUDED_DIRS = {".git", ".venv", "venv", "env", "node_modules", "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache", ".tox", ".nox", ".idea", ".vscode-test", "coverage", "htmlcov"}
EXCLUDED_NAMES = {".env", ".env.local", ".env.development", ".env.production", "credentials.json", "secrets.json", "id_rsa", "id_ed25519", "known_hosts", ".ds_store", "thumbs.db"}
EXCLUDED_SUFFIXES = {".pem", ".key", ".p12", ".pfx", ".pyc", ".pyo"}
SECRET_PATTERNS = [re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----"), re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}\b"), re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}\b"), re.compile(r"\bAKIA[0-9A-Z]{16}\b"), re.compile(r"\bsk-(?:proj-)?[A-Za-z0-9_-]{24,}\b")]
MAX_SCAN_BYTES = 2 * 1024 * 1024

def normalize_repository(value: str) -> tuple[str, str]:
    raw = value.strip()
    if re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", raw):
        owner, repo = raw.split("/", 1)
        repo = repo.removesuffix(".git")
        return f"https://github.com/{owner}/{repo}.git", f"{owner}/{repo}"
    match = re.fullmatch(r"(?:https://github\.com/|git@github\.com:)([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+?)(?:\.git)?/?", raw)
    if not match: raise ValueError("--repo 必须是 owner/repo 或 GitHub HTTPS/SSH 仓库 URL")
    owner, repo = match.groups()
    return f"https://github.com/{owner}/{repo}.git", f"{owner}/{repo}"

def validate_branch(branch: str) -> str:
    if not branch or branch.startswith("-") or branch.startswith("/") or branch.endswith("/"): raise ValueError("无效的 Git 分支名")
    if ".." in branch or branch.endswith(".lock") or re.search(r"[\s~^:?*\\\[\]]", branch): raise ValueError(f"无效的 Git 分支名：{branch}")
    if any(p in {"", ".", ".."} or p.startswith(".") or p.endswith(".") for p in branch.split("/")): raise ValueError(f"无效的 Git 分支名：{branch}")
    return branch

def is_excluded(rel: str, is_dir: bool = False) -> bool:
    parts = Path(rel).parts
    if any(p in EXCLUDED_DIRS for p in parts): return True
    name = parts[-1].lower() if parts else rel.lower()
    return name in EXCLUDED_NAMES or name.startswith(".env.") or Path(name).suffix in EXCLUDED_SUFFIXES or name.endswith("~") or name in {".ds_store", "desktop.ini"}

def collect_source_files(source: Path) -> tuple[dict[str, Path], list[str], list[dict[str, str]]]:
    source = source.resolve()
    if not source.is_dir(): raise ValueError(f"本地源目录不存在或不是目录：{source}")
    if source == Path(source.anchor): raise ValueError("为避免误发布，不能把磁盘/文件系统根目录作为源目录")
    files, excluded, findings = {}, [], []
    for current, dirs, names in os.walk(source, topdown=True, followlinks=False):
        base = Path(current)
        kept = []
        for name in dirs:
            path = base / name
            rel = path.relative_to(source).as_posix()
            if path.is_symlink() or is_excluded(rel, True): excluded.append(rel + "/")
            else: kept.append(name)
        dirs[:] = kept
        for name in names:
            path = base / name
            rel = path.relative_to(source).as_posix()
            if path.is_symlink() or is_excluded(rel): excluded.append(rel); continue
            files[rel] = path
            try:
                if path.stat().st_size > MAX_SCAN_BYTES: continue
                content = path.read_bytes().decode("utf-8")
            except (OSError, UnicodeDecodeError): continue
            if any(p.search(content) for p in SECRET_PATTERNS): findings.append({"path": rel, "reason": "文件内容疑似包含访问令牌或私钥"})
    return files, sorted(excluded), findings

def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""): h.update(chunk)
    return h.hexdigest()

def git_run(args: list[str], cwd: Path | None = None, timeout: int = 180) -> str:
    try: result = subprocess.run(["git", *args], cwd=str(cwd) if cwd else None, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout, check=False)
    except FileNotFoundError as exc: raise ValueError("未找到 Git。请先安装 Git，并确保 git 已加入 PATH。") from exc
    except subprocess.TimeoutExpired as exc: raise ValueError(f"Git 命令超时：git {' '.join(args[:3])}") from exc
    if result.returncode:
        detail = (result.stderr or result.stdout).strip()
        raise ValueError(f"Git 命令失败（退出码 {result.returncode}）：{detail[-1500:]}")
    return result.stdout.strip()

def _target_snapshot(root: Path) -> dict[str, str]:
    result = {}
    for current, dirs, names in os.walk(root, topdown=True, followlinks=False):
        base = Path(current)
        dirs[:] = [d for d in dirs if d != ".git" and not (base / d).is_symlink()]
        for name in names:
            path = base / name
            if not path.is_symlink(): result[path.relative_to(root).as_posix()] = sha256_file(path)
    return result

def build_change_plan(source_files: dict[str, Path], target_files: dict[str, str]) -> dict[str, list[str]]:
    hashes = {p: sha256_file(f) for p, f in source_files.items()}
    added = sorted(set(hashes) - set(target_files))
    updated = sorted(p for p in set(hashes) & set(target_files) if hashes[p] != target_files[p])
    deleted = sorted(set(target_files) - set(hashes))
    unchanged = sorted((set(hashes) & set(target_files)) - set(updated))
    return {"added": added, "updated": updated, "deleted": deleted, "unchanged": unchanged}

def publish_project(source: Path, repository: str, branch: str | None = None, apply: bool = False, confirm: str | None = None, message: str = "chore: mirror local project with AIMES") -> dict[str, Any]:
    source = source.expanduser().resolve()
    url, repo_name = normalize_repository(repository)
    if branch: validate_branch(branch)
    if apply and confirm != "PUBLISH": raise ValueError("执行发布必须同时提供 --apply --confirm PUBLISH")
    source_files, excluded, findings = collect_source_files(source)
    if not source_files: raise ValueError("源目录没有可发布文件；为避免清空远端仓库，已停止")
    if apply and findings:
        raise ValueError("源文件疑似包含密钥/令牌，已阻止发布：" + ", ".join(x["path"] for x in findings[:10]) + "。请移除密钥后重新预览。")
    with tempfile.TemporaryDirectory(prefix="aimes-publish-") as temp:
        clone = Path(temp) / "repo"
        args = ["clone", "--quiet"] + (["--branch", branch, "--single-branch"] if branch else []) + [url, str(clone)]
        git_run(args, timeout=240)
        actual_branch = git_run(["branch", "--show-current"], cwd=clone)
        if branch and actual_branch != branch: raise ValueError(f"克隆到的分支与请求不一致：{actual_branch} != {branch}")
        base_sha = git_run(["rev-parse", "HEAD"], cwd=clone)
        plan = build_change_plan(source_files, _target_snapshot(clone))
        report: dict[str, Any] = {"ok": True, "mode": "apply" if apply else "dry-run", "repository": repo_name, "branch": actual_branch, "source": str(source), "source_file_count": len(source_files), "excluded_count": len(excluded), "excluded_preview": excluded[:100], "secret_findings": findings, "changes": plan, "change_counts": {k: len(v) for k, v in plan.items()}, "base_commit": base_sha, "commit": None, "warning": "根目录完整镜像会删除本地源目录中不存在的远端文件；不会修改 .git 元数据，且不会强制推送。"}
        if not apply:
            report["message"] = "仅预览，未向 GitHub 推送任何更改。确认删除清单后，使用 --apply --confirm PUBLISH 执行。"
            return report
        if not any(plan[k] for k in ("added", "updated", "deleted")):
            report["message"] = "远端与本地镜像一致，无需提交或推送。"
            return report
        for child in clone.iterdir():
            if child.name == ".git": continue
            if child.is_dir() and not child.is_symlink(): shutil.rmtree(child)
            else: child.unlink()
        for rel, src in source_files.items():
            dest = clone / Path(rel)
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dest)
        git_run(["add", "--force", "-A", "--", "."], cwd=clone)
        staged = subprocess.run(["git", "diff", "--cached", "--quiet"], cwd=str(clone), capture_output=True, check=False)
        if staged.returncode == 0:
            report["message"] = "远端与本地镜像一致，无需提交或推送。"
            return report
        if staged.returncode != 1: raise ValueError("无法检查暂存区差异，发布已中止")
        git_run(["-c", "user.name=AIMES CLI", "-c", "user.email=aimes-cli@users.noreply.github.com", "commit", "-m", message], cwd=clone)
        commit = git_run(["rev-parse", "HEAD"], cwd=clone)
        git_run(["push", "origin", f"HEAD:refs/heads/{actual_branch}"], cwd=clone, timeout=240)
        report.update({"commit": commit, "commit_url": f"https://github.com/{repo_name}/commit/{commit}", "repository_url": f"https://github.com/{repo_name}", "message": "镜像提交已推送到 GitHub。"})
        return report
