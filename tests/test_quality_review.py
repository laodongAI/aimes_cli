import json
from pathlib import Path
import tempfile
import unittest

from aimes_cli.quality_review import validate_ai_review_report


class AIReviewReportTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / "src").mkdir()
        (self.root / "src" / "Page.vue").write_text("<template>\n<div/>\n</template>\n", encoding="utf-8")

    def tearDown(self):
        self.tmp.cleanup()

    def _report(self, evidence=None, severity="WARNING", confidence=0.91):
        report = {
            "schema_version": 1,
            "findings": [{
                "id": "AI-001", "category": "component-reuse", "severity": severity,
                "message": "Potential duplicate presentation logic.",
                "recommendation": "Check whether a shared component is appropriate.",
                "confidence": confidence,
                "evidence": evidence or {"path": "src/Page.vue", "line_start": 1, "line_end": 3, "excerpt": "<template>"},
            }],
        }
        path = self.root / "review.json"
        path.write_text(json.dumps(report), encoding="utf-8")
        return path

    def test_accepts_evidence_backed_ai_advisory(self):
        result = validate_ai_review_report(self._report(), self.root)
        self.assertTrue(result["ok"])
        self.assertEqual(result["findings"][0]["origin"], "ai")
        self.assertFalse(result["findings"][0]["blocking"])

    def test_ai_cannot_assign_blocking_error(self):
        result = validate_ai_review_report(self._report(severity="ERROR"), self.root)
        self.assertFalse(result["ok"])

    def test_rejects_excerpt_not_matching_source(self):
        result = validate_ai_review_report(self._report(evidence={"path": "src/Page.vue", "line_start": 1, "line_end": 1, "excerpt": "secret"}), self.root)
        self.assertFalse(result["ok"])

    def test_rejects_path_traversal(self):
        result = validate_ai_review_report(self._report(evidence={"path": "../outside.py", "line_start": 1, "line_end": 1, "excerpt": "x"}), self.root)
        self.assertFalse(result["ok"])

    def test_rejects_confidence_out_of_range(self):
        result = validate_ai_review_report(self._report(confidence=1.5), self.root)
        self.assertFalse(result["ok"])

    def test_report_must_be_inside_project(self):
        outside = Path(self.tmp.name).parent / "outside-review.json"
        outside.write_text('{"schema_version":1,"findings":[]}', encoding="utf-8")
        try:
            result = validate_ai_review_report(outside, self.root)
            self.assertFalse(result["ok"])
        finally:
            outside.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
