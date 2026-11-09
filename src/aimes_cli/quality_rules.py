from __future__ import annotations

import ast
import hashlib
import json
from fnmatch import fnmatch
import os
from pathlib import Path
import re
import xml.etree.ElementTree as ET
from typing import Any

MAX_SOURCE_FILES = 500
MAX_SOURCE_BYTES = 1024 * 1024
SOURCE_SKIP_PARTS = {".git", ".venv", "venv", "node_modules", "dist", "build", "__pycache__", ".pytest_cache", ".mypy_cache", ".tox", ".aimes"}

SECRET_ASSIGNMENT = re.compile(
    r"""(?i)\b(?:api[_-]?key|secret|password|passwd|access[_-]?token)\b\s*[:=]\s*['"]([^'"]{8,})['"]"""
)
VUE_PROP_MUTATION = re.compile(
    r"""\bprops\s*\.\s*[A-Za-z_$][\w$]*(?:\s*\.\s*[A-Za-z_$][\w$]*)*\s*(?:=(?!=)|\.(?:push|pop|shift|unshift|splice|sort|reverse)\s*\()"""
)
VUE_LITERAL_COLOR = re.compile(r"""(?:#[0-9a-fA-F]{3,8}\b|\brgba?\s*\(|\bhsla?\s*\()""")
DECISION_NODES = (ast.If, ast.For, ast.AsyncFor, ast.While, ast.IfExp, ast.ExceptHandler, ast.With, ast.AsyncWith, ast.Assert)


def _finding(code: str, path: str, line: int, message: str, recommendation: str,
             severity: str = "WARNING", evidence: str | None = None, category: str = "maintainability") -> dict[str, Any]:
    item = {
        "severity": severity, "code": code, "category": category, "path": path,
        "line": max(1, int(line)), "message": message, "recommendation": recommendation,
        "origin": "static",
    }
    if evidence:
        item["evidence"] = evidence[:240]
    return item


def _function_complexity(node: ast.FunctionDef | ast.AsyncFunctionDef) -> int:
    return 1 + sum(isinstance(child, DECISION_NODES) for child in ast.walk(node))


