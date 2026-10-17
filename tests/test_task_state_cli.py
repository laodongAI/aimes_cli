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

    def test_require_active_fails_when_declaration_is_missing(self):
        with contextlib.redirect_stdout(io.StringIO()):
            code = main(["task", "validate", "--root", str(self.root), "--require-active", "--format", "json"])
        self.assertEqual(code, 1)


if __name__ == "__main__":
    unittest.main()
