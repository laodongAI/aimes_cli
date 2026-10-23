from __future__ import annotations
import hashlib, os, re, shutil, subprocess, tempfile
from pathlib import Path
from typing import Any
from fnmatch import fnmatchcase

# 默认过滤开发环境、AI 工具本地状态、运行产物和构建缓存。
EXCLUDED_DIRS = {
    ".git", ".venv", "venv", "env", "ENV", ".env", "node_modules", "__pycache__",
    ".pytest_cache", ".mypy_cache", ".ruff_cache", ".tox", ".nox", ".idea", ".vscode-test",
    ".cache", "cache", "logs", "log", "tmp", "temp", "runtime", "run", "site-packages",
    "coverage", "htmlcov", "build", "dist", ".claude", ".codex", ".cursor", ".aider",
    ".continue", ".windsurf", ".trae", ".qoder", ".zcode", ".gemini", ".opencode", ".copilot",
}
EXCLUDED_NAMES = {
    ".env", ".env.local", ".env.development", ".env.production", "credentials.json",
    "secrets.json", "id_rsa", "id_ed25519", "known_hosts", ".ds_store", "thumbs.db",
    "desktop.ini", ".aider.chat.history.md", ".python_history",
}
EXCLUDED_SUFFIXES = {
    ".pem", ".key", ".p12", ".pfx", ".pyc", ".pyo", ".pyd", ".log", ".pid",
    ".swp", ".swo", ".tmp", ".temp", ".bak", ".orig", ".class", ".o", ".obj",
    ".so", ".dll", ".dylib", ".sock",
}
SECRET_PATTERNS = [re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----"), re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}\b"), re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}\b"), re.compile(r"\bAKIA[0-9A-Z]{16}\b"), re.compile(r"\bsk-(?:proj-)?[A-Za-z0-9_-]{24,}\b")]
MAX_SCAN_BYTES = 2 * 1024 * 1024
# GitHub rejects a single Git blob at 2 GiB. Leave headroom for server-side limits.
MAX_GITHUB_BLOB_BYTES = 2 * 1024 * 1024 * 1024 - 1024 * 1024

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

def _is_aimes_governance_path(normalized: str, is_dir: bool = False) -> bool:
    """识别应随项目发布的 AIMES 治理资产及其必要父目录。"""
    path = normalized.strip("/")
    exact = {"AGENTS.md", "CLAUDE.md", ".github/copilot-instructions.md", ".trae/rules/00-aimes-governance.md"}
    prefixes = (".aimes/", "docs/_governance/", "skills/")
    if path in exact or any(path.startswith(prefix) for prefix in prefixes):
        return True
    # 允许遍历必要父目录，但不放行这些目录下的其他本地状态文件。
    return is_dir and any(target.startswith(path.rstrip("/") + "/") for target in exact)

def is_excluded(rel: str, is_dir: bool = False, extra_patterns: tuple[str, ...] | list[str] = ()) -> bool:
    normalized = rel.replace("\\", "/").strip("/")
    parts = normalized.split("/") if normalized else []
    name = parts[-1].lower() if parts else normalized.lower()
    # 密钥、凭证和危险二进制后缀始终优先过滤，AIMES 例外不能绕过这些安全规则。
    if name in EXCLUDED_NAMES or name.startswith(".env.") or Path(name).suffix.lower() in EXCLUDED_SUFFIXES or name.endswith("~"):
        return True
    # AIMES 规则入口、Core、Skill、Manifest 与适配配置不得被通用缓存/IDE 状态规则误过滤。
    if _is_aimes_governance_path(normalized, is_dir):
        return False
    if any(p.lower() in EXCLUDED_DIRS for p in parts): return True
    # 支持 basename glob 和相对路径 glob；只能追加过滤，不能用 ! 取消安全规则。
    for raw in extra_patterns:
        pattern = str(raw).strip().replace("\\", "/").strip("/")
        if not pattern or pattern.startswith("!") or "\x00" in pattern: continue
        if fnmatchcase(normalized, pattern) or any(fnmatchcase(part, pattern) for part in parts): return True
        if pattern.endswith("/**") and (normalized == pattern[:-3].rstrip("/") or normalized.startswith(pattern[:-2])): return True
    return False

