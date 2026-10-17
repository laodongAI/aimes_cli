from datetime import datetime, timedelta, timezone
from pathlib import Path
import tempfile
import unittest

import yaml
from aimes_cli.cleanup_audit import audit_temp_registry


class CleanupAuditTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / ".aimes").mkdir()
        self.registry = self.root / ".aimes" / "temp-registry.yaml"

    def tearDown(self):
        self.tmp.cleanup()

    def test_missing_registry_is_warning_and_does_not_delete_candidates(self):
        candidate = self.root / "pip-install-demo"
        candidate.mkdir()
        (candidate / "marker.txt").write_text("keep", encoding="utf-8")
        result = audit_temp_registry(self.root)
        self.assertTrue(result["ok"])
        self.assertTrue(any(item["code"] == "REGISTRY_MISSING" for item in result["findings"]))
        self.assertTrue(any(item["path"] == "pip-install-demo" for item in result["candidates"]))
        self.assertTrue((candidate / "marker.txt").is_file())

    def test_registered_expired_item_is_reported(self):
        path = self.root / "build-output.tmp"
        path.write_text("data", encoding="utf-8")
        data = {
            "schema_version": 1,
            "entries": [{
                "id": "TMP-1", "path": "build-output.tmp", "purpose": "test",
                "created_at": "2026-01-01T00:00:00+00:00",
                "expires_at": (datetime.now(timezone.utc) - timedelta(days=1)).isoformat(),
                "classification": "B", "status": "ACTIVE"
            }]
        }
        self.registry.write_text(yaml.safe_dump(data), encoding="utf-8")
        result = audit_temp_registry(self.root)
        self.assertTrue(any(item["code"] == "TEMP_EXPIRED" for item in result["findings"]))
        self.assertTrue(path.exists())

    def test_path_escape_is_rejected(self):
        self.registry.write_text(yaml.safe_dump({
            "schema_version": 1,
            "entries": [{"id":"TMP-2","path":"../outside","purpose":"bad","classification":"A","status":"ACTIVE"}]
        }), encoding="utf-8")
        result = audit_temp_registry(self.root)
        self.assertFalse(result["ok"])
        self.assertTrue(any(item["code"] == "PATH_INVALID" for item in result["findings"]))

    def test_duplicate_ids_are_rejected(self):
        entry = {"id":"TMP-DUP","path":"one.tmp","purpose":"test","classification":"B","status":"ACTIVE"}
        self.registry.write_text(yaml.safe_dump({"schema_version":1,"entries":[entry,entry]}), encoding="utf-8")
        result = audit_temp_registry(self.root)
        self.assertFalse(result["ok"])
        self.assertTrue(any(item["code"] == "DUPLICATE_ID" for item in result["findings"]))


if __name__ == "__main__":
    unittest.main()
