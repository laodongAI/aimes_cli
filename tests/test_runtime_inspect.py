import json
import tempfile
import unittest
from pathlib import Path

from aimes_cli.runtime_inspect import inspect_adapters
from aimes_cli.cli import parser


class RuntimeInspectionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def write(self, relative, content):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return path

    def test_codex_reports_instruction_skill_mcp_hook_and_agent_configuration(self):
        self.write("AGENTS.md", "# Project rules")
        self.write(".agents/skills/review/SKILL.md", "---\nname: review\ndescription: Review code\n---\n")
        self.write(".codex/config.toml", '[mcp_servers.docs]\nurl = "https://example.invalid/mcp"\n[agents.reviewer]\ndescription = "Review changes"\n[[hooks.PreToolUse]]\nmatcher = ".*"\n')
        self.write(".codex/hooks.json", '{"PreToolUse": []}')
        result = inspect_adapters(self.root, ["codex-cli"])
        integrations = {item["id"]: item for item in result["adapters"][0]["integrations"]}
        self.assertEqual(integrations["instructions"]["status"], "present")
        self.assertEqual(integrations["skills"]["status"], "configured")
        self.assertEqual(integrations["mcp"]["status"], "configured")
        self.assertEqual(integrations["hooks"]["status"], "configured")
        self.assertEqual(integrations["agents"]["status"], "configured")
        self.assertNotIn("url", json.dumps(result))

    def test_claude_detects_project_entries_without_exposing_config_values(self):
        self.write("CLAUDE.md", "# Rules")
        self.write(".claude/settings.json", '{"hooks": {"PreToolUse": []}, "mcpServers": {"local": {"command": "secret-command"}}}')
        self.write(".mcp.json", '{"mcpServers": {"docs": {"url": "https://example.invalid"}}}')
        self.write(".claude/skills/triage/SKILL.md", "---\nname: triage\ndescription: Triage issues\n---\n")
        self.write(".claude/agents/reviewer.md", "---\nname: reviewer\ndescription: Review\n---\n")
        result = inspect_adapters(self.root, ["claude-code"])
        integrations = {item["id"]: item for item in result["adapters"][0]["integrations"]}
        self.assertEqual(integrations["instructions"]["status"], "present")
        self.assertEqual(integrations["skills"]["status"], "configured")
        self.assertEqual(integrations["mcp"]["status"], "configured")
        self.assertEqual(integrations["hooks"]["status"], "configured")
        self.assertEqual(integrations["agents"]["status"], "configured")
        rendered = json.dumps(result)
        self.assertNotIn("secret-command", rendered)
        self.assertNotIn("example.invalid", rendered)

    def test_invalid_json_is_reported_as_invalid_not_configured(self):
        self.write(".claude/settings.json", '{"hooks": ')
        result = inspect_adapters(self.root, ["claude-code"])
        hooks = next(item for item in result["adapters"][0]["integrations"] if item["id"] == "hooks")
        self.assertEqual(hooks["status"], "invalid")

    def test_symlinked_config_is_not_followed(self):
        outside = Path(self.temp.name).parent / (Path(self.temp.name).name + "-outside.json")
        outside.write_text('{"hooks": {"PreToolUse": []}}', encoding="utf-8")
        try:
            (self.root / ".claude").mkdir()
            (self.root / ".claude/settings.json").symlink_to(outside)
            result = inspect_adapters(self.root, ["claude-code"])
            hooks = next(item for item in result["adapters"][0]["integrations"] if item["id"] == "hooks")
            self.assertEqual(hooks["status"], "unknown")
            self.assertEqual(hooks["evidence"][0]["reason"], "symlink_not_followed")
        finally:
            outside.unlink(missing_ok=True)

    def test_unknown_tool_context_is_rejected(self):
        with self.assertRaises(ValueError):
            inspect_adapters(self.root, ["trae-code"])

    def test_cli_parser_supports_read_only_inspection(self):
        args = parser().parse_args(["adapter", "inspect", "--root", str(self.root), "--tool", "codex-cli", "--format", "json"])
        self.assertEqual(args.adapter_command, "inspect")
        self.assertEqual(args.tool, ["codex-cli"])
        self.assertEqual(args.format, "json")


if __name__ == "__main__":
    unittest.main()
