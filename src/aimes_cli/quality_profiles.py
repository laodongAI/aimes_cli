from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

import yaml

PROFILE_REGISTRY_PATH = Path(".aimes/quality-profiles.yaml")
BUILTIN_REGISTRY: dict[str, Any] = {
    "schema_version": 1,
    "registry_version": "1.0.0",
    "default_profile": "baseline",
    "description": "AIMES 模式质量配置注册表。项目 quality-gates.yaml 的显式设置优先于 profile 默认值；enforce/fail_on 始终由项目全局门禁控制。",
    "profiles": {
        "baseline": {
            "description": "baseline 工程质量基线；提供对应工程模式的静态检查默认值；未实现的领域不会被宣称为已覆盖。",
            "vue": {},
            "python": {},
            "general": {}
        },
        "requirements": {
            "description": "requirements 工程质量基线；仅调整当前已实现的 Vue 静态检查阈值，不替代专项审查。",
            "vue": {}
        },
        "architecture": {
            "description": "architecture 工程质量基线；仅调整当前已实现的 Vue 静态检查阈值，不替代专项审查。",
            "vue": {}
        },
        "implementation": {
            "description": "implementation 工程质量基线；仅调整当前已实现的 Vue 静态检查阈值，不替代专项审查。",
            "vue": {
                "max_sfc_lines": {
                    "warning": 400,
                    "error": 600
                },
                "max_script_lines": {
                    "warning": 250,
                    "error": 400
                },
                "max_template_lines": {
                    "warning": 250,
                    "error": 400
                }
            }
        },
        "backend": {
            "description": "FastAPI/Python backend quality baseline with conservative AST-based checks.",
            "vue": {},
            "python": {"max_file_lines": 700, "max_function_lines": 70, "max_cyclomatic_complexity": 10},
            "general": {"max_source_file_lines": 1000}
        },
        "frontend": {
            "description": "frontend 工程质量基线；仅调整当前已实现的 Vue 静态检查阈值，不替代专项审查。",
            "vue": {
                "max_sfc_lines": {
                    "warning": 350,
                    "error": 500
                },
                "max_script_lines": {
                    "warning": 220,
                    "error": 350
                },
                "max_template_lines": {
                    "warning": 220,
                    "error": 350
                }
            }
        },
        "regression": {
            "description": "Regression profile; requires measured line coverage of at least 80% when selected.",
            "vue": {"disallow_direct_http_calls": True},
            "general": {"min_coverage_percent": 80}
        },
        "performance": {
            "description": "performance 工程质量基线；仅调整当前已实现的 Vue 静态检查阈值，不替代专项审查。",
            "vue": {}
        },
        "security": {
            "description": "security 工程质量基线；仅调整当前已实现的 Vue 静态检查阈值，不替代专项审查。",
            "vue": {}
        },
        "release": {
            "description": "release 工程质量基线；仅调整当前已实现的 Vue 静态检查阈值，不替代专项审查。",
            "vue": {}
        },
        "documentation": {
            "description": "documentation 工程质量基线；仅调整当前已实现的 Vue 静态检查阈值，不替代专项审查。",
            "vue": {}
        },
        "delivery": {
            "description": "delivery 工程质量基线；仅调整当前已实现的 Vue 静态检查阈值，不替代专项审查。",
            "vue": {}
        },
        "operations": {
            "description": "operations 工程质量基线；仅调整当前已实现的 Vue 静态检查阈值，不替代专项审查。",
            "vue": {}
        },
        "ai-evaluation": {
            "description": "ai-evaluation 工程质量基线；仅调整当前已实现的 Vue 静态检查阈值，不替代专项审查。",
            "vue": {}
        },
        "reliability": {
            "description": "reliability 工程质量基线；仅调整当前已实现的 Vue 静态检查阈值，不替代专项审查。",
            "vue": {}
        },
        "migration": {
            "description": "migration 工程质量基线；仅调整当前已实现的 Vue 静态检查阈值，不替代专项审查。",
            "vue": {}
        },
        "audit": {
            "description": "audit 工程质量基线；仅调整当前已实现的 Vue 静态检查阈值，不替代专项审查。",
            "vue": {
                "max_sfc_lines": {
                    "warning": 350,
                    "error": 500
                },
                "max_script_lines": {
                    "warning": 220,
                    "error": 350
                },
                "max_template_lines": {
                    "warning": 220,
                    "error": 350
                },
                "disallow_direct_http_calls": True
            }
        }
    }
}


