import json
from pathlib import Path
import tempfile
import unittest

from aimes_cli.quality_report import build_quality_report
from aimes_cli.cli import parser


class UnifiedQualityReportTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / ".aimes").mkdir()
        (self.root / "src").mkdir()
        (self.root / "src" / "Page.vue").write_text("<template>\n<div/>\n</template>\n", encoding="utf-8")
        (self.root / ".aimes" / "quality-gates.yaml").write_text(
            "schema_version: 1\nenabled: true\nenforce: false\nfail_on: ERROR\n", encoding="utf-8"
        )

    def tearDown(self):
        self.tmp.cleanup()

    def _ai_report(self):
        path = self.root / ".aimes" / "review.json"
        path.write_text(json.dumps({
            "schema_version": 1,
            "findings": [{
                "id": "AI-001", "category": "component-reuse", "severity": "WARNING",
                "message": "Potential duplicate component responsibility.",
                "recommendation": "Compare behavior before extracting a shared component.",
                "confidence": 0.88,
                "evidence": {"path": "src/Page.vue", "line_start": 1, "line_end": 3, "excerpt": "<template>"},
            }],
        }), encoding="utf-8")
        return path

    def test_cli_parser_exposes_unified_report_command(self):
        args = parser().parse_args(["quality", "report", "--root", str(self.root), "--ai-report", ".aimes/review.json", "--format", "json"])
        self.assertEqual(args.quality_command, "report")
        self.assertEqual(str(args.ai_report), ".aimes/review.json")

    def test_unifies_static_and_ai_findings(self):
        result = build_quality_report(self.root, self._ai_report())
        self.assertTrue(result["ok"])
        self.assertEqual(result["summary"]["ai_findings"], 1)
        self.assertTrue(any(item["origin"] == "ai" for item in result["findings"]))
        self.assertTrue(all(not item["blocking"] for item in result["findings"]))

    def test_ai_warning_does_not_fail_static_gate(self):
        result = build_quality_report(self.root, self._ai_report())
        self.assertTrue(result["ok"])
        self.assertEqual(result["summary"]["blocking_findings"], 0)

    def test_invalid_ai_report_is_not_silently_merged(self):
        path = self._ai_report()
        path.write_text('{"schema_version": 1, "findings": [{"severity": "ERROR"}]}', encoding="utf-8")
        result = build_quality_report(self.root, path)
        self.assertFalse(result["ok"])
        self.assertEqual(result["status"], "INVALID_AI_REPORT")
        self.assertEqual(result["findings"], [])

    def test_static_gate_result_remains_authoritative(self):
        (self.root / ".aimes" / "quality-gates.yaml").write_text(
            "schema_version: 1\nenabled: true\nenforce: true\nfail_on: ERROR\n", encoding="utf-8"
        )
        huge = "<template>\n" + ("<div/>\n" * 650) + "</template>"
        (self.root / "src" / "Page.vue").write_text(huge, encoding="utf-8")
        result = build_quality_report(self.root, self._ai_report())
        self.assertFalse(result["ok"])
        self.assertEqual(result["status"], "STATIC_QUALITY_GATE_FAILED")
        self.assertTrue(any(item["origin"] == "ai" and not item["blocking"] for item in result["findings"]))


if __name__ == "__main__":
    unittest.main()