def _is_route_handler(node: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    return any(isinstance(decorator, ast.Call) and isinstance(decorator.func, ast.Attribute)
               and decorator.func.attr.lower() in {"get", "post", "put", "patch", "delete"}
               for decorator in node.decorator_list)


def inspect_python_file(path: str, content: str, config: dict[str, Any]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    lines = content.splitlines()
    settings = config.get("python", {})
    if len(lines) > settings.get("max_file_lines", 800):
        findings.append(_finding("PYTHON_FILE_LINES", path, 1,
            f"Python file contains {len(lines)} lines (limit {settings.get('max_file_lines', 800)}).",
            "Split the module by cohesive responsibility and keep public contracts explicit."))

    for match in SECRET_ASSIGNMENT.finditer(content):
        literal = match.group(1).lower()
        if any(marker in literal for marker in ("example", "dummy", "test", "fake", "placeholder", "changeme", "your_", "xxx")):
            continue
        line = content.count("\n", 0, match.start()) + 1
        findings.append(_finding("PYTHON_POSSIBLE_SECRET", path, line,
            "A credential-like assignment contains a hard-coded string literal.",
            "Load credentials from environment variables or a secret manager; rotate any real exposed credential.",
            severity="ERROR", evidence=match.group(0), category="security"))

    try:
        tree = ast.parse(content, filename=path)
    except SyntaxError as exc:
        findings.append(_finding("PYTHON_SYNTAX", path, exc.lineno or 1,
            f"Python source cannot be parsed: {exc.msg}",
            "Fix the syntax error before relying on further static findings.", severity="ERROR", category="correctness"))
        return findings

    normalized_path = path.replace("\\", "/").lower()
    if any(segment in normalized_path.split("/") for segment in ("api", "router", "routers", "routes")):
        for imported in ast.walk(tree):
            if isinstance(imported, ast.ImportFrom) and imported.module and re.search(r"(?:^|\.)(?:repositories|repository|models|database|db)(?:\.|$)", imported.module):
                findings.append(_finding("FASTAPI_LAYER_IMPORT", path, imported.lineno,
                    "API/router module imports a persistence-layer module directly.",
                    "Prefer API -> service -> repository dependency direction; document intentional architecture exceptions.",
                    category="architecture"))
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            end = getattr(node, "end_lineno", node.lineno)
            function_lines = end - node.lineno + 1
            if function_lines > settings.get("max_function_lines", 80):
                findings.append(_finding("PYTHON_FUNCTION_LINES", path, node.lineno,
                    f"Function {node.name} spans {function_lines} lines.",
                    "Extract cohesive operations and keep orchestration separate from domain logic."))
            complexity = _function_complexity(node)
            if complexity > settings.get("max_cyclomatic_complexity", 12):
                findings.append(_finding("PYTHON_COMPLEXITY", path, node.lineno,
                    f"Function {node.name} has an estimated decision complexity of {complexity}.",
                    "Reduce branching with guard clauses, focused helpers, or explicit strategy objects."))
            defaults = list(node.args.defaults) + [value for value in node.args.kw_defaults if value is not None]
            for default in defaults:
                if isinstance(default, (ast.List, ast.Dict, ast.Set)):
                    findings.append(_finding("PYTHON_MUTABLE_DEFAULT", path, default.lineno,
                        f"Function {node.name} uses a mutable default argument.",
                        "Use None as the default and create a new mutable value inside the function.",
                        severity="ERROR", category="correctness"))
                    break
            if _is_route_handler(node):
                for call in (child for child in ast.walk(node) if isinstance(child, ast.Call)):
                    func = call.func
                    if isinstance(func, ast.Attribute) and func.attr in {"execute", "commit", "flush", "add", "delete", "query"}:
                        findings.append(_finding("FASTAPI_ROUTE_DATA_ACCESS", path, call.lineno,
                            f"Route handler {node.name} performs direct data-session operation ({func.attr}).",
                            "Move persistence and transaction boundaries into the project's service/repository layer; preserve existing architecture conventions.",
                            category="architecture"))
                        break
        elif isinstance(node, ast.ExceptHandler) and isinstance(node.type, ast.Name) and node.type.id in {"Exception", "BaseException"}:
            findings.append(_finding("PYTHON_BROAD_EXCEPTION", path, node.lineno,
                f"Broad exception handler catches {node.type.id}.",
                "Catch expected exception types, preserve causal context, and avoid swallowing cancellation or programming errors.",
                category="reliability"))

    return findings


def inspect_vue_file(path: str, content: str, config: dict[str, Any]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    vue = config.get("vue", {})
    if vue.get("check_prop_mutation", True):
        for match in VUE_PROP_MUTATION.finditer(content):
            line = content.count("\n", 0, match.start()) + 1
            findings.append(_finding("VUE_PROP_MUTATION", path, line,
                "Component code appears to mutate a prop or a nested value received through props.",
                "Treat props as read-only; emit an update event or copy the value into explicitly owned local state.",
                severity="ERROR", evidence=match.group(0), category="correctness"))
    if vue.get("check_hardcoded_colors", True):
        in_style = False
        for line_number, line in enumerate(content.splitlines(), 1):
            lower = line.lower()
            if "<style" in lower:
                in_style = True
            stripped = line.strip()
            if not stripped.startswith(("<!--", "//", "*", "/*")) and (in_style or "<template" in stripped or "style" in lower or "class=" in stripped) and VUE_LITERAL_COLOR.search(line):
                findings.append(_finding("VUE_HARDCODED_COLOR", path, line_number,
                    "Vue markup or style contains a literal color value.",
                    "Prefer the project's approved design tokens or theme variables; retain literals only for documented exceptions.",
                    evidence=line.strip(), category="ui"))
            if "</style" in lower:
                in_style = False
    script_blocks = re.findall(r"<script(?:\s[^>]*)?>([\s\S]*?)</script\s*>", content, flags=re.IGNORECASE)
    stateful_calls = sum(len(re.findall(r"\b(?:ref|reactive|computed|watch|watchEffect)\s*\(", block)) for block in script_blocks)
    if stateful_calls > 12:
        findings.append(_finding("VUE_STATEFUL_LOGIC_DENSITY", path, 1,
            f"Vue component contains {stateful_calls} state/reactivity calls.",
            "Review whether cohesive stateful logic belongs in a focused Composable; this heuristic is advisory and does not require extraction by itself.",
            category="architecture"))
    return findings


def inspect_general_file(path: str, content: str, config: dict[str, Any]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    settings = config.get("general", {})
    lines = content.splitlines()
    if len(lines) > settings.get("max_source_file_lines", 1000):
        findings.append(_finding("SOURCE_FILE_LINES", path, 1,
            f"Source file contains {len(lines)} lines.",
            "Split by cohesive responsibility and keep modules independently testable."))
    return findings


def _inspect_dependency_manifests(root: Path) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    for manifest in sorted(root.glob("requirements*.txt")):
        if manifest.is_symlink() or not manifest.is_file():
            continue
        try:
            lines = manifest.read_text(encoding="utf-8-sig").splitlines()
        except (OSError, UnicodeError):
            continue
        for number, raw in enumerate(lines, 1):
            line = raw.strip()
            if not line or line.startswith(("#", "-", "http://", "https://")):
                continue
            if re.match(r"^[A-Za-z0-9_.-]+$", line):
                findings.append(_finding("DEPENDENCY_UNPINNED", manifest.name, number,
                    f"Dependency {line} has no version constraint.",
                    "Use a reviewed version range or lockfile; this check does not assess known CVEs.",
                    category="dependency"))
    package_json = root / "package.json"
    if package_json.is_file() and not package_json.is_symlink():
        try:
            payload = json.loads(package_json.read_text(encoding="utf-8-sig"))
            if isinstance(payload, dict):
                for section in ("dependencies", "devDependencies", "optionalDependencies"):
                    values = payload.get(section, {})
                    if isinstance(values, dict):
                        for name, version in values.items():
                            if isinstance(version, str) and version in {"*", "latest"}:
                                findings.append(_finding("DEPENDENCY_WILDCARD", "package.json", 1,
                                    f"{section}.{name} uses the floating version specifier {version}.",
                                    "Pin a reviewed version range and commit the package manager lockfile.",
                                    category="dependency"))
        except (OSError, UnicodeError, json.JSONDecodeError):
            findings.append(_finding("DEPENDENCY_MANIFEST_INVALID", "package.json", 1,
                "package.json could not be parsed for dependency policy checks.",
                "Validate the manifest with the project's package manager.", category="dependency"))
    return findings


def _inspect_coverage(root: Path, config: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    threshold = config.get("general", {}).get("min_coverage_percent")
    report_xml = root / "coverage.xml"
    report_json = root / "coverage.json"
    report = report_xml if report_xml.is_file() and not report_xml.is_symlink() else report_json if report_json.is_file() and not report_json.is_symlink() else None
    metadata: dict[str, Any] = {"status": "NOT_PROVIDED", "percent": None, "threshold": threshold}
    if report is None:
        if threshold is not None:
            return [_finding("COVERAGE_REPORT_MISSING", "coverage.xml", 1,
                "A coverage threshold is configured but no coverage.xml or coverage.json report was found.",
                "Run the project's tests with coverage reporting and provide the generated report.",
                category="testing")], metadata
        return [], metadata
    try:
        if report.suffix == ".xml":
            payload = ET.parse(report).getroot()
            percent = float(payload.attrib["line-rate"]) * 100
        else:
            payload = json.loads(report.read_text(encoding="utf-8-sig"))
            percent = float(payload["totals"]["percent_covered"])
    except (OSError, ValueError, KeyError, TypeError, ET.ParseError, json.JSONDecodeError):
        metadata["status"] = "INVALID"
        return [_finding("COVERAGE_REPORT_INVALID", report.name, 1,
            "Coverage report is malformed or does not contain a valid total line coverage value.",
            "Regenerate the report using the project's coverage.py XML/JSON format.",
            category="testing")], metadata
    metadata.update({"status": "AVAILABLE", "percent": round(percent, 2)})
    if threshold is not None and percent < threshold:
        return [_finding("COVERAGE_BELOW_THRESHOLD", report.name, 1,
            f"Measured line coverage is {percent:.2f}%, below the configured {threshold}% threshold.",
            "Add focused tests for uncovered behavior and inspect the coverage report before raising the threshold.",
            category="testing")], metadata
    return [], metadata


def inspect_project_sources(root: Path, config: dict[str, Any], exclude_patterns: list[str] | None = None) -> tuple[list[dict[str, Any]], dict[str, int]]:
    findings: list[dict[str, Any]] = []
    counts = {"python_files_scanned": 0, "vue_files_scanned": 0, "source_files_scanned": 0, "files_skipped": 0}
    findings.extend(_inspect_dependency_manifests(root))
    coverage_findings, coverage_metadata = _inspect_coverage(root, config)
    findings.extend(coverage_findings)
    counts["coverage"] = coverage_metadata
    candidates: list[tuple[str, Path]] = []
    duplicate_functions: dict[str, list[tuple[str, str, int]]] = {}
    patterns = exclude_patterns or []
    for current, dirs, files in os.walk(root, followlinks=False):
        current_path = Path(current)
        dirs[:] = [name for name in dirs if name not in SOURCE_SKIP_PARTS and not (current_path / name).is_symlink() and not any(fnmatch((current_path / name).relative_to(root).as_posix(), pattern) for pattern in patterns)]
        for name in files:
            path = current_path / name
            if path.is_symlink() or path.suffix.lower() not in {".py", ".vue"}:
                continue
            relative = path.relative_to(root).as_posix()
            if any(fnmatch(relative, pattern) for pattern in patterns):
                continue
            candidates.append((relative, path))
            if len(candidates) >= MAX_SOURCE_FILES:
                break
        if len(candidates) >= MAX_SOURCE_FILES:
            break

    for relative, path in sorted(candidates):
        try:
            if path.stat().st_size > MAX_SOURCE_BYTES:
                counts["files_skipped"] += 1
                continue
            content = path.read_text(encoding="utf-8-sig")
        except (OSError, UnicodeError):
            counts["files_skipped"] += 1
            continue
        counts["source_files_scanned"] += 1
        findings.extend(inspect_general_file(relative, content, config))
        if path.suffix.lower() == ".py":
            counts["python_files_scanned"] += 1
            findings.extend(inspect_python_file(relative, content, config))
            try:
                tree = ast.parse(content, filename=relative)
                for node in ast.walk(tree):
                    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and len(node.body) >= 6:
                        body = ast.Module(body=node.body, type_ignores=[])
                        fingerprint = hashlib.sha256(ast.dump(body, include_attributes=False).encode("utf-8")).hexdigest()
                        duplicate_functions.setdefault(fingerprint, []).append((relative, node.name, node.lineno))
            except SyntaxError:
                pass
        elif path.suffix.lower() == ".vue":
            counts["vue_files_scanned"] += 1
            findings.extend(inspect_vue_file(relative, content, config))

    for occurrences in duplicate_functions.values():
        if len({item[0] for item in occurrences}) > 1:
            for relative, name, line in occurrences:
                findings.append(_finding("PYTHON_DUPLICATE_FUNCTION", relative, line,
                    f"Function {name} has an identical AST body in another source file.",
                    "Review whether this duplication is intentional; extract a shared helper only when responsibility and change reasons are genuinely common.",
                    category="maintainability"))
    return findings, counts
