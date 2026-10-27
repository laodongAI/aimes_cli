import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from aimes_cli.cli import main
from aimes_cli.hooks import HOOK_MARKER, apply_hook_install, plan_hook_install


class HookInstallTests(unittest.TestCase):
    def test_preview_does_not_write(self):
        with tempfile.TemporaryDirectory() as directory:
            plan = plan_hook_install(Path(directory))
            self.assertEqual(plan["actions"], [{"path": plan["target"], "action": "create"}])
            self.assertFalse((Path(directory) / "hooks").exists())
            self.assertIn("aimes validate", plan["content_preview"])
            self.assertIn(HOOK_MARKER, plan["content_preview"])

    def test_apply_requires_confirm(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(ValueError):
                apply_hook_install(Path(directory), confirm="PUBLISH")
            self.assertFalse((Path(directory) / "hooks" / "pre-commit").exists())

    def test_apply_creates_executable_managed_hook(self):
        with tempfile.TemporaryDirectory() as directory:
            result = apply_hook_install(Path(directory), confirm="hook")
            self.assertTrue(result["ok"])
            hook = Path(directory) / "hooks" / "pre-commit"
            self.assertTrue(hook.is_file())
            self.assertIn(HOOK_MARKER, hook.read_text(encoding="utf-8"))

    def test_user_owned_hook_is_preserved_as_proposal(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "hooks").mkdir()
            (root / "hooks" / "pre-commit").write_text("#!/bin/sh\necho user hook\n", encoding="utf-8")
            result = apply_hook_install(root, confirm="HOOK")
            self.assertEqual((root / "hooks" / "pre-commit").read_text(encoding="utf-8"), "#!/bin/sh\necho user hook\n")
            proposal = root / ".aimes/proposed/hooks/pre-commit"
            self.assertTrue(proposal.is_file())
            self.assertIn(HOOK_MARKER, proposal.read_text(encoding="utf-8"))

    def test_managed_hook_is_updated_in_place(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            apply_hook_install(root, confirm="HOOK")
            hook = root / "hooks" / "pre-commit"
            original = hook.read_text(encoding="utf-8")
            plan = plan_hook_install(root)
            self.assertEqual(plan["actions"][0]["action"], "unchanged")
            hook.write_text(original.replace("exit 0", "exit 0 # stale"), encoding="utf-8")
            result = apply_hook_install(root, confirm="HOOK")
            self.assertEqual(result["actions"][0]["action"], "update-managed")
            self.assertEqual(hook.read_text(encoding="utf-8"), original)

    def test_cli_hook_install_flow(self):
        with tempfile.TemporaryDirectory() as directory:
            buffer = io.StringIO()
            with redirect_stdout(buffer):
                code = main(["hook", "install", "--root", directory, "--format", "json"])
            self.assertEqual(code, 0)
            preview = json.loads(buffer.getvalue())
            self.assertTrue(preview["dry_run"])
            self.assertFalse((Path(directory) / "hooks" / "pre-commit").exists())
            buffer.seek(0); buffer.truncate(0)
            with redirect_stdout(buffer):
                code = main(["hook", "install", "--root", directory, "--apply", "--format", "json"])
            self.assertEqual(code, 2)  # missing confirm raises a usage error
            with redirect_stdout(buffer):
                code = main(["hook", "install", "--root", directory, "--apply", "--confirm", "HOOK", "--format", "json"])
            self.assertEqual(code, 0)
            self.assertTrue((Path(directory) / "hooks" / "pre-commit").is_file())


if __name__ == "__main__":
    unittest.main()
