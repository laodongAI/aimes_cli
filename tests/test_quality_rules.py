from pathlib import Path
import tempfile
import unittest
import subprocess

from aimes_cli.quality_rules import inspect_general_file, inspect_project_sources, inspect_python_file, inspect_public_api_compatibility, inspect_vue_file


class QualityRuleTests(unittest.TestCase):
    def test_python_mutable_default_is_error(self):
        findings = inspect_python_file("service.py", "def load(items=[]):\n    return items\n", {})
        self.assertTrue(any(item["code"] == "PYTHON_MUTABLE_DEFAULT" and item["severity"] == "ERROR" for item in findings))

    def test_python_broad_exception_is_reported(self):
        source = "def run():\n    try:\n        work()\n    except Exception:\n        return None\n"
        findings = inspect_python_file("service.py", source, {})
        self.assertTrue(any(item["code"] == "PYTHON_BROAD_EXCEPTION" for item in findings))

    def test_python_complexity_threshold_is_configurable(self):
        source = "def choose(a, b, c):\n    if a:\n        pass\n    if b:\n        pass\n    if c:\n        pass\n"
        findings = inspect_python_file("service.py", source, {"python": {"max_cyclomatic_complexity": 2}})
        self.assertTrue(any(item["code"] == "PYTHON_COMPLEXITY" for item in findings))

    def test_fastapi_route_direct_persistence_is_reported(self):
        source = "from fastapi import APIRouter\nrouter = APIRouter()\n@router.get('/')\ndef list_items(db):\n    return db.execute('select 1')\n"
        findings = inspect_python_file("app/api/routes/items.py", source, {})
        self.assertTrue(any(item["code"] == "FASTAPI_ROUTE_DATA_ACCESS" for item in findings))

    def test_api_layer_direct_repository_import_is_reported(self):
        source = "from app.repositories.users import UserRepository\n"
        findings = inspect_python_file("app/api/routes/users.py", source, {})
        self.assertTrue(any(item["code"] == "FASTAPI_LAYER_IMPORT" for item in findings))

    def test_vue_prop_mutation_is_error(self):
        source = "<script setup>\nprops.user.name = 'changed'\n</script>\n"
        findings = inspect_vue_file("UserCard.vue", source, {})
        self.assertTrue(any(item["code"] == "VUE_PROP_MUTATION" and item["severity"] == "ERROR" for item in findings))

    def test_vue_style_literal_color_is_reported(self):
        source = "<style scoped>\n.card { color: #fff; }\n</style>\n"
        findings = inspect_vue_file("Card.vue", source, {})
        self.assertTrue(any(item["code"] == "VUE_HARDCODED_COLOR" for item in findings))

    def test_vue_stateful_logic_density_is_advisory(self):
        calls = "\n".join(f"const value{i} = ref({i})" for i in range(13))
        findings = inspect_vue_file("Large.vue", f"<script setup>\n{calls}\n</script>", {})
        self.assertTrue(any(item["code"] == "VUE_STATEFUL_LOGIC_DENSITY" for item in findings))
        self.assertTrue(all(item["severity"] == "WARNING" for item in findings))

    def test_general_source_size_rule_is_configurable(self):
        findings = inspect_general_file("module.py", "line\n" * 12, {"general": {"max_source_file_lines": 10}})
        self.assertTrue(any(item["code"] == "SOURCE_FILE_LINES" for item in findings))

    def test_dependency_wildcards_are_reported_without_claiming_cve_analysis(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "package.json").write_text(
                '{"dependencies":{"unsafe":"*","floating":"latest","stable":"^2.1.0"}}',
                encoding="utf-8",
            )
            findings, _ = inspect_project_sources(root, {})
        self.assertEqual(sum(item["code"] == "DEPENDENCY_WILDCARD" for item in findings), 2)

    def test_measured_coverage_below_threshold_is_reported(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "coverage.xml").write_text(
                '<coverage line-rate="0.72"></coverage>', encoding="utf-8"
            )
            findings, counts = inspect_project_sources(
                root, {"general": {"min_coverage_percent": 80}}
            )
        self.assertTrue(any(item["code"] == "COVERAGE_BELOW_THRESHOLD" for item in findings))
        self.assertEqual(counts["coverage"]["percent"], 72.0)

    def test_missing_coverage_report_is_not_fabricated(self):
        with tempfile.TemporaryDirectory() as directory:
            findings, counts = inspect_project_sources(
                Path(directory), {"general": {"min_coverage_percent": None}}
            )
        self.assertFalse(any(item["code"].startswith("COVERAGE_") for item in findings))
        self.assertEqual(counts["coverage"]["status"], "NOT_PROVIDED")

    def test_public_api_removal_is_detected_against_git_base_ref(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            subprocess.run(["git", "init", "-q", str(root)], check=True)
            subprocess.run(["git", "-C", str(root), "config", "user.email", "test@example.com"], check=True)
            subprocess.run(["git", "-C", str(root), "config", "user.name", "AIMES Test"], check=True)
            module = root / "api.py"
            module.write_text("def public_api(value, option=None):\\n    return value\\n", encoding="utf-8")
            subprocess.run(["git", "-C", str(root), "add", "api.py"], check=True)
            subprocess.run(["git", "-C", str(root), "commit", "-qm", "baseline"], check=True)
            module.write_text("def replacement(value):\\n    return value\\n", encoding="utf-8")
            findings, metadata = inspect_public_api_compatibility(root, "HEAD")
        self.assertEqual(metadata["status"], "COMPARED")
        self.assertTrue(any(item["code"] == "PUBLIC_API_REMOVED" for item in findings))

    def test_public_api_signature_change_is_detected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            subprocess.run(["git", "init", "-q", str(root)], check=True)
            subprocess.run(["git", "-C", str(root), "config", "user.email", "test@example.com"], check=True)
            subprocess.run(["git", "-C", str(root), "config", "user.name", "AIMES Test"], check=True)
            module = root / "api.py"
            module.write_text("def public_api(value, option=None):\\n    return value\\n", encoding="utf-8")
            subprocess.run(["git", "-C", str(root), "add", "api.py"], check=True)
            subprocess.run(["git", "-C", str(root), "commit", "-qm", "baseline"], check=True)
            module.write_text("def public_api(value, required):\\n    return value\\n", encoding="utf-8")
            findings, _ = inspect_public_api_compatibility(root, "HEAD")
        self.assertTrue(any(item["code"] == "PUBLIC_API_SIGNATURE_CHANGED" for item in findings))

    def test_identical_python_functions_are_reported_across_files(self):
        body = "def transform(value):\n    first = value + 1\n    second = first * 2\n    third = second - 3\n    fourth = third + 4\n    fifth = fourth * 5\n    return fifth\n"
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "one.py").write_text(body, encoding="utf-8")
            (root / "two.py").write_text(body, encoding="utf-8")
            findings, counts = inspect_project_sources(root, {})
        self.assertEqual(counts["python_files_scanned"], 2)
        self.assertEqual(sum(item["code"] == "PYTHON_DUPLICATE_FUNCTION" for item in findings), 2)


if __name__ == "__main__":
    unittest.main()
