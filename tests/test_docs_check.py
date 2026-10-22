from pathlib import Path
import tempfile
import unittest

from aimes_cli.docs_check import check_docs


class DocsCheckTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / "docs" / "_governance").mkdir(parents=True)
        (self.root / "docs" / "_governance" / "AIMES-CORE-V1.2.md").write_text("# Core\n", encoding="utf-8")
        (self.root / "AGENTS.md").write_text(
            "Read docs/_governance/AIMES-CORE-V1.2.md before changes.\n", encoding="utf-8"
        )
        (self.root / "README.md").write_text("# Readme\n\n[Core](docs/_governance/AIMES-CORE-V1.2.md)\n", encoding="utf-8")

    def tearDown(self):
        self.tmp.cleanup()

    def test_valid_docs_and_thin_entry_pass(self):
        result = check_docs(self.root)
        self.assertTrue(result["ok"], result["findings"])
        self.assertEqual(result["summary"]["entry_files_checked"], 1)
        self.assertEqual(result["summary"]["local_links_checked"], 1)

    def test_broken_local_link_fails(self):
        (self.root / "README.md").write_text("[Missing](docs/nope.md)\n", encoding="utf-8")
        result = check_docs(self.root)
        self.assertFalse(result["ok"])
        self.assertTrue(any(item["code"] == "BROKEN_LINK" for item in result["findings"]))

    def test_missing_core_reference_fails(self):
        (self.root / "AGENTS.md").write_text("# Full copied rules\n", encoding="utf-8")
        result = check_docs(self.root)
        self.assertFalse(result["ok"])
        self.assertTrue(any(item["code"] == "CORE_REFERENCE_MISSING" for item in result["findings"]))

    def test_oversized_entry_fails(self):
        (self.root / "AGENTS.md").write_text(
            "docs/_governance/AIMES-CORE-V1.2.md\n" + "extra\n" * 40, encoding="utf-8"
        )
        result = check_docs(self.root)
        self.assertFalse(result["ok"])
        self.assertTrue(any(item["code"] == "ENTRY_TOO_LONG" for item in result["findings"]))

    def test_configured_missing_entry_fails(self):
        (self.root / ".aimes").mkdir()
        (self.root / ".aimes" / "config.yaml").write_text(
            "governance:\n  core: docs/_governance/AIMES-CORE-V1.2.md\n"
            "tools:\n  - id: codex-cli\n    entry_paths: [AGENTS.md, MISSING.md]\n",
            encoding="utf-8",
        )
        result = check_docs(self.root)
        self.assertFalse(result["ok"])
        self.assertTrue(any(item["code"] == "ENTRY_MISSING" for item in result["findings"]))

    def test_generic_markdown_repo_does_not_require_aimes_core(self):
        (self.root / "AGENTS.md").unlink()
        (self.root / "README.md").write_text("# Plain docs repo\n", encoding="utf-8")
        (self.root / "docs" / "_governance" / "AIMES-CORE-V1.2.md").unlink()
        result = check_docs(self.root)
        self.assertTrue(result["ok"], result["findings"])

    def test_packaged_core_template_links_are_not_checked_at_template_location(self):
        template = self.root / "src" / "aimes_cli" / "templates" / "core"
        template.mkdir(parents=True)
        (template / "AIMES-CORE-V1.2.md").write_text("[Project task file](project-control/TASKS.md)\n", encoding="utf-8")
        result = check_docs(self.root)
        self.assertFalse(any(item["code"] == "BROKEN_LINK" for item in result["findings"]))

    def test_configured_task_and_handoff_paths_are_checked(self):
        (self.root / ".aimes").mkdir(exist_ok=True)
        (self.root / ".aimes" / "config.yaml").write_text(
            "governance:\n  core: docs/_governance/AIMES-CORE-V1.2.md\n"
            "records:\n  tasks: project-control/TASKS.md\n  handoff: HANDOFF.md\n"
            "tools:\n  - id: codex-cli\n    entry_paths: [AGENTS.md]\n", encoding="utf-8")
        result = check_docs(self.root)
        missing = [item for item in result["findings"] if item["code"] == "RECORD_PATH_MISSING"]
        self.assertEqual({item["path"] for item in missing}, {"project-control/TASKS.md", "HANDOFF.md"})

    def test_duplicate_env_example_assignments_are_reported(self):
        (self.root / ".env.example").write_text(
            "# first declaration\nCOSYVOICE_MODEL_DIR=/models\n# duplicate\nCOSYVOICE_MODEL_DIR=/other\n", encoding="utf-8")
        result = check_docs(self.root)
        duplicates = [item for item in result["findings"] if item["code"] == "ENV_KEY_DUPLICATE"]
        self.assertEqual(len(duplicates), 1)
        self.assertEqual(duplicates[0]["line"], 4)

    def test_record_path_escape_is_rejected(self):
        (self.root / ".aimes").mkdir(exist_ok=True)
        (self.root / ".aimes" / "config.yaml").write_text(
            "governance:\n  core: docs/_governance/AIMES-CORE-V1.2.md\n"
            "records:\n  tasks: ../outside/TASKS.md\n"
            "tools:\n  - id: codex-cli\n    entry_paths: [AGENTS.md]\n", encoding="utf-8")
        result = check_docs(self.root)
        self.assertTrue(any(item["code"] == "RECORD_PATH_ESCAPE" for item in result["findings"]))

    def test_pending_proposal_is_reported_without_modification(self):
        proposal = self.root / ".aimes" / "proposed" / "CLAUDE.md.proposed"
        proposal.parent.mkdir(parents=True)
        proposal.write_text("# Proposed entry\\n", encoding="utf-8")
        result = check_docs(self.root)
        self.assertTrue(any(item["code"] == "PROPOSAL_PENDING" and item["path"] == ".aimes/proposed/CLAUDE.md.proposed" for item in result["findings"]))
        self.assertEqual(proposal.read_text(encoding="utf-8"), "# Proposed entry\\n")

    def test_git_untracked_files_are_reported_read_only(self):
        import subprocess
        subprocess.run(["git", "init", str(self.root)], capture_output=True, check=True)
        untracked = self.root / ".trae" / "rules" / "example.md"
        untracked.parent.mkdir(parents=True)
        untracked.write_text("rule\\n", encoding="utf-8")
        result = check_docs(self.root)
        self.assertTrue(any(item["code"] == "GIT_UNTRACKED_FILE" and item["path"] == ".trae/rules/example.md" for item in result["findings"]))
        self.assertTrue(untracked.is_file())

    def test_external_links_are_ignored(self):
        (self.root / "README.md").write_text(
            "[External](https://example.com/not-local)\n[Email](mailto:test@example.com)\n",
            encoding="utf-8",
        )
        result = check_docs(self.root)
        self.assertTrue(result["ok"], result["findings"])
        self.assertEqual(result["summary"]["local_links_checked"], 0)


if __name__ == "__main__":
    unittest.main()
