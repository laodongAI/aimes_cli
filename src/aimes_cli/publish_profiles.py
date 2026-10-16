"""本地发布配置档案：不保存 GitHub 认证凭据。"""
from __future__ import annotations
import json, os
from pathlib import Path
from typing import Any

def config_path() -> Path:
    base = os.environ.get("AIMES_CONFIG_HOME")
    root = Path(base).expanduser() if base else Path.home() / ".aimes"
    return root / "publish-profiles.json"

def load_profiles() -> dict[str, dict[str, Any]]:
    path = config_path()
    if not path.exists(): return {}
    try: raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc: raise ValueError(f"无法读取发布配置文件 {path}：{exc}") from exc
    profiles = raw.get("profiles", {}) if isinstance(raw, dict) else None
    if not isinstance(profiles, dict): raise ValueError(f"发布配置格式错误：{path}")
    return {name: value for name, value in profiles.items() if isinstance(name, str) and isinstance(value, dict)}

def save_profile(name: str, profile: dict[str, Any]) -> Path:
    normalized = name.strip()
    invalid = '\\/:*?"<>|'
    if not normalized or len(normalized) > 64 or any(c in normalized for c in invalid):
        raise ValueError('配置名称不能为空，且不能超过 64 个字符或包含 \\ / : * ? " < > |')
    path = config_path()
    profiles = load_profiles()
    profiles[normalized] = {
        "source": str(profile["source"]), "repository": str(profile["repository"]),
        "branch": str(profile.get("branch") or ""),
        "message": str(profile.get("message") or "chore: mirror local project with AIMES"),
        "excludes": list(profile.get("excludes") or []),
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"version": 1, "profiles": profiles}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path
