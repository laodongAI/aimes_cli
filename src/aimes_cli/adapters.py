from dataclasses import dataclass
from pathlib import PurePosixPath

@dataclass(frozen=True)
class Adapter:
    key: str
    label: str
    status: str
    paths: tuple[str, ...]
    description: str
    detection_commands: tuple[str, ...] = ()

ADAPTERS = {
    "trae-code": Adapter("trae-code", "Trae Code", "template", (".trae/rules/00-aimes-governance.md",), "Trae project rule entry; verify loading in the installed version.", ("trae",)),
    "vscode-codex": Adapter("vscode-codex", "VS Code + Codex", "template", ("AGENTS.md",), "Uses the Codex-compatible repository instruction entry; VS Code extension behavior must be tested.", ("code",)),
    "vscode-claude-code": Adapter("vscode-claude-code", "VS Code + Claude Code", "template", ("CLAUDE.md",), "Claude Code project instruction entry when the extension runs Claude Code semantics.", ("code",)),
    "vscode-copilot": Adapter("vscode-copilot", "VS Code + GitHub Copilot", "template", (".github/copilot-instructions.md",), "Repository-wide Copilot instructions; path-specific instructions are a future enhancement.", ("code",)),
    "zcode": Adapter("zcode", "ZCode", "manual", (".aimes/adapters/zcode/README.md",), "No ZCode rule path is assumed. Review the installed plugin and explicitly map its supported entry.", ("zcode",)),
    "qcode": Adapter("qcode", "QCode", "manual", (".aimes/adapters/qcode/README.md",), "Product/version and rule-loading mechanism must be identified before native files are written.", ("qcode",)),
    "claude-code": Adapter("claude-code", "Claude Code CLI", "template", ("CLAUDE.md",), "Claude Code project instruction entry.", ("claude",)),
    "codex-cli": Adapter("codex-cli", "Codex CLI", "template", ("AGENTS.md",), "Codex repository instruction entry.", ("codex",)),
}

ALIASES = {
    "trae": "trae-code", "traecode": "trae-code", "trae-code": "trae-code",
    "vscode-codex": "vscode-codex", "vscode-claude": "vscode-claude-code", "vscode-claude-code": "vscode-claude-code",
    "copilot": "vscode-copilot", "vscode-copilot": "vscode-copilot",
    "zcode": "zcode", "qcode": "qcode", "claude": "claude-code", "claude-code": "claude-code",
    "codex": "codex-cli", "codex-cli": "codex-cli",
}

def normalize_tools(raw: str | list[str] | None) -> list[str]:
    if not raw:
        return []
    values = raw.split(",") if isinstance(raw, str) else raw
    out = []
    for item in values:
        key = ALIASES.get(item.strip().lower())
        if not key:
            raise ValueError(f"Unknown tool '{item}'. Supported: {', '.join(ADAPTERS)}")
        if key not in out:
            out.append(key)
    return out

def adapter_payload():
    return [{"id": a.key, "name": a.label, "status": a.status, "entry_paths": list(a.paths), "description": a.description} for a in ADAPTERS.values()]
