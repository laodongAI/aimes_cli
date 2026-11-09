from pathlib import Path
import tempfile
import unittest
import yaml

from aimes_cli.quality_check import inspect_project_quality


class QualityCheckTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def _write_config(self, **overrides):
        config = {
            "schema_version": 1, "enabled": True, "enforce": True, "fail_on": "ERROR",
            "vue": {
                "max_sfc_lines": {"warning": 10, "error": 20},
                "max_script_lines": {"warning": 5, "error": 10},
                "max_template_lines": {"warning": 5, "error": 10},
            },
            "exclude": ["vendor/**"],
        }
        config.update(overrides)
        target = self.root / ".aimes" / "quality-gates.yaml"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(yaml.safe_dump(config), encoding="utf-8")

    def test_reports_large_vue_sfc_without_modifying_source(self):
        source = self.root / "src" / "Page.vue"
        source.parent.mkdir()
        original = "<template>\n<div/>\n</template>\n" + "<script setup>\nconst x = 1\n</script>\n" + "line\n" * 15
        source.write_text(original, encoding="utf-8")
        self._write_config()
        result = inspect_project_quality(self.root)
        self.assertFalse(result["ok"])
        self.assertTrue(any(item["code"] == "SFC_LINES" and item["severity"] == "ERROR" for item in result["findings"]))
        self.assertEqual(source.read_text(encoding="utf-8"), original)

    def test_script_and_template_thresholds_are_checked(self):
        source = self.root / "Feature.vue"
        source.write_text("<template>\n" + "x\n" * 7 + "</template>\n<script>\n" + "x\n" * 7 + "</script>\n", encoding="utf-8")
        self._write_config()
        result = inspect_project_quality(self.root)
        self.assertTrue({item["code"] for item in result["findings"]} >= {"SCRIPT_LINES", "TEMPLATE_LINES"})

    def test_excluded_paths_are_not_scanned(self):
        source = self.root / "vendor" / "Legacy.vue"
        source.parent.mkdir()
        source.write_text("x\n" * 50, encoding="utf-8")
        self._write_config()
        result = inspect_project_quality(self.root)
        self.assertEqual(result["summary"]["files_scanned"], 0)
        self.assertTrue(result["ok"])

    def test_advisory_mode_does_not_fail_gate(self):
        source = self.root / "Big.vue"
        source.write_text("x\n" * 30, encoding="utf-8")
        self._write_config(enforce=False)
        result = inspect_project_quality(self.root)
        self.assertTrue(result["ok"])
        self.assertEqual(result["status"], "PASS_WITH_FINDINGS")

    def test_invalid_config_fails_even_when_enforcement_cannot_be_trusted(self):
        target = self.root / ".aimes" / "quality-gates.yaml"
        target.parent.mkdir(parents=True)
        target.write_text("enforce: [this is not a boolean", encoding="utf-8")
        result = inspect_project_quality(self.root)
        self.assertFalse(result["ok"])
        self.assertEqual(result["status"], "CONFIG_ERROR")

    def test_invalid_threshold_fails_closed(self):
        self._write_config(vue={"max_sfc_lines": {"warning": 20, "error": 10}})
        result = inspect_project_quality(self.root)
        self.assertFalse(result["ok"])
        self.assertTrue(any(item["code"] == "QUALITY_THRESHOLD_CONFIG" for item in result["findings"]))


if __name__ == "__main__":
    unittest.main()