def _merge(target: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    result = deepcopy(target)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _merge(result[key], value)
        else:
            result[key] = deepcopy(value)
    return result


def load_quality_profiles(root: Path) -> tuple[dict[str, Any], str | None]:
    base = root.resolve()
    path = (base / PROFILE_REGISTRY_PATH).resolve()
    try:
        path.relative_to(base)
    except ValueError as exc:
        raise ValueError("Quality profile registry path escapes project root") from exc
    if not path.is_file():
        return deepcopy(BUILTIN_REGISTRY), "BUILTIN_FALLBACK"
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8-sig"))
    except (OSError, yaml.YAMLError) as exc:
        raise ValueError(f"Cannot read quality profile registry {path}: {exc}") from exc
    if not isinstance(raw, dict) or raw.get("schema_version") != 1:
        raise ValueError("Quality profile registry must be a schema_version: 1 mapping")
    profiles = raw.get("profiles")
    default_id = raw.get("default_profile")
    if not isinstance(profiles, dict) or not profiles:
        raise ValueError("Quality profile registry profiles must be a non-empty mapping")
    if not isinstance(default_id, str) or default_id not in profiles:
        raise ValueError("Quality profile registry default_profile must reference a declared profile")
    for profile_id, profile in profiles.items():
        if not isinstance(profile_id, str) or not isinstance(profile, dict):
            raise ValueError("Each quality profile must be a named mapping")
        if not isinstance(profile.get("description", ""), str):
            raise ValueError(f"Profile {profile_id} description must be a string")
        vue = profile.get("vue", {})
        if not isinstance(vue, dict):
            raise ValueError(f"Profile {profile_id} vue settings must be a mapping")
        for key in ("max_sfc_lines", "max_script_lines", "max_template_lines"):
            if key not in vue:
                continue
            limits = vue[key]
            if not isinstance(limits, dict) or set(limits) != {"warning", "error"}:
                raise ValueError(f"Profile {profile_id} vue.{key} must define warning and error")
            warning, error = limits["warning"], limits["error"]
            if type(warning) is not int or type(error) is not int or warning < 1 or error <= warning:
                raise ValueError(f"Profile {profile_id} vue.{key} requires positive integer thresholds and error > warning")
        for boolean_rule in ("disallow_direct_http_calls", "check_prop_mutation", "check_hardcoded_colors"):
            if boolean_rule in vue and type(vue[boolean_rule]) is not bool:
                raise ValueError(f"Profile {profile_id} vue.{boolean_rule} must be a boolean")
        unknown = set(vue) - {"max_sfc_lines", "max_script_lines", "max_template_lines", "disallow_direct_http_calls", "check_prop_mutation", "check_hardcoded_colors"}
        if unknown:
            raise ValueError(f"Profile {profile_id} contains unsupported Vue rules: {', '.join(sorted(unknown))}")
        for section, allowed in {
            "python": {"max_file_lines", "max_function_lines", "max_cyclomatic_complexity"},
            "general": {"max_source_file_lines", "min_coverage_percent"},
        }.items():
            values = profile.get(section, {})
            if not isinstance(values, dict):
                raise ValueError(f"Profile {profile_id} {section} settings must be a mapping")
            unsupported = set(values) - allowed
            if unsupported:
                raise ValueError(f"Profile {profile_id} contains unsupported {section} rules")
            for key, value in values.items():
                if type(value) not in (int, float) or (value < 0 if key == "min_coverage_percent" else value < 1) or (key == "min_coverage_percent" and value > 100):
                    raise ValueError(f"Profile {profile_id} {section}.{key} has an invalid numeric value")
    return raw, None


def resolve_quality_profile(root: Path, profile_id: str | None = None) -> dict[str, Any]:
    registry, source_status = load_quality_profiles(root)
    selected = profile_id or registry["default_profile"]
    profiles = registry["profiles"]
    if selected not in profiles:
        raise ValueError(f"Unknown quality profile: {selected}")
    profile = profiles[selected]
    return {
        "id": selected,
        "description": profile.get("description", ""),
        "overrides": {key: deepcopy(profile.get(key, {})) for key in ("vue", "python", "general")},
        "registry_status": source_status or "PROJECT_CONFIGURED",
        "registry_path": PROFILE_REGISTRY_PATH.as_posix() if source_status is None else None,
    }
