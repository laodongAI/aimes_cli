import json
import tempfile
import unittest
from pathlib import Path

import yaml

from aimes_cli.runtime_probe import create_runtime_probe, validate_runtime_probe


class RuntimeProbeContextTests(unittest.TestCase):
    def test_malformed_manifest_tool_type_returns_validation_error(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve()
            probe_dir = root / "probe"
            create_runtime_probe(
                root, probe_dir, tool="codex-cli", product_version="codex-test-version",
                governance_version="1.2", observer="unit-test",
            )
            manifest_path = probe_dir / "probe-manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["tool"] = ["codex-cli"]
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "Unsupported tool ID"):
                validate_runtime_probe(root, probe_dir)

    def test_symlinked_response_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve()
            probe_dir = root / "probe"
            create_runtime_probe(
                root, probe_dir, tool="codex-cli", product_version="codex-test-version",
                governance_version="1.2", observer="unit-test",
            )
            outside = root / "outside-response.txt"
            outside.write_text("AIMES_PROBE_" + "A" * 32, encoding="utf-8")
            try:
                (probe_dir / "response.txt").symlink_to(outside)
            except OSError as exc:
                self.skipTest(f"Symbolic links are unavailable on this platform: {exc}")
            with self.assertRaisesRegex(ValueError, "symbolic link"):
                validate_runtime_probe(root, probe_dir)

    def test_malformed_optional_context_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve()
            probe_dir = root / "probe"
            create_runtime_probe(
                root, probe_dir, tool="codex-cli", product_version="codex-test-version",
                governance_version="1.2", observer="unit-test",
            )
            manifest_path = probe_dir / "probe-manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["host_id"] = ["terminal"]
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "host_id"):
                validate_runtime_probe(root, probe_dir)

    def test_probe_manifest_and_generated_evidence_capture_host_harness(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve()
            probe_dir = root / "probe"
            created = create_runtime_probe(
                root, probe_dir, tool="codex-cli", product_version="codex-test-version",
                governance_version="1.2", observer="unit-test",
            )
            manifest = json.loads((probe_dir / "probe-manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["host_id"], "terminal")
            self.assertEqual(manifest["harness_id"], "codex")
            self.assertEqual(manifest["adapter_registry_version"], "2.0.0")

            rule_text = (probe_dir / "AGENTS.md").read_text(encoding="utf-8")
            marker = "reply with exactly the following token and no other text:\n\n"
            token = rule_text.split(marker, 1)[1].splitlines()[0].strip()
            (probe_dir / "response.txt").write_text(token, encoding="utf-8")

            result = validate_runtime_probe(root, probe_dir, observer="unit-test")
            self.assertTrue(result["ok"], result)
            evidence = yaml.safe_load((probe_dir / "verification-evidence.yaml").read_text(encoding="utf-8"))
            check = evidence["checks"][0]
            self.assertEqual(check["host_id"], "terminal")
            self.assertEqual(check["harness_id"], "codex")
            self.assertEqual(check["adapter_registry_version"], "2.0.0")


if __name__ == "__main__":
    unittest.main()
