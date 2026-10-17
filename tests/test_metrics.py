from datetime import datetime, timedelta, timezone
from pathlib import Path
import json
import tempfile
import unittest

import yaml
from aimes_cli.metrics import build_metrics_report


class MetricsReportTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / "README.md").write_text("# Demo project\n", encoding="utf-8")

    def tearDown(self):
        self.tmp.cleanup()

    def test_missing_sources_are_unknown_not_zero(self):
        report = build_metrics_report(self.root)
        self.assertTrue(report["ok"], report["findings"])
        self.assertEqual(report["summary"]["metrics_total"], 9)
        self.assertEqual(report["summary"]["metrics_unknown"], 9)
        self.assertTrue(all(metric["value"] is None for metric in report["metrics"]))

    def test_trace_metrics_calculate_from_valid_manifest_and_evidence(self):
        (self.root / "logs").mkdir()
        (self.root / "logs" / "test.log").write_text("pytest passed", encoding="utf-8")
        (self.root / "evidence.yaml").write_text(
            yaml.safe_dump({
                "schema_version": 1,
                "evidence": [{
                    "id": "E-1", "kind": "test", "command": "pytest", "exit_code": 0,
                    "result": "PASS", "observed_at": datetime.now(timezone.utc).isoformat(),
                    "artifact_path": "logs/test.log",
                }],
            }),
            encoding="utf-8",
        )
        manifest = {
            "schema_version": 1,
            "evidence_file": "evidence.yaml",
            "entities": [
                {"id": "REQ-1", "type": "requirement", "status": "APPROVED", "links": [{"target": "FEAT-1", "relation": "realizes"}]},
                {"id": "FEAT-1", "type": "feature", "status": "PLANNED", "critical": True,
                 "links": [{"target": "IMPL-1", "relation": "implemented_by"}, {"target": "TEST-1", "relation": "verified_by"}]},
                {"id": "IMPL-1", "type": "implementation", "status": "IMPLEMENTED_UNVERIFIED", "links": []},
                {"id": "TEST-1", "type": "test", "status": "VERIFIED", "links": [], "evidence_refs": ["E-1"]},
            ],
        }
        trace_path = self.root / "trace.yaml"
        trace_path.write_text(yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8")
        report = build_metrics_report(self.root, trace_manifest=trace_path)
        self.assertTrue(report["ok"], report["findings"])
        metrics = {item["id"]: item for item in report["metrics"]}
        for metric_id in (
            "requirement_traceability_rate", "feature_implementation_mapping_rate",
            "feature_test_mapping_rate", "verification_evidence_completeness_rate",
            "trace_reference_validity_rate",
        ):
            self.assertEqual(metrics[metric_id]["value"], 1.0, metrics[metric_id])

    def test_handoff_temp_and_gate_metrics_use_supplied_sources(self):
        now = datetime.now(timezone.utc)
        evidence = self.root / "handoff-proof.txt"
        evidence.write_text("reviewed", encoding="utf-8")
        trials = self.root / "handoff-trials.yaml"
        trials.write_text(yaml.safe_dump({
            "schema_version": 1,
            "trials": [
                {"task_id": "T-1", "resumed_without_chat": True, "evidence_file": "handoff-proof.txt"},
                {"task_id": "T-2", "resumed_without_chat": False, "evidence_file": "handoff-proof.txt"},
            ],
        }), encoding="utf-8")
        temp_file = self.root / "known.tmp"
        temp_file.write_text("registered", encoding="utf-8")
        temp_registry = self.root / "temp-registry.yaml"
        temp_registry.write_text(yaml.safe_dump({
            "schema_version": 1,
            "entries": [{
                "id": "TMP-1", "path": "known.tmp", "purpose": "test", "classification": "B",
                "status": "ACTIVE", "created_at": now.isoformat(),
                "expires_at": (now + timedelta(days=1)).isoformat(),
            }],
        }), encoding="utf-8")
        (self.root / "pip-install-demo").mkdir()
        audit_log = self.root / "events.jsonl"
        audit_log.write_text(
            json.dumps({"event_id": "1", "event_type": "gate.bypassed"}) + "\n" +
            json.dumps({"event_id": "2", "event_type": "task.completed"}) + "\n",
            encoding="utf-8",
        )
        report = build_metrics_report(
            self.root, handoff_trials=trials, temp_registry=temp_registry, audit_log=audit_log
        )
        self.assertTrue(report["ok"], report["findings"])
        metrics = {item["id"]: item for item in report["metrics"]}
        self.assertEqual(metrics["handoff_recoverability_rate"]["value"], 0.5)
        self.assertEqual(metrics["temporary_file_compliance_rate"]["value"], 0.5)
        self.assertEqual(metrics["gate_bypass_count"]["value"], 1)


if __name__ == "__main__":
    unittest.main()
