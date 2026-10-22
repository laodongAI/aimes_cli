import contextlib
import io
from pathlib import Path
import tempfile
import unittest

from aimes_cli.cli import main


class TaskValidateCliTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_no_active_writer_is_advisory_by_default(self):
        with contextlib.redirect_stdout(io.StringIO()):
            code = main(["task", "validate", "--root", str(self.root), "--format", "json"])
        self.assertEqual(code, 0)

    def test_claim_and_release_cli_round_trip(self):
        import subprocess
        from datetime import datetime, timezone
        subprocess.run(["git", "init", "-b", "main", str(self.root)], check=True, capture_output=True, text=True)
        subprocess.run(["git", "-C", str(self.root), "config", "user.email", "aimes-test@example.com"], check=True)
        subprocess.run(["git", "-C", str(self.root), "config", "user.name", "AIMES Test"], check=True)
        (self.root / "README.md").write_text("# baseline\\n", encoding="utf-8")
        subprocess.run(["git", "-C", str(self.root), "add", "README.md"], check=True)
        subprocess.run(["git", "-C", str(self.root), "commit", "-m", "baseline"], check=True, capture_output=True, text=True)
        base = subprocess.run(["git", "-C", str(self.root), "rev-parse", "HEAD"], check=True, capture_output=True, text=True).stdout.strip()
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            claim_code = main([
                "task", "claim", "--root", str(self.root), "--task-id", "TASK-CLI-001",
                "--tool-id", "trae-code", "--branch", "main", "--base-commit", base,
                "--allowed-path", "src/", "--confirm", "cLaIm", "--format", "json",
            ])
        self.assertEqual(claim_code, 0, output.getvalue())
        handoff = self.root / "project-control" / "handoffs" / "2026-10-18-TASK-CLI-001-trae-code.md"
        handoff.parent.mkdir(parents=True)
        handoff.write_text(
            f"""# Task Handoff: TASK-CLI-001
- **Task ID:** TASK-CLI-001
- **Baseline commit:** `{base}`
- **Task status:** IN_PROGRESS
- **Evidence status:** NOT_RUN

## 1. Goal and acceptance criteria
Goal

## 2. Repository state at handoff
State

## 3. Changes made
Changes

## 4. Verification evidence
NOT_RUN

## 5. Open issues, risks and decisions
None

## 6. Next steps
Continue

## 7. Incoming tool checklist
Check
""",
            encoding="utf-8",
        )
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            release_code = main([
                "task", "release", "--root", str(self.root), "--task-id", "TASK-CLI-001",
                "--tool-id", "trae-code", "--handoff-file",
                "project-control/handoffs/2026-10-18-TASK-CLI-001-trae-code.md",
                "--confirm", "rElEaSe", "--format", "json",
            ])
        self.assertEqual(release_code, 0, output.getvalue())

    def test_require_active_fails_when_declaration_is_missing(self):
        with contextlib.redirect_stdout(io.StringIO()):
            code = main(["task", "validate", "--root", str(self.root), "--require-active", "--format", "json"])
        self.assertEqual(code, 1)


if __name__ == "__main__":
    unittest.main()
