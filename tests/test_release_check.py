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
        (self.root / "CHANGELOG.md").write_text("## 0.7.9 - Test release\\n\\n- Test.\\n", encoding="utf-8")
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

    def test_dynamic_package_version_uses_runtime_version(self):
        (self.root / "pyproject.toml").write_text(
            '[project]\nname = "aimes-governance-cli"\ndynamic = ["version"]\n'
            '[tool.setuptools.dynamic]\nversion = { attr = "aimes_cli.__version__" }\n'
            '[tool.setuptools.package-data]\naimes_cli = ["templates/**/*.md", "schemas/*.json"]\n',
            encoding="utf-8",
        )
        result = validate_release(self.root)
        self.assertTrue(result["ok"], result["findings"])
        self.assertEqual(result["versions"]["package"], "0.7.9")
        self.assertTrue(any(item["name"] == "version_source_is_canonical" and item["status"] == "PASS" for item in result["checks"]))

    def test_dynamic_package_version_rejects_noncanonical_source(self):
        (self.root / "pyproject.toml").write_text(
            '[project]\nname = "aimes-governance-cli"\ndynamic = ["version"]\n'
            '[tool.setuptools.dynamic]\nversion = { attr = "other_package.__version__" }\n'
            '[tool.setuptools.package-data]\naimes_cli = ["templates/**/*.md", "schemas/*.json"]\n',
            encoding="utf-8",
        )
        result = validate_release(self.root)
        self.assertFalse(result["ok"])
        self.assertTrue(any(item["name"] == "version_source_is_canonical" and item["status"] == "FAIL" for item in result["checks"]))

    def test_changelog_version_mismatch_fails(self):
        (self.root / "CHANGELOG.md").write_text("## 0.7.8 - Old release\n", encoding="utf-8")
        result = validate_release(self.root)
        self.assertFalse(result["ok"])
        self.assertTrue(any(item["name"] == "changelog_package_version_match" and item["status"] == "FAIL" for item in result["checks"]))

    def test_stale_wheel_filename_in_install_section_fails(self):
        (self.root / "README.md").write_text(
            "# AIMES local CLI (V0.7.9)\n\n## 3. 安装（Windows PowerShell）\n"
            "python -m pip install .\\dist\\aimes_governance_cli-0.5.3-py3-none-any.whl\n\n"
            "## 4. 第一次初始化\n",
            encoding="utf-8",
        )
        result = validate_release(self.root)
        self.assertFalse(result["ok"])
        self.assertTrue(any(item["name"] == "readme_installation_not_pinned_to_historical_wheel" and item["status"] == "FAIL" for item in result["checks"]))


if __name__ == "__main__":
    unittest.main()