def detect_project_profile(source: Path) -> dict[str, Any]:
    """根据项目标志文件识别技术栈，并返回对应的附加过滤规则。"""
    source = source.resolve()
    files = {p.name.lower() for p in source.iterdir() if p.is_file()}
    dirs = {p.name.lower() for p in source.iterdir() if p.is_dir()}
    stacks: list[str] = []
    rules: list[str] = []

    if files.intersection({"pyproject.toml", "setup.py", "setup.cfg", "requirements.txt", "pipfile", "poetry.lock", "uv.lock"}):
        stacks.append("python")
        rules.extend([".coverage", ".nox", "pip-wheel-metadata", "*.egg-info", "__pypackages__"])
    if "package.json" in files or files.intersection({"pnpm-lock.yaml", "yarn.lock", "package-lock.json", "bun.lockb", "bun.lock"}):
        stacks.append("nodejs")
        rules.extend([".next", ".nuxt", ".output", ".svelte-kit", ".angular", ".turbo", ".parcel-cache", ".vite", "playwright-report", "test-results", "storybook-static"])
        package_file = source / "package.json"
        try:
            package = package_file.read_text(encoding="utf-8")
            if '"vue"' in package or "'vue'" in package:
                stacks.append("vue")
            if '"react"' in package or "'react'" in package:
                stacks.append("react")
        except (OSError, UnicodeDecodeError):
            pass
    if files.intersection({"pom.xml", "build.gradle", "build.gradle.kts", "settings.gradle", "settings.gradle.kts", "gradlew"}):
        stacks.append("java")
        rules.extend(["target", ".gradle", "out", "*.class"])
    if "go.mod" in files:
        stacks.append("go")
        rules.extend(["bin"])
    if "cargo.toml" in files:
        stacks.append("rust")
        rules.extend(["target"])
    if any(name.endswith((".sln", ".csproj", ".fsproj", ".vbproj")) for name in files):
        stacks.append("dotnet")
        rules.extend(["bin", "obj", ".vs"])
    if files.intersection({"gemfile", "gemfile.lock"}) or "gemspec" in " ".join(files):
        stacks.append("ruby")
        rules.extend(["vendor/bundle", ".bundle"])
    if files.intersection({"composer.json", "composer.lock"}):
        stacks.append("php")
        rules.extend(["vendor"])
    if files.intersection({"makefile", "cmakelists.txt", "meson.build"}):
        stacks.append("native")
        rules.extend(["cmake-build-debug", "cmake-build-release", "CMakeFiles", "CMakeCache.txt"])

    # 读取常见 .gitignore 规则；忽略反向规则，避免用户自定义的 ! 规则意外绕过安全过滤。
    ignore_file = source / ".gitignore"
    if ignore_file.is_file():
        try:
            for line in ignore_file.read_text(encoding="utf-8-sig").splitlines():
                rule = line.strip()
                if not rule or rule.startswith("#") or rule.startswith("!"):
                    continue
                rules.append(rule)
        except (OSError, UnicodeDecodeError):
            pass
    return {"stacks": list(dict.fromkeys(stacks)) or ["generic"], "rules": list(dict.fromkeys(rules))}


def collect_source_files(source: Path, extra_patterns: tuple[str, ...] | list[str] = ()) -> tuple[dict[str, Path], list[str], list[dict[str, str]]]:
    source = source.resolve()
    if not source.is_dir(): raise ValueError(f"本地源目录不存在或不是目录：{source}")
    if source == Path(source.anchor): raise ValueError("为避免误发布，不能把磁盘/文件系统根目录作为源目录")
    profile = detect_project_profile(source)
    effective_patterns = list(dict.fromkeys([*profile["rules"], *extra_patterns]))
    files, excluded, findings = {}, [], []
    for current, dirs, names in os.walk(source, topdown=True, followlinks=False):
        base = Path(current)
        kept = []
        for name in dirs:
            path = base / name
            rel = path.relative_to(source).as_posix()
            if path.is_symlink() or is_excluded(rel, True, effective_patterns): excluded.append(rel + "/")
            else: kept.append(name)
        dirs[:] = kept
        for name in names:
            path = base / name
            rel = path.relative_to(source).as_posix()
            if path.is_symlink() or is_excluded(rel, extra_patterns=effective_patterns): excluded.append(rel); continue
            try:
                file_size = path.stat().st_size
            except OSError:
                excluded.append(rel + " (无法读取文件大小，已跳过)")
                continue
            if file_size >= MAX_GITHUB_BLOB_BYTES:
                # Prevent a deterministic GitHub HTTP 422 push failure before staging/commit.
                excluded.append(rel + " (单文件接近/超过 GitHub 2 GiB 限制，已自动排除)")
                continue
            files[rel] = path
            try:
                if file_size > MAX_SCAN_BYTES: continue
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

