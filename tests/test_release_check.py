from pathlib import Path
import tempfile
import unittest

from aimes_cli.release_check import validate_release


class ReleaseCheckTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / "src" / "aimes_cli" / "templates" / "core").mkdir(parents=True)
        (self.root / "src" / "aimes_cli" / "templates" / "core" / "AIMES-CORE-V1.2.md").write_text("# Core\n", encoding="utf-8")
        (self.root / "src" / "aimes_cli" / "__init__.py").write_text(
            '__version__ = "0.7.9"\nSCHEMA_VERSION = 1\nGOVERNANCE_VERSION = "1.2"\n', encoding="utf-8"
        )
        (self.root / "pyproject.toml").write_text(
            '[project]\nname = "aimes-governance-cli"\nversion = "0.7.9"\n'
            '[tool.setuptools.package-data]\naimes_cli = ["templates/**/*.md", "schemas/*.json"]\n',
            encoding="utf-8",
        )
        (self.root / "README.md").write_text("# AIMES local CLI（V0.7.9）\n", encoding="utf-8")
        (self.root / "build_windows_exe.ps1").write_text("pyinstaller --collect-data aimes_cli\n", encoding="utf-8")

    def tearDown(self):
        self.tmp.cleanup()

    def test_compatible_versions_and_package_resources_pass(self):
        result = validate_release(self.root)
        self.assertTrue(result["ok"], result["findings"])
        self.assertEqual(result["summary"]["failed"], 0)

    def test_readme_version_mismatch_fails(self):
        (self.root / "README.md").write_text("# AIMES local CLI (V0.7.8)\n", encoding="utf-8")
        result = validate_release(self.root)
        self.assertFalse(result["ok"])
        self.assertTrue(any(item["code"] == "RELEASE_COMPATIBILITY" and "README version" in item["message"] for item in result["findings"]))

    def test_missing_package_data_flag_fails(self):
        (self.root / "build_windows_exe.ps1").write_text("pyinstaller --onefile\n", encoding="utf-8")
        result = validate_release(self.root)
        self.assertFalse(result["ok"])
        self.assertTrue(any("package data" in item["message"] for item in result["findings"]))


if __name__ == "__main__":
    unittest.main()
