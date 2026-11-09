from pathlib import Path
import io
import tempfile
import unittest
from contextlib import redirect_stdout
import yaml

from aimes_cli.quality_check import inspect_project_quality
from aimes_cli.cli import main


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

    def test_direct_http_calls_in_vue_scripts_are_reported_with_line_evidence(self):
        source = self.root / "src" / "pages" / "Users.vue"
        source.parent.mkdir(parents=True)
        source.write_text(
            "<script setup>\n"
            "// fetch('/api/commented')\n"
            "const load = () => fetch('/api/users')\n"
            "axios.get('/api/users')\n"
            "</script>\n<template><div/></template>\n",
            encoding="utf-8",
        )
        self._write_config()
        result = inspect_project_quality(self.root)
        findings = [item for item in result["findings"] if item["code"] == "VUE_DIRECT_HTTP_CALL"]
        self.assertEqual(len(findings), 2)
        self.assertEqual([item["line"] for item in findings], [3, 4])
        self.assertTrue(all(item["severity"] == "WARNING" for item in findings))
        # Default fail_on=ERROR keeps advisory architecture warnings non-blocking.
        self.assertTrue(result["ok"])

    def test_warning_can_block_when_project_explicitly_sets_fail_on_warning(self):
        source = self.root / "Page.vue"
        source.write_text("<script setup>\nfetch('/api/users')\n</script>\n", encoding="utf-8")
        self._write_config(fail_on="WARNING")
        result = inspect_project_quality(self.root)
        self.assertFalse(result["ok"])
        self.assertEqual(result["status"], "FAIL")

    def test_direct_http_call_rule_can_be_disabled_per_project(self):
        source = self.root / "Page.vue"
        source.write_text("<script setup>\nfetch('/api/users')\n</script>\n", encoding="utf-8")
        self._write_config(vue={
            "max_sfc_lines": {"warning": 10, "error": 20},
            "max_script_lines": {"warning": 5, "error": 10},
            "max_template_lines": {"warning": 5, "error": 10},
            "disallow_direct_http_calls": False,
        })
        result = inspect_project_quality(self.root)
        self.assertFalse(any(item["code"] == "VUE_DIRECT_HTTP_CALL" for item in result["findings"]))

    def test_invalid_direct_http_rule_type_fails_closed(self):
        self._write_config(vue={
            "max_sfc_lines": {"warning": 10, "error": 20},
            "max_script_lines": {"warning": 5, "error": 10},
            "max_template_lines": {"warning": 5, "error": 10},
            "disallow_direct_http_calls": "yes",
        })
        result = inspect_project_quality(self.root)
        self.assertFalse(result["ok"])
        self.assertTrue(any(item["code"] == "QUALITY_VUE_CONFIG" for item in result["findings"]))

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

    def test_frontend_profile_applies_stricter_threshold_than_baseline(self):
        source = self.root / "Page.vue"
        source.write_text("line\n" * 375, encoding="utf-8")
        baseline = inspect_project_quality(self.root, profile_id="baseline")
        frontend = inspect_project_quality(self.root, profile_id="frontend")
        self.assertFalse(any(item["code"] == "SFC_LINES" for item in baseline["findings"]))
        self.assertTrue(any(item["code"] == "SFC_LINES" and item["severity"] == "WARNING"
                            for item in frontend["findings"]))
        self.assertEqual(frontend["policy"]["profile"]["id"], "frontend")
        self.assertTrue(frontend["ok"])  # advisory policy remains controlled globally

    def test_empty_project_vue_overrides_preserve_profile_defaults(self):
        source = self.root / "Page.vue"
        source.write_text("line\n" * 375, encoding="utf-8")
        config = self.root / ".aimes" / "quality-gates.yaml"
        config.parent.mkdir(parents=True)
        config.write_text("schema_version: 1\nenabled: true\nenforce: false\nfail_on: ERROR\nvue: {}\n",
                          encoding="utf-8")
        result = inspect_project_quality(self.root, profile_id="frontend")
        self.assertTrue(any(item["code"] == "SFC_LINES" for item in result["findings"]))

    def test_project_thresholds_override_profile_defaults(self):
        source = self.root / "Page.vue"
        source.write_text("line\n" * 375, encoding="utf-8")
        self._write_config(enforce=False, vue={
            "max_sfc_lines": {"warning": 500, "error": 700},
            "max_script_lines": {"warning": 300, "error": 450},
            "max_template_lines": {"warning": 300, "error": 450},
            "disallow_direct_http_calls": True,
        })
        result = inspect_project_quality(self.root, profile_id="frontend")
        self.assertFalse(any(item["code"] == "SFC_LINES" for item in result["findings"]))

    def test_mode_selects_its_mapped_quality_profile(self):
        modes = self.root / ".aimes" / "project-state" / "engineering-modes.yaml"
        modes.parent.mkdir(parents=True)
        modes.write_text(
            "schema_version: 1\nmodes:\n  - id: frontend-development\n"
            "    label: Frontend\n    triggers: []\n    skills: []\n"
            "    workflow: feature-development\n    quality_profile: frontend\n",
            encoding="utf-8",
        )
        source = self.root / "Page.vue"
        source.write_text("line\n" * 375, encoding="utf-8")
        result = inspect_project_quality(self.root, mode_id="frontend-development")
        self.assertEqual(result["policy"]["profile"]["id"], "frontend")
        self.assertTrue(any(item["code"] == "SFC_LINES" for item in result["findings"]))

    def test_bundled_mode_registry_profiles_are_all_declared(self):
        project_root = Path(__file__).resolve().parents[1]
        modes_path = project_root / "src" / "aimes_cli" / "templates" / "project-state" / "engineering-modes.yaml"
        profiles_path = project_root / "src" / "aimes_cli" / "templates" / "skills" / "quality-profiles.yaml"
        modes = yaml.safe_load(modes_path.read_text(encoding="utf-8"))
        profiles = yaml.safe_load(profiles_path.read_text(encoding="utf-8"))
        declared = set(profiles["profiles"])
        mapped = {item.get("quality_profile") for item in modes["modes"]}
        self.assertTrue(mapped)
        self.assertEqual(mapped - declared, set())

    def test_unknown_profile_fails_closed(self):
        result = inspect_project_quality(self.root, profile_id="does-not-exist")
        self.assertFalse(result["ok"])
        self.assertEqual(result["status"], "CONFIG_ERROR")
        self.assertTrue(any(item["code"] == "QUALITY_PROFILE_CONFIG" for item in result["findings"]))

    def test_cli_quality_inspect_accepts_profile_selection(self):
        source = self.root / "Page.vue"
        source.write_text("line\n" * 375, encoding="utf-8")
        output = io.StringIO()
        with redirect_stdout(output):
            code = main(["quality", "inspect", "--root", str(self.root),
                         "--profile", "frontend", "--format", "json"])
        self.assertEqual(code, 0)
        self.assertIn('"id": "frontend"', output.getvalue())


if __name__ == "__main__":
    unittest.main()
