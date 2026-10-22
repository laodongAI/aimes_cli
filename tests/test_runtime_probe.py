import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from aimes_cli.runtime_probe import create_runtime_probe, validate_runtime_probe
from aimes_cli.v05 import validate_adapter_evidence
from aimes_cli.cli import main


class RuntimeProbeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.probe = self.root / ".aimes" / "probes" / "codex"
        self.created = create_runtime_probe(
            self.root, self.probe, tool="codex-cli",
            product_version="codex-cli test-version", governance_version="1.2",
            observer="unit-test",
        )

    def tearDown(self):
        self.tmp.cleanup()

    def token_from_rule(self):
        text = (self.probe / "AGENTS.md").read_text(encoding="utf-8")
        marker = "reply with exactly the following token and no other text:\n\n"
        return text.split(marker, 1)[1].splitlines()[0].strip()

    def test_probe_does_not_leak_expected_token_into_prompt_or_manifest(self):
        token = self.token_from_rule()
        prompt = (self.probe / "PROMPT.txt").read_text(encoding="utf-8")
        manifest = json.loads((self.probe / "probe-manifest.json").read_text(encoding="utf-8"))
        self.assertNotIn(token, prompt)
        self.assertNotIn(token, json.dumps(manifest))
        self.assertIn("AGENTS.md", manifest["rule_entry"])

    def test_exact_response_generates_valid_runtime_evidence(self):
        (self.probe / "response.txt").write_text(self.token_from_rule() + "\n", encoding="utf-8")
        result = validate_runtime_probe(self.root, self.probe, observer="tester")
        self.assertTrue(result["ok"], result)
        evidence = self.probe / "verification-evidence.yaml"
        validated = validate_adapter_evidence(evidence, self.root)
        self.assertTrue(validated["ok"], validated["findings"])
        text = evidence.read_text(encoding="utf-8")
        self.assertIn("verification: PASS", text)
        self.assertIn("method: runtime_observation", text)

    def test_mismatched_response_is_fail_not_pass(self):
        (self.probe / "response.txt").write_text("I think the token is hidden.\n", encoding="utf-8")
        result = validate_runtime_probe(self.root, self.probe)
        self.assertFalse(result["ok"])
        self.assertEqual(result["status"], "FAIL")
        validated = validate_adapter_evidence(self.probe / "verification-evidence.yaml", self.root)
        self.assertTrue(validated["ok"], validated["findings"])

    def test_missing_response_is_not_run(self):
        result = validate_runtime_probe(self.root, self.probe)
        self.assertFalse(result["ok"])
        self.assertEqual(result["status"], "NOT_RUN")
        self.assertFalse((self.probe / "verification-evidence.yaml").exists())

    def test_changed_rule_entry_invalidates_probe(self):
        (self.probe / "AGENTS.md").write_text("# replaced\n", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "missing or changed"):
            validate_runtime_probe(self.root, self.probe)

    def test_existing_output_directory_is_never_overwritten(self):
        with self.assertRaisesRegex(ValueError, "Refusing to overwrite"):
            create_runtime_probe(
                self.root, self.probe, tool="codex-cli",
                product_version="codex-cli test-version",
            )

    def test_path_escape_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "inside the project root"):
            create_runtime_probe(
                self.root, self.root.parent / "escape-probe", tool="codex-cli",
                product_version="codex-cli test-version",
            )

    def test_claude_probe_uses_native_entry_name(self):
        target = self.root / ".aimes" / "probes" / "claude"
        create_runtime_probe(
            self.root, target, tool="claude-code",
            product_version="claude test-version",
        )
        self.assertTrue((target / "CLAUDE.md").is_file())
        self.assertFalse((target / "AGENTS.md").exists())


    def test_cli_create_and_validate_probe(self):
        target = self.root / ".aimes" / "probes" / "cli"
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            code = main([
                "adapter", "probe", "create", "--tool", "claude-code",
                "--product-version", "claude-code-test", "--output-dir", str(target),
                "--root", str(self.root), "--format", "json"
            ])
        self.assertEqual(code, 0, output.getvalue())
        token_text = (target / "CLAUDE.md").read_text(encoding="utf-8")
        token = token_text.split("reply with exactly the following token and no other text:\n\n", 1)[1].splitlines()[0]
        (target / "response.txt").write_text(token + "\n", encoding="utf-8")
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            code = main([
                "adapter", "probe", "validate", str(target),
                "--root", str(self.root), "--format", "json"
            ])
        self.assertEqual(code, 0, output.getvalue())
        self.assertTrue((target / "verification-evidence.yaml").is_file())

if __name__ == "__main__":
    unittest.main()
