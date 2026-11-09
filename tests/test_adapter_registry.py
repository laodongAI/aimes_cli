import unittest

from aimes_cli.adapters import ADAPTERS, adapter_payload, normalize_tools
from aimes_cli.cli import parser, emit
import io
from contextlib import redirect_stdout


class AdapterRegistryTests(unittest.TestCase):
    def test_registry_is_declarative_and_exposes_host_harness_split(self):
        codex_ide = ADAPTERS["vscode-codex"]
        codex_cli = ADAPTERS["codex-cli"]
        self.assertEqual(codex_ide.harness_id, codex_cli.harness_id)
        self.assertNotEqual(codex_ide.host_type, codex_cli.host_type)
        self.assertEqual(codex_ide.execution_modes, ("ide_extension",))
        self.assertEqual(codex_cli.execution_modes, ("cli",))

    def test_capability_unknown_is_not_promoted_to_supported(self):
        payload = {item["id"]: item for item in adapter_payload()}
        self.assertEqual(payload["vscode-copilot"]["capabilities"]["hooks"], "unknown")
        self.assertEqual(payload["zcode"]["capabilities"]["instructions"], "manual")

    def test_legacy_adapter_attributes_and_aliases_remain_compatible(self):
        self.assertEqual(ADAPTERS["codex-cli"].status, "template")
        self.assertEqual(ADAPTERS["codex-cli"].paths, ("AGENTS.md",))
        self.assertEqual(normalize_tools("codex,codex-cli,claude"), ["codex-cli", "claude-code"])

    def test_cli_exposes_registry_listing_in_json_mode(self):
        args = parser().parse_args(["adapter", "list", "--format", "json"])
        self.assertEqual(args.command, "adapter")
        self.assertEqual(args.adapter_command, "list")
        self.assertEqual(args.format, "json")

    def test_text_output_includes_adapter_details(self):
        output = io.StringIO()
        with redirect_stdout(output):
            emit({"ok": True, "adapters": adapter_payload()})
        self.assertIn("Codex CLI", output.getvalue())
        self.assertIn("Terminal / OpenAI Codex", output.getvalue())

    def test_registry_has_unique_ids_and_known_capability_states(self):
        ids = [item["id"] for item in adapter_payload()]
        self.assertEqual(len(ids), len(set(ids)))
        allowed = {"native", "template", "manual", "unknown", "unsupported"}
        for item in adapter_payload():
            self.assertTrue(item["host"]["id"])
            self.assertTrue(item["harness"]["id"])
            self.assertTrue(item["execution_modes"])
            self.assertTrue(set(item["capabilities"].values()).issubset(allowed))


if __name__ == "__main__":
    unittest.main()
