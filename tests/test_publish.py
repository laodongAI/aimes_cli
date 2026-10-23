import hashlib
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path
from aimes_cli.publish import build_change_plan, collect_source_files, detect_project_profile, is_excluded, normalize_repository, publish_project, validate_branch
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

    def test_project_stack_detection_selects_automatic_rules(self):
        (self.root / "package.json").write_text('{"dependencies":{"vue":"^3.0.0"}}', encoding="utf-8")
        (self.root / "pnpm-lock.yaml").write_text("lockfileVersion: '9.0'", encoding="utf-8")
        (self.root / ".gitignore").write_text("# local output\ncoverage/\nlocal-data.json\n!keep-me.json\n", encoding="utf-8")
        profile = detect_project_profile(self.root)
        self.assertIn("nodejs", profile["stacks"])
        self.assertIn("vue", profile["stacks"])
        self.assertIn("coverage/", profile["rules"])
        self.assertIn(".next", profile["rules"])

    def test_collect_files_applies_detected_stack_and_gitignore_rules(self):
        (self.root / "package.json").write_text('{"scripts":{"build":"vite build"}}', encoding="utf-8")
        (self.root / ".gitignore").write_text("local-data.json\ncoverage/\n", encoding="utf-8")
        (self.root / "README.md").write_text("hello", encoding="utf-8")
        (self.root / "local-data.json").write_text("local", encoding="utf-8")
        (self.root / ".next").mkdir()
        (self.root / ".next" / "cache.bin").write_text("cache", encoding="utf-8")
        (self.root / "coverage").mkdir()
        (self.root / "coverage" / "report.txt").write_text("coverage", encoding="utf-8")
        files, excluded, _ = collect_source_files(self.root)
        self.assertEqual(set(files), {"package.json", ".gitignore", "README.md"})
        self.assertIn("local-data.json", excluded)
        self.assertIn(".next/", excluded)
        self.assertIn("coverage/", excluded)

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

    def test_interactive_publish_remembers_last_used_profile(self):
        import os
        from unittest.mock import call
        from aimes_cli.cli import run_publish_wizard
        config_home = self.root / "user-config"
        old = os.environ.get("AIMES_CONFIG_HOME")
        os.environ["AIMES_CONFIG_HOME"] = str(config_home)
        (self.root / "README.md").write_text("hello", encoding="utf-8")
        args = parser().parse_args(["publish"])
        preview = {"ok": True, "change_counts": {"added": 1, "updated": 0, "deleted": 0}, "changes": {"added": ["README.md"], "updated": [], "deleted": [], "unchanged": []}}
        applied = {"ok": True, "message": "published"}
        try:
            with patch("aimes_cli.cli.sys.stdin") as stdin, \
                 patch("aimes_cli.cli._ask", side_effect=[str(self.root), "owner/repo", "", "chore: test", ""]), \
                 patch("builtins.input", side_effect=["publsh", "pUbLiSh"]), \
                 patch("aimes_cli.cli.publish_project", side_effect=[preview, applied]) as publish:
                stdin.isatty.return_value = True
                self.assertEqual(run_publish_wizard(args), 0)
                profiles = load_profiles()
                self.assertEqual(profiles["上次使用"]["repository"], "owner/repo")
                self.assertEqual(profiles["上次使用"]["source"], str(self.root))
                self.assertEqual(publish.call_count, 2)
        finally:
            if old is None:
                os.environ.pop("AIMES_CONFIG_HOME", None)
            else:
                os.environ["AIMES_CONFIG_HOME"] = old


    def test_publish_confirmation_is_case_insensitive_and_retries_invalid_input(self):
        from aimes_cli.cli import run_publish_wizard
        (self.root / "README.md").write_text("hello", encoding="utf-8")
        args = parser().parse_args([
            "publish", "--source", str(self.root), "--repo", "owner/repo",
            "--apply", "--confirm", "pUbLiSh",
        ])
        preview = {"ok": True, "change_counts": {"added": 1, "updated": 0, "deleted": 0},
                   "changes": {"added": ["README.md"], "updated": [], "deleted": [], "unchanged": []}}
        applied = {"ok": True, "message": "published"}
        with patch("aimes_cli.cli.sys.stdin") as stdin, \
             patch("aimes_cli.cli.publish_project", side_effect=[preview, applied]) as publish:
            stdin.isatty.return_value = False
            self.assertEqual(run_publish_wizard(args), 0)
        self.assertEqual(publish.call_count, 2)
        self.assertEqual(publish.call_args.args[4], "PUBLISH")

    def test_confirmation_helper_reprompts_until_valid_or_cancelled(self):
        from aimes_cli.cli import _confirm_word, _ask_yes_no
        with patch("builtins.input", side_effect=["publsh", "pUbLiSh"]):
            self.assertTrue(_confirm_word("Confirm:", "PUBLISH"))
        with patch("builtins.input", side_effect=["maybe", "YeS"]):
            self.assertTrue(_ask_yes_no("Proceed?", default=False))
        with patch("builtins.input", side_effect=["wrong", "N"]):
            self.assertFalse(_confirm_word("Confirm:", "YES"))

    def test_collect_files_automatically_excludes_github_oversized_blobs(self):
        (self.root / "README.md").write_text("hello", encoding="utf-8")
        (self.root / "large.bin").write_bytes(b"0123456789")
        with patch("aimes_cli.publish.MAX_GITHUB_BLOB_BYTES", 8):
            files, excluded, _ = collect_source_files(self.root)
        self.assertEqual(set(files), {"README.md"})
        self.assertTrue(any(item.startswith("large.bin") and "GitHub 2 GiB" in item for item in excluded))

    def test_collect_files_flags_token_like_content(self):
        (self.root / "config.txt").write_text("token=ghp_" + "A" * 30, encoding="utf-8")
        files, _, findings = collect_source_files(self.root)
        self.assertIn("config.txt", files)
        self.assertEqual(findings[0]["path"], "config.txt")

    def test_publish_preview_supports_empty_remote_repository(self):
        (self.root / "README.md").write_text("hello", encoding="utf-8")

        def fake_git_run(args, cwd=None, timeout=180):
            if args[:2] == ["ls-remote", "--heads"]:
                return ""
            if args[:2] == ["ls-remote", "--symref"]:
                return ""
            if args[0] == "clone":
                clone = Path(args[-1])
                clone.mkdir()
                (clone / ".git").mkdir()
                return ""
            if args[0] == "symbolic-ref":
                return ""
            raise AssertionError(f"Unexpected git command: {args}")

        with patch("aimes_cli.publish.git_run", side_effect=fake_git_run):
            report = publish_project(self.root, "owner/repo")

        self.assertTrue(report["ok"])
        self.assertTrue(report["remote_empty"])
        self.assertEqual(report["branch"], "main")
        self.assertIsNone(report["base_commit"])
        self.assertEqual(report["change_counts"]["added"], 1)

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


    def test_aimes_governance_files_bypass_generic_tool_and_gitignore_filters(self):
        self.assertFalse(is_excluded('.trae', is_dir=True, extra_patterns=['.trae/']))
        self.assertFalse(is_excluded('.trae/rules/00-aimes-governance.md', extra_patterns=['.trae/']))
        self.assertFalse(is_excluded('.aimes/skills/registry.yaml', extra_patterns=['.aimes/**']))
        self.assertFalse(is_excluded('docs', is_dir=True, extra_patterns=['docs/**']))
        self.assertFalse(is_excluded('docs/_governance/AIMES-CORE-V1.2.md', extra_patterns=['docs/**']))
        self.assertTrue(is_excluded('.trae/settings.json'))
        self.assertTrue(is_excluded('.aimes/credentials.json'))

    def test_collect_files_keeps_aimes_trae_rule_but_filters_other_trae_state(self):
        (self.root / '.gitignore').write_text('.trae/' + chr(10), encoding='utf-8')
        rule = self.root / '.trae' / 'rules' / '00-aimes-governance.md'
        rule.parent.mkdir(parents=True)
        rule.write_text('# AIMES rule', encoding='utf-8')
        state = self.root / '.trae' / 'settings.json'
        state.write_text('{ }', encoding='utf-8')
        files, excluded, _ = collect_source_files(self.root)
        self.assertIn('.trae/rules/00-aimes-governance.md', files)
        self.assertNotIn('.trae/settings.json', files)
        self.assertIn('.trae/settings.json', excluded)


if __name__ == "__main__":
    unittest.main()
