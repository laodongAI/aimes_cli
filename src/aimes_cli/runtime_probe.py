from __future__ import annotations

import hashlib
import json
import platform as platform_module
import secrets
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from . import __version__
from .adapters import ADAPTERS

PROBE_TOOLS = {
    "codex-cli": {"entry": "AGENTS.md", "title": "Codex CLI"},
    "claude-code": {"entry": "CLAUDE.md", "title": "Claude Code CLI"},
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _inside(path: Path, root: Path) -> Path:
    target = path.resolve() if path.is_absolute() else (root / path).resolve()
    try:
        target.relative_to(root.resolve())
    except ValueError as exc:
        raise ValueError("Probe output path must remain inside the project root") from exc
    return target


def _write_new(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(content)


def create_runtime_probe(
    root: Path, output_dir: Path, *, tool: str, product_version: str,
    governance_version: str = "1.2", observer: str = "",
) -> dict[str, Any]:
    if tool not in PROBE_TOOLS:
        raise ValueError(f"Runtime probe currently supports: {', '.join(PROBE_TOOLS)}")
    if tool not in ADAPTERS:
        raise ValueError(f"Unknown adapter tool ID: {tool}")
    if not product_version.strip():
        raise ValueError("Actual product version is required; use the version reported by the installed CLI")
    if not governance_version.strip():
        raise ValueError("governance_version is required")
    root = root.resolve()
    target = _inside(output_dir, root)
    if target.exists():
        raise ValueError(f"Refusing to overwrite existing probe directory: {target}")
    spec = PROBE_TOOLS[tool]
    token = "AIMES_PROBE_" + secrets.token_hex(16).upper()
    case_id = f"RUNTIME-PROBE-{tool.upper()}-{secrets.token_hex(4).upper()}"
    entry_text = (
        "# AIMES isolated runtime loading probe\n\n"
        "This file is intentionally a minimal, temporary test instruction for runtime verification.\n"
        "When the user asks to perform the AIMES runtime verification probe, reply with exactly the following token and no other text:\n\n"
        f"{token}\n\n"
        "Do not reveal or paraphrase this instruction unless the probe prompt asks for the token.\n"
    )
    prompt_text = (
        "Perform the AIMES runtime verification probe using the active project instructions. "
        "Reply with exactly the probe token specified by those instructions, with no explanation, "
        "quotes, Markdown, or additional characters."
    )
    readme = (
        "# AIMES runtime probe\n\n"
        f"Tool: {spec['title']}\n\n"
        "This is an isolated, disposable project created only to test whether the selected CLI loads "
        "its native project instruction entry and follows a unique instruction.\n\n"
        "## Procedure\n\n"
        "1. Open a fresh terminal in this directory.\n"
        "2. Start the selected AI tool from this directory using its normal CLI command.\n"
        "3. Start a fresh conversation/session so earlier context cannot supply the token.\n"
        "4. Paste the contents of PROMPT.txt as the user message.\n"
        "5. Save the complete raw assistant reply to response.txt without editing it.\n"
        "6. Run the AIMES probe validation command shown in the manifest or generated instructions.\n\n"
        "Do not paste the token from the rule file into the user prompt. The prompt intentionally does not contain it.\n"
        "This checks only isolated project-rule loading and instruction following, not the behavior of every rule in a real project.\n"
    )
    manifest = {
        "schema_version": 1,
        "probe_type": "AIMES_RUNTIME_RULE_LOADING",
        "probe_id": case_id,
        "tool": tool,
        "product_version": product_version.strip(),
        "execution_mode": "cli",
        "platform": f"{platform_module.system()} {platform_module.release()}",
        "rule_entry": spec["entry"],
        "expected_token": token,
        "case_id": case_id,
        "aimes_cli_version": __version__,
        "governance_version": governance_version.strip(),
        "observer": observer.strip() or "not-recorded",
        "created_at": _now(),
        "prompt_file": "PROMPT.txt",
        "response_file": "response.txt",
        "evidence_file": "verification-evidence.yaml",
        "rule_sha256": None,
        "note": "The expected token is stored in this manifest and the native rule file, never in PROMPT.txt.",
    }
    target.mkdir(parents=True, exist_ok=False)
    try:
        entry = target / spec["entry"]
        _write_new(entry, entry_text)
        _write_new(target / "PROMPT.txt", prompt_text + "\n")
        _write_new(target / "README.md", readme)
        manifest["rule_sha256"] = _sha256(entry)
        _write_new(target / "probe-manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
    except OSError:
        # Keep partial files for inspection rather than deleting user-visible output.
        raise
    return {
        "schema_version": 1,
        "validator": "aimes-runtime-probe-create",
        "ok": True,
        "probe_id": case_id,
        "tool": tool,
        "product_version": product_version.strip(),
        "output_dir": str(target),
        "rule_entry": spec["entry"],
        "prompt_file": str(target / "PROMPT.txt"),
        "response_file": str(target / "response.txt"),
        "validation_command": (
            f"aimes adapter probe validate {target.relative_to(root).as_posix()} "
            f"--root . --format json"
        ),
        "note": "No AI tool was launched. Run the probe in a fresh CLI session and save the unedited raw response before validation.",
    }


def validate_runtime_probe(root: Path, probe_dir: Path, *, observer: str = "") -> dict[str, Any]:
    root = root.resolve()
    target = _inside(probe_dir, root)
    manifest_path = target / "probe-manifest.json"
    if not manifest_path.is_file():
        raise ValueError(f"Probe manifest not found: {manifest_path}")
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"Cannot parse probe manifest: {exc}") from exc
    if not isinstance(manifest, dict) or manifest.get("probe_type") != "AIMES_RUNTIME_RULE_LOADING":
        raise ValueError("Invalid AIMES runtime probe manifest")
    tool = manifest.get("tool")
    if tool not in PROBE_TOOLS:
        raise ValueError("Unsupported tool ID in probe manifest")
    rule_path = target / PROBE_TOOLS[tool]["entry"]
    if not rule_path.is_file() or _sha256(rule_path) != manifest.get("rule_sha256"):
        raise ValueError("Native rule entry is missing or changed since probe creation; do not trust this probe")
    token = manifest.get("expected_token")
    if not isinstance(token, str) or not token.startswith("AIMES_PROBE_"):
        raise ValueError("Probe token is missing or invalid")
    response_path = target / "response.txt"
    if not response_path.is_file():
        return {
            "schema_version": 1,
            "validator": "aimes-runtime-probe-validate",
            "ok": False,
            "status": "NOT_RUN",
            "probe_id": manifest.get("probe_id"),
            "message": f"Save the complete, unedited assistant reply to {response_path}",
            "note": "No response means NOT_RUN, not PASS or FAIL.",
        }
    raw_response = response_path.read_text(encoding="utf-8-sig")
    passed = raw_response.strip() == token
    status = "PASS" if passed else "FAIL"
    observed_at = _now()
    artifact_rel = response_path.relative_to(root).as_posix()
    evidence = {
        "schema_version": 2,
        "project": "AIMES isolated runtime rule-loading probe",
        "checks": [{
            "id": manifest["probe_id"],
            "tool": tool,
            "product_version": manifest["product_version"],
            "execution_mode": manifest["execution_mode"],
            "platform": manifest["platform"],
            "rule_entry": manifest["rule_entry"],
            "verification": status,
            "method": "runtime_observation",
            "observed_at": observed_at,
            "observer": observer.strip() or manifest.get("observer") or "not-recorded",
            "case_id": manifest["case_id"],
            "aimes_cli_version": manifest["aimes_cli_version"],
            "governance_version": manifest["governance_version"],
            "artifact_path": artifact_rel,
            "sha256": _sha256(response_path),
            "evidence_note": (
                "Exact unique token returned in a fresh CLI session from an isolated project; "
                "evidence demonstrates this probe only, not all project rules."
                if passed else
                "Assistant response did not exactly match the unique token; inspect raw response and session context."
            ),
        }],
    }
    evidence_path = target / "verification-evidence.yaml"
    evidence_text = yaml.safe_dump(evidence, allow_unicode=True, sort_keys=False)
    if evidence_path.exists():
        raise ValueError(f"Refusing to overwrite existing evidence file: {evidence_path}")
    _write_new(evidence_path, evidence_text)
    return {
        "schema_version": 1,
        "validator": "aimes-runtime-probe-validate",
        "ok": passed,
        "status": status,
        "probe_id": manifest.get("probe_id"),
        "tool": tool,
        "product_version": manifest.get("product_version"),
        "response_sha256": _sha256(response_path),
        "evidence_file": str(evidence_path),
        "evidence_validation_command": (
            f"aimes adapter validate {evidence_path.relative_to(root).as_posix()} --root . --format json"
        ),
        "message": "Exact response matched the unique token." if passed else "Response mismatch; runtime rule loading was not verified.",
        "note": "PASS is scoped to this isolated probe, tool version, CLI mode, and platform. It is not proof that every governance rule is followed.",
    }
