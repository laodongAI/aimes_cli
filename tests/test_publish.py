import hashlib
import tempfile
import unittest
from pathlib import Path
from aimes_cli.publish import build_change_plan, collect_source_files, is_excluded, normalize_repository, validate_branch
from aimes_cli.publish_profiles import config_path, load_profiles, save_profile
from aimes_cli.cli import parser


class PublishTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_publish_parser_defaults_to_preview_and_supports_profiles(self):
        args = parser().parse_args(['publish', '--source', str(self.root), '--repo', 'owner/repo', '--exclude', 'generated/**', '--save-profile', 'demo'])
        self.assertFalse(args.apply)
        self.assertIsNone(args.branch)
        self.assertEqual(args.exclude, ['generated/**'])
        self.assertEqual(args.save_profile, 'demo')
        self.assertIsNone(parser().parse_args(['publish']).source)

    def test_normalize_repository_name_and_url(self):
        url, name = normalize_repository("laodongAI/demo")
        self.assertEqual(url, "https://github.com/laodongAI/demo.git")
        self.assertEqual(name, "laodongAI/demo")
        self.assertEqual(normalize_repository("https://github.com/owner/repo.git")[1], "owner/repo")
        self.assertEqual(normalize_repository("git@github.com:owner/repo.git")[1], "owner/repo")

    def test_reject_non_github_repository_url(self):
        with self.assertRaises(ValueError): normalize_repository("https://example.com/owner/repo.git")
        with self.assertRaises(ValueError): normalize_repository("owner/repo/extra")

    def test_branch_validation(self):
        self.assertEqual(validate_branch("feature/publish"), "feature/publish")
        for value in ("", "-main", "a..b", "main.lock", "a b", "a//b"):
            with self.subTest(value=value), self.assertRaises(ValueError): validate_branch(value)

    def test_sensitive_paths_are_excluded(self):
        for path in (".env", ".env.local", "private.pem", "id_rsa", "node_modules/pkg.js", ".git/config", "src/__pycache__/x.pyc", ".venv/Lib/site-packages/x.py", ".claude/settings.local.json", ".codex/session.json", ".cursor/cache/state.json", "logs/app.log", "tmp/run.pid", "src/module.pyd"):
            self.assertTrue(is_excluded(path), path)
        self.assertFalse(is_excluded("src/main.py"))
        self.assertFalse(is_excluded("CLAUDE.md"))
        self.assertFalse(is_excluded("pyproject.toml"))
        self.assertTrue(is_excluded("src/generated/client.py", extra_patterns=["src/generated/**"]))
        self.assertTrue(is_excluded("local-fixture.json", extra_patterns=["local-fixture.json"]))

    def test_collect_files_excludes_sensitive_paths(self):
        (self.root / "README.md").write_text("hello", encoding="utf-8")
        (self.root / ".env").write_text("TOKEN=example", encoding="utf-8")
        (self.root / "private.pem").write_text("private", encoding="utf-8")
        (self.root / "src").mkdir()
        (self.root / "src" / "main.py").write_text("print('hello')", encoding="utf-8")
        files, excluded, findings = collect_source_files(self.root)
        self.assertEqual(set(files), {"README.md", "src/main.py"})
        self.assertIn(".env", excluded)
        self.assertIn("private.pem", excluded)
        self.assertEqual(findings, [])

    def test_collect_files_applies_custom_excludes(self):
        (self.root / "README.md").write_text("hello", encoding="utf-8")
        (self.root / "local-data.json").write_text("{}", encoding="utf-8")
        (self.root / "src").mkdir()
        (self.root / "src" / "generated.py").write_text("# generated", encoding="utf-8")
        files, excluded, _ = collect_source_files(self.root, ["local-data.json", "src/generated.py"])
        self.assertEqual(set(files), {"README.md"})
        self.assertIn("local-data.json", excluded)
        self.assertIn("src/generated.py", excluded)

    def test_publish_profiles_round_trip(self):
        import os
        config_home = self.root / "user-config"
        old = os.environ.get("AIMES_CONFIG_HOME")
        os.environ["AIMES_CONFIG_HOME"] = str(config_home)
        try:
            save_profile("demo", {"source": str(self.root), "repository": "owner/repo", "branch": "main", "excludes": ["local.json"]})
            profiles = load_profiles()
            self.assertEqual(profiles["demo"]["repository"], "owner/repo")
            self.assertEqual(profiles["demo"]["excludes"], ["local.json"])
            self.assertTrue(config_path().is_file())
        finally:
            if old is None: os.environ.pop("AIMES_CONFIG_HOME", None)
            else: os.environ["AIMES_CONFIG_HOME"] = old

    def test_collect_files_flags_token_like_content(self):
        (self.root / "config.txt").write_text("token=ghp_" + "A" * 30, encoding="utf-8")
        files, _, findings = collect_source_files(self.root)
        self.assertIn("config.txt", files)
        self.assertEqual(findings[0]["path"], "config.txt")

    def test_change_plan_reports_add_update_delete_and_unchanged(self):
        files = {}
        for name, content in {"new.txt": "new", "changed.txt": "new content", "same.txt": "same"}.items():
            path = self.root / name
            path.write_text(content, encoding="utf-8")
            files[name] = path
        digest = lambda value: hashlib.sha256(value.encode("utf-8")).hexdigest()
        plan = build_change_plan(files, {"changed.txt": digest("old content"), "same.txt": digest("same"), "deleted.txt": digest("remote")})
        self.assertEqual(plan["added"], ["new.txt"])
        self.assertEqual(plan["updated"], ["changed.txt"])
        self.assertEqual(plan["deleted"], ["deleted.txt"])
        self.assertEqual(plan["unchanged"], ["same.txt"])


if __name__ == "__main__":
    unittest.main()