def publish_project(source: Path, repository: str, branch: str | None = None, apply: bool = False, confirm: str | None = None, message: str = "chore: mirror local project with AIMES", excludes: list[str] | None = None) -> dict[str, Any]:
    source = source.expanduser().resolve()
    url, repo_name = normalize_repository(repository)
    if branch: validate_branch(branch)
    if apply and confirm != "PUBLISH": raise ValueError("执行发布必须同时提供 --apply --confirm PUBLISH")
    extra_patterns = list(dict.fromkeys(excludes or []))
    if any(not rule.strip() or "\x00" in rule or rule.strip().startswith("!") for rule in extra_patterns):
        raise ValueError("自定义排除规则不能为空、不能包含 NUL，也不支持以 ! 开头的反向规则")
    source_files, excluded, findings = collect_source_files(source, extra_patterns)
    if not source_files: raise ValueError("源目录没有可发布文件；为避免清空远端仓库，已停止")
    if apply and findings:
        raise ValueError("源文件疑似包含密钥/令牌，已阻止发布：" + ", ".join(x["path"] for x in findings[:10]) + "。请移除密钥后重新预览。")
    with tempfile.TemporaryDirectory(prefix="aimes-publish-") as temp:
        clone = Path(temp) / "repo"
        # 先检查远端引用。新建但尚无提交的 GitHub 仓库没有 HEAD，不能直接 rev-parse HEAD。
        remote_refs = git_run(["ls-remote", "--heads", url], timeout=240)
        remote_head = git_run(["ls-remote", "--symref", url, "HEAD"], timeout=240)
        head_match = re.search(r"^ref:\s+refs/heads/([^\s]+)\s+HEAD$", remote_head, re.MULTILINE)
        remote_default_branch = head_match.group(1) if head_match else None
        remote_has_refs = bool(remote_refs.strip())
        if branch and remote_has_refs:
            available_branches = {
                line.split("\t", 1)[1].removeprefix("refs/heads/")
                for line in remote_refs.splitlines() if "\trefs/heads/" in line
            }
            if branch not in available_branches:
                raise ValueError(f"远端仓库不存在目标分支：{branch}。请填写已有分支，或在空仓库中指定要创建的分支。")
        clone_args = ["clone", "--quiet"]
        if branch and remote_has_refs:
            clone_args += ["--branch", branch, "--single-branch"]
        clone_args += [url, str(clone)]
        git_run(clone_args, timeout=240)

        if remote_has_refs:
            actual_branch = git_run(["branch", "--show-current"], cwd=clone)
            if branch and actual_branch != branch: raise ValueError(f"克隆到的分支与请求不一致：{actual_branch} != {branch}")
            base_sha = git_run(["rev-parse", "HEAD"], cwd=clone)
        else:
            # 空仓库没有提交：使用用户指定分支、远端声明的默认分支，最后回退到 main。
            actual_branch = branch or remote_default_branch or "main"
            validate_branch(actual_branch)
            git_run(["symbolic-ref", "HEAD", f"refs/heads/{actual_branch}"], cwd=clone)
            base_sha = None

        plan = build_change_plan(source_files, _target_snapshot(clone))
        report: dict[str, Any] = {"ok": True, "mode": "apply" if apply else "dry-run", "repository": repo_name, "branch": actual_branch, "source": str(source), "source_file_count": len(source_files), "excluded_count": len(excluded), "excluded_preview": excluded[:100], "detected_stacks": detect_project_profile(source)["stacks"], "auto_excludes": detect_project_profile(source)["rules"], "custom_excludes": extra_patterns, "secret_findings": findings, "changes": plan, "change_counts": {k: len(v) for k, v in plan.items()}, "base_commit": base_sha, "remote_empty": not remote_has_refs, "commit": None, "warning": "根目录完整镜像会删除本地源目录中不存在的远端文件；不会修改 .git 元数据，且不会强制推送。"}
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
